from flask import Blueprint, jsonify, request

from backend_app.agent.errors import AgentRuntimeError

from . import repository


def create_ai_settings_blueprint(service_factory, instance_token_validator=None):
    blueprint = Blueprint("ai_settings_v2", __name__)

    @blueprint.route("/api/ai/migration-status", methods=["GET"])
    def migration_status_api():
        return jsonify({
            "code": 200,
            "data": service_factory().legacy_migration_status(),
        })

    @blueprint.route("/api/ai/providers", methods=["GET", "POST"])
    def providers_api():
        service = service_factory()
        if request.method == "GET":
            return jsonify({"code": 200, "data": service.list_providers()})
        try:
            provider = service.save_provider(request.get_json(silent=True) or {})
            return jsonify({"code": 200, "message": "Provider 已保存", "data": provider})
        except ValueError as exc:
            return jsonify({"code": 400, "message": str(exc), "data": None}), 400

    @blueprint.route("/api/ai/providers/<provider_id>", methods=["PUT", "DELETE"])
    def provider_api(provider_id):
        service = service_factory()
        if request.method == "DELETE":
            if any(
                profile["provider_id"] == provider_id
                for profile in service.list_model_profiles()
            ):
                return jsonify({
                    "code": 409,
                    "message": "Provider 已被模型使用，请先调整或删除相关模型",
                    "data": None,
                }), 409
            deleted = repository.delete_provider(service.db_path, provider_id)
            if not deleted:
                return jsonify({"code": 404, "message": "Provider 不存在", "data": None}), 404
            return jsonify({"code": 200, "message": "Provider 已删除", "data": None})
        try:
            provider = service.save_provider(request.get_json(silent=True) or {}, provider_id)
            return jsonify({"code": 200, "message": "Provider 已更新", "data": provider})
        except ValueError as exc:
            return jsonify({"code": 400, "message": str(exc), "data": None}), 400

    @blueprint.route("/api/ai/providers/<provider_id>/credential", methods=["PUT", "DELETE"])
    def provider_credential_api(provider_id):
        service = service_factory()
        if request.method == "DELETE":
            service.clear_credential(provider_id)
            return jsonify({"code": 200, "message": "Provider 密钥已删除", "data": None})
        api_key = str((request.get_json(silent=True) or {}).get("apiKey") or "").strip()
        if not api_key:
            return jsonify({"code": 400, "message": "API Key 不能为空", "data": None}), 400
        try:
            service.set_credential(provider_id, api_key)
            return jsonify({
                "code": 200,
                "message": "Provider 密钥已安全保存",
                "data": {"credentialConfigured": True},
            })
        except KeyError as exc:
            return jsonify({"code": 404, "message": str(exc), "data": None}), 404
        except (ValueError, RuntimeError) as exc:
            return jsonify({"code": 400, "message": str(exc), "data": None}), 400

    @blueprint.route("/api/ai/model-profiles", methods=["GET", "POST"])
    def model_profiles_api():
        service = service_factory()
        if request.method == "GET":
            return jsonify({"code": 200, "data": service.list_model_profiles()})
        try:
            profile = service.save_model_profile(request.get_json(silent=True) or {})
            return jsonify({"code": 200, "message": "模型配置已保存", "data": profile})
        except ValueError as exc:
            return jsonify({"code": 400, "message": str(exc), "data": None}), 400

    @blueprint.route("/api/ai/providers/<provider_id>/test", methods=["POST"])
    def test_provider_api(provider_id):
        try:
            result = service_factory().test_provider_connection(provider_id)
            return jsonify({"code": 200, "message": "连接和鉴权通过", "data": result})
        except KeyError:
            return jsonify({"code": 404, "message": "Provider 不存在", "data": None}), 404
        except AgentRuntimeError as exc:
            return jsonify({"code": 400, "message": str(exc), "errorCode": exc.code, "data": None}), 400
        except (ValueError, RuntimeError) as exc:
            return jsonify({"code": 400, "message": str(exc), "data": None}), 400

    @blueprint.route("/api/ai/model-profiles/<profile_id>", methods=["PUT", "DELETE"])
    def model_profile_api(profile_id):
        service = service_factory()
        if request.method == "DELETE":
            deleted = repository.delete_model_profile(service.db_path, profile_id)
            if not deleted:
                return jsonify({"code": 404, "message": "模型配置不存在", "data": None}), 404
            return jsonify({"code": 200, "message": "模型配置已删除", "data": None})
        try:
            profile = service.save_model_profile(request.get_json(silent=True) or {}, profile_id)
            return jsonify({"code": 200, "message": "模型配置已更新", "data": profile})
        except ValueError as exc:
            return jsonify({"code": 400, "message": str(exc), "data": None}), 400

    @blueprint.route("/api/ai/agent-profiles", methods=["GET"])
    def agent_profiles_api():
        service = service_factory()
        service.ensure_default_agent_profiles()
        return jsonify({"code": 200, "data": service.list_agent_profiles()})

    @blueprint.route("/api/ai/agent-profiles/<agent_key>", methods=["PUT"])
    def agent_profile_api(agent_key):
        try:
            profile = service_factory().save_agent_profile(
                request.get_json(silent=True) or {}, agent_key
            )
            return jsonify({"code": 200, "message": "Agent 配置已更新", "data": profile})
        except ValueError as exc:
            return jsonify({"code": 400, "message": str(exc), "data": None}), 400

    @blueprint.route("/runtime/ai/pi-credential", methods=["POST"])
    def migrate_pi_credential():
        if not instance_token_validator or not instance_token_validator():
            return jsonify({"code": 403, "message": "无效的桌面运行时令牌", "data": None}), 403
        payload = request.get_json(silent=True) or {}
        api_key = str(payload.get("apiKey") or "").strip()
        if not api_key:
            return jsonify({"code": 400, "message": "PI Agent 密钥为空", "data": None}), 400
        service = service_factory()
        try:
            provider = service.save_provider(
                {
                    "name": "DeepSeek Direct",
                    "provider_type": "openai_compatible",
                    "base_url": payload.get("baseUrl") or "https://api.deepseek.com",
                    "timeout_seconds": payload.get("timeout") or 300,
                    "enabled": True,
                    "capabilities": {"tools": True},
                },
                "deepseek-direct",
            )
            service.set_credential(provider["id"], api_key)
            model = service.save_model_profile(
                {
                    "name": "DeepSeek Tool Agent",
                    "provider_id": provider["id"],
                    "model_name": payload.get("model") or "deepseek-chat",
                    "extra_options": {
                        "thinking_level": payload.get("thinkingLevel") or "off"
                    },
                    "enabled": True,
                },
                "deepseek-tool-agent",
            )
            service.save_agent_profile(
                {
                    "name": "运营工具 Agent",
                    "execution_mode": "tool_loop",
                    "primary_model_profile_id": model["id"],
                    "timeout_seconds": payload.get("timeout") or 300,
                    "max_steps": 8,
                    "enabled": True,
                },
                "piOperations",
            )
            return jsonify({
                "code": 200,
                "message": "PI Agent 配置已迁移到统一 AI Runtime",
                "data": {"credentialConfigured": True, "agentKey": "piOperations"},
            })
        except (ValueError, RuntimeError) as exc:
            return jsonify({"code": 400, "message": str(exc), "data": None}), 400

    return blueprint
