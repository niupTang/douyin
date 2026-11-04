import re
import time

from flask import Blueprint, jsonify, request


def create_legacy_ai_settings_blueprint(
    load_runtime_settings, save_runtime_settings, get_hermes_settings,
    public_hermes_settings, hermes_request, get_agent_models,
    normalize_agent_model, call_hermes_structured, log,
):
    blueprint = Blueprint("ai_settings_legacy", __name__)

    @blueprint.route("/settings/hermes", methods=["GET", "PUT"])
    def hermes_settings_api():
        settings = load_runtime_settings()
        if request.method == "GET":
            return jsonify({"code": 200, "data": public_hermes_settings(settings)})
        payload = request.get_json(silent=True) or {}
        current = get_hermes_settings(settings)
        gateway_url = str(payload.get("gatewayUrl") or "").strip().rstrip("/")
        if not re.match(r"^https?://", gateway_url, re.IGNORECASE):
            return jsonify({"code": 400, "message": "Gateway 地址必须以 http:// 或 https:// 开头"}), 400
        try:
            timeout = max(10, min(int(payload.get("timeout") or current["timeout"]), 1800))
        except (TypeError, ValueError):
            return jsonify({"code": 400, "message": "超时时间必须是数字"}), 400
        api_key = current["apiKey"]
        if payload.get("clearApiKey"):
            api_key = ""
        elif payload.get("apiKey"):
            api_key = str(payload.get("apiKey")).strip()
        settings["hermes"] = {"gatewayUrl": gateway_url, "apiKey": api_key, "timeout": timeout}
        save_runtime_settings(settings)
        return jsonify({"code": 200, "message": "Hermes 配置已保存", "data": public_hermes_settings(settings)})


    @blueprint.route("/settings/hermes/test", methods=["POST"])
    def test_hermes_settings():
        try:
            payload = request.get_json(silent=True) or {}
            saved_settings = load_runtime_settings()
            saved_hermes = get_hermes_settings(saved_settings)
            gateway_url = str(payload.get("gatewayUrl") or "").strip().rstrip("/")
            if not re.match(r"^https?://", gateway_url, re.IGNORECASE):
                return jsonify({"code": 400, "message": "Gateway 地址必须以 http:// 或 https:// 开头"}), 400
            try:
                timeout = max(10, min(int(payload.get("timeout") or saved_hermes["timeout"]), 1800))
            except (TypeError, ValueError):
                return jsonify({"code": 400, "message": "超时时间必须是数字"}), 400
            test_settings = {
                "hermes": {
                    "gatewayUrl": gateway_url,
                    "apiKey": str(payload.get("apiKey") or saved_hermes["apiKey"]).strip(),
                    "timeout": timeout,
                }
            }
            health = hermes_request("/health", timeout=min(timeout, 15), settings=test_settings)
            capabilities = None
            try:
                capabilities = hermes_request(
                    "/v1/capabilities", timeout=min(timeout, 20), settings=test_settings
                )
            except Exception as exc:
                log(f"Hermes capabilities unavailable, using legacy mode: {exc}")
            return jsonify({"code": 200, "message": "Hermes Gateway 连接正常", "data": {
                "health": health, "capabilities": capabilities,
                "legacyMode": capabilities is None,
            }})
        except Exception as exc:
            return jsonify({"code": 502, "message": str(exc), "data": None}), 502


    @blueprint.route("/settings/hermes/models", methods=["GET"])
    def discover_hermes_models():
        try:
            refresh = request.args.get("refresh") in {"1", "true", "True"}
            path = "/api/model/options?refresh=1" if refresh else "/api/model/options"
            try:
                options = hermes_request(path, timeout=60 if refresh else 30)
            except Exception as exc:
                log(f"Hermes rich model catalog unavailable, using /v1/models: {exc}")
                legacy = hermes_request("/v1/models", timeout=30)
                rows = legacy.get("data") if isinstance(legacy, dict) else []
                options = {
                    "legacyMode": True,
                    "providers": [{
                        "provider": "gateway-default",
                        "models": [
                            {"id": item.get("id"), "name": item.get("id")}
                            for item in (rows or []) if isinstance(item, dict) and item.get("id")
                        ],
                    }],
                }
            return jsonify({"code": 200, "data": options})
        except Exception as exc:
            return jsonify({"code": 502, "message": str(exc), "data": None}), 502


    @blueprint.route("/settings/agent-models", methods=["GET", "POST"])
    def agent_models_api():
        settings = load_runtime_settings()
        if request.method == "GET":
            task_models = settings.get("taskModels") if isinstance(settings.get("taskModels"), dict) else {}
            return jsonify({"code": 200, "data": {"models": get_agent_models(settings), "taskModels": task_models}})
        try:
            model = normalize_agent_model(request.get_json(silent=True) or {})
            models = get_agent_models(settings)
            models.append(model)
            settings["agentModels"] = models
            save_runtime_settings(settings)
            return jsonify({"code": 200, "message": "Agent 模型已添加", "data": model})
        except ValueError as exc:
            return jsonify({"code": 400, "message": str(exc), "data": None}), 400


    @blueprint.route("/settings/agent-models/<model_id>", methods=["PUT", "DELETE"])
    def agent_model_api(model_id):
        settings = load_runtime_settings()
        models = get_agent_models(settings)
        index = next((i for i, item in enumerate(models) if item.get("id") == model_id), None)
        if index is None:
            return jsonify({"code": 404, "message": "Agent 模型不存在", "data": None}), 404
        if request.method == "DELETE":
            models.pop(index)
            task_models = settings.get("taskModels") if isinstance(settings.get("taskModels"), dict) else {}
            settings["taskModels"] = {key: value for key, value in task_models.items() if value != model_id}
            settings["agentModels"] = models
            save_runtime_settings(settings)
            return jsonify({"code": 200, "message": "Agent 模型已删除", "data": None})
        try:
            model = normalize_agent_model(request.get_json(silent=True) or {}, existing_id=model_id)
            models[index] = model
            settings["agentModels"] = models
            save_runtime_settings(settings)
            return jsonify({"code": 200, "message": "Agent 模型已更新", "data": model})
        except ValueError as exc:
            return jsonify({"code": 400, "message": str(exc), "data": None}), 400


    @blueprint.route("/settings/task-models", methods=["PUT"])
    def task_models_api():
        payload = request.get_json(silent=True) or {}
        viral_model_id = str(payload.get("viralAnalysis") or "").strip()
        settings = load_runtime_settings()
        if viral_model_id and not any(
            item.get("id") == viral_model_id and item.get("enabled", True)
            for item in get_agent_models(settings)
        ):
            return jsonify({"code": 400, "message": "所选 Agent 模型不存在或已停用", "data": None}), 400
        task_models = settings.get("taskModels") if isinstance(settings.get("taskModels"), dict) else {}
        task_models["viralAnalysis"] = viral_model_id
        settings["taskModels"] = task_models
        save_runtime_settings(settings)
        return jsonify({"code": 200, "message": "爆款拆解模型已保存", "data": task_models})


    @blueprint.route("/settings/agent-models/<model_id>/test", methods=["POST"])
    def test_agent_model(model_id):
        settings = load_runtime_settings()
        model = next((item for item in get_agent_models(settings) if item.get("id") == model_id), None)
        if not model:
            return jsonify({"code": 404, "message": "Agent 模型不存在", "data": None}), 404
        started = time.monotonic()
        try:
            result = call_hermes_structured(
                "只返回一个 JSON 对象，字段 result 的值必须是 OK。",
                {"type": "object", "additionalProperties": False, "required": ["result"],
                 "properties": {"result": {"type": "string"}}},
                model_config=model, timeout=60,
            )
            return jsonify({"code": 200, "message": "模型测试成功", "data": {
                "result": result, "elapsedMs": int((time.monotonic() - started) * 1000),
                "provider": model.get("provider"), "model": model.get("model"),
            }})
        except Exception as exc:
            return jsonify({"code": 502, "message": str(exc), "data": None}), 502

    return blueprint
