import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from backend_app.agent.secret_store import SecretStore
from backend_app.common.database import ensure_core_tables

from . import repository


LEGACY_MIGRATION_KEY = "migration.settings_json.version"
LEGACY_MIGRATION_ERROR_KEY = "migration.settings_json.error"
LEGACY_MIGRATION_VERSION = 1
HERMES_PROVIDER_ID = "hermes-default"


class AiSettingsService:
    def __init__(self, db_path, secret_store=None):
        self.db_path = Path(db_path)
        ensure_core_tables(self.db_path)
        self.secret_store = secret_store or SecretStore()

    def _key_reference(self, provider_id):
        location = str(self.db_path.resolve().parent).casefold().encode("utf-8")
        installation = hashlib.sha256(location).hexdigest()[:16]
        return f"sunbird-ai:{installation}:{provider_id}:v1"

    @staticmethod
    def _validate_base_url(base_url, provider_type):
        if provider_type == "codex_cli":
            return ""
        base_url = str(base_url or "").strip().rstrip("/")
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Provider 地址必须是有效的 HTTP(S) URL")
        host = (parsed.hostname or "").casefold()
        if parsed.scheme == "http" and host not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("非本机 Provider 必须使用 HTTPS")
        return base_url

    def save_provider(self, payload, provider_id=None):
        provider_type = str(payload.get("provider_type") or payload.get("providerType") or "").strip()
        if provider_type not in {"hermes", "openai_compatible", "codex_cli"}:
            raise ValueError("不支持的 Provider 类型")
        name = re.sub(r"\s+", " ", str(payload.get("name") or "")).strip()
        if not name:
            raise ValueError("Provider 名称不能为空")
        try:
            timeout = max(1, min(int(payload.get("timeout_seconds") or payload.get("timeoutSeconds") or 300), 3600))
        except (TypeError, ValueError) as exc:
            raise ValueError("Provider 超时时间必须是数字") from exc
        return repository.save_provider(
            self.db_path,
            {
                "id": provider_id or payload.get("id"),
                "name": name,
                "provider_type": provider_type,
                "base_url": self._validate_base_url(
                    payload.get("base_url") or payload.get("baseUrl"), provider_type
                ),
                "timeout_seconds": timeout,
                "enabled": bool(payload.get("enabled", True)),
                "capabilities": payload.get("capabilities") or {},
            },
        )

    def list_providers(self):
        providers = repository.list_providers(self.db_path)
        for provider in providers:
            provider["credentialConfigured"] = bool(
                repository.get_credential(self.db_path, provider["id"])
            )
        return providers

    def set_credential(self, provider_id, plaintext):
        if not repository.get_provider(self.db_path, provider_id):
            raise KeyError("Provider 不存在")
        encrypted = self.secret_store.encrypt(
            plaintext, self._key_reference(provider_id)
        )
        repository.save_credential(self.db_path, provider_id, encrypted.as_dict())

    def clear_credential(self, provider_id):
        return repository.delete_credential(self.db_path, provider_id)

    def get_credential_secret(self, provider_id):
        encrypted = repository.get_credential(self.db_path, provider_id)
        return self.secret_store.decrypt(encrypted) if encrypted else ""

    def test_provider_connection(self, provider_id):
        from backend_app.agent.providers.openai_compatible import OpenAICompatibleProviderAdapter

        provider = repository.get_provider(self.db_path, provider_id)
        if not provider:
            raise KeyError("Provider 不存在")
        if provider["provider_type"] == "codex_cli":
            raise ValueError("Codex CLI 请通过具体模型任务验证")
        return OpenAICompatibleProviderAdapter(
            provider, {}, self.get_credential_secret(provider_id)
        ).check_connection()

    def save_model_profile(self, payload, profile_id=None):
        provider_id = str(payload.get("provider_id") or payload.get("providerId") or "").strip()
        if not repository.get_provider(self.db_path, provider_id):
            raise ValueError("所选 Provider 不存在")
        name = re.sub(r"\s+", " ", str(payload.get("name") or "")).strip()
        model_name = str(payload.get("model_name") or payload.get("modelName") or "").strip()
        if not name or not model_name:
            raise ValueError("模型名称和 Model 均不能为空")
        return repository.save_model_profile(
            self.db_path,
            {
                "id": profile_id or payload.get("id"),
                "provider_id": provider_id,
                "name": name,
                "model_name": model_name,
                "reasoning_effort": str(payload.get("reasoning_effort") or payload.get("reasoningEffort") or "").strip(),
                "service_tier": str(payload.get("service_tier") or payload.get("serviceTier") or "").strip(),
                "temperature": payload.get("temperature"),
                "max_tokens": payload.get("max_tokens") or payload.get("maxTokens"),
                "extra_options": payload.get("extra_options") or payload.get("extraOptions") or {},
                "enabled": bool(payload.get("enabled", True)),
            },
        )

    def list_model_profiles(self):
        return repository.list_model_profiles(self.db_path)

    def save_agent_profile(self, payload, agent_key=None):
        agent_key = str(agent_key or payload.get("agent_key") or payload.get("agentKey") or "").strip()
        if not agent_key:
            raise ValueError("Agent Key 不能为空")
        execution_mode = str(payload.get("execution_mode") or payload.get("executionMode") or "structured").strip()
        if execution_mode not in {"structured", "tool_loop"}:
            raise ValueError("Agent 执行方式必须是 structured 或 tool_loop")
        primary_id = payload.get("primary_model_profile_id") or payload.get("primaryModelProfileId") or None
        fallback_id = payload.get("fallback_model_profile_id") or payload.get("fallbackModelProfileId") or None
        for profile_id in (primary_id, fallback_id):
            if profile_id and not repository.get_model_profile(self.db_path, profile_id):
                raise ValueError("Agent 绑定的模型不存在")
        return repository.save_agent_profile(
            self.db_path,
            {
                "agent_key": agent_key,
                "name": str(payload.get("name") or agent_key).strip(),
                "execution_mode": execution_mode,
                "primary_model_profile_id": primary_id,
                "fallback_model_profile_id": fallback_id,
                "timeout_seconds": max(1, min(int(payload.get("timeout_seconds") or payload.get("timeoutSeconds") or 300), 3600)),
                "max_steps": max(1, min(int(payload.get("max_steps") or payload.get("maxSteps") or 8), 100)),
                "enabled": bool(payload.get("enabled", True)),
            },
        )

    def list_agent_profiles(self):
        return repository.list_agent_profiles(self.db_path)

    def ensure_default_agent_profiles(self):
        models = repository.list_model_profiles(self.db_path, enabled_only=True)
        if not models:
            return []
        default_model_id = models[0]["id"]
        codex_model = next(
            (
                model
                for model in models
                if (repository.get_provider(self.db_path, model["provider_id"]) or {}).get("provider_type") == "codex_cli"
            ),
            None,
        )
        defaults = {
            "benchmarkAnalysis": ("对标作品分析", "structured", (codex_model or models[0])["id"]),
            "viralAnalysis": ("爆款拆解", "structured"),
            "scriptGeneration": ("口播文案生成", "structured"),
            "ideaRadar": ("选题雷达", "structured"),
            "accountDiagnosis": ("账号诊断", "structured"),
            "ownContentReview": ("自有作品复盘", "structured"),
            "piOperations": ("运营工具 Agent", "tool_loop"),
        }
        created = []
        for agent_key, definition in defaults.items():
            name, execution_mode = definition[:2]
            selected_model_id = definition[2] if len(definition) > 2 else default_model_id
            if repository.get_agent_profile(self.db_path, agent_key):
                continue
            created.append(
                self.save_agent_profile(
                    {
                        "agent_key": agent_key,
                        "name": name,
                        "execution_mode": execution_mode,
                        "primary_model_profile_id": selected_model_id,
                        "timeout_seconds": 300,
                        "max_steps": 8,
                    },
                    agent_key,
                )
            )
        return created

    def legacy_settings(self):
        settings = repository.list_app_settings(self.db_path)
        hermes = repository.get_provider(self.db_path, HERMES_PROVIDER_ID)
        if hermes:
            settings["hermes"] = {
                "gatewayUrl": hermes.get("base_url") or "http://127.0.0.1:8642",
                "apiKey": self.get_credential_secret(HERMES_PROVIDER_ID),
                "timeout": hermes["timeout_seconds"],
            }
        models = []
        for profile in repository.list_model_profiles(self.db_path):
            provider = repository.get_provider(self.db_path, profile["provider_id"])
            if not provider or provider.get("provider_type") != "hermes":
                continue
            options = profile.get("extra_options") or {}
            models.append(
                {
                    "id": profile["id"],
                    "name": profile["name"],
                    "provider": options.get("gateway_provider") or "gateway-default",
                    "model": profile["model_name"],
                    "reasoningEffort": profile.get("reasoning_effort") or "",
                    "serviceTier": profile.get("service_tier") or "",
                    "enabled": profile["enabled"],
                }
            )
        settings["agentModels"] = models
        settings["taskModels"] = {
            profile["agent_key"]: profile.get("primary_model_profile_id") or ""
            for profile in repository.list_agent_profiles(self.db_path)
            if profile["execution_mode"] == "structured"
        }
        return settings

    def apply_legacy_settings(self, settings):
        settings = settings if isinstance(settings, dict) else {}
        hermes = settings.get("hermes") if isinstance(settings.get("hermes"), dict) else {}
        self.save_provider(
            {
                "id": HERMES_PROVIDER_ID,
                "name": "Hermes Gateway",
                "provider_type": "hermes",
                "base_url": hermes.get("gatewayUrl") or "http://127.0.0.1:8642",
                "timeout_seconds": hermes.get("timeout") or 300,
                "enabled": True,
            },
            HERMES_PROVIDER_ID,
        )
        if hermes.get("apiKey"):
            self.set_credential(HERMES_PROVIDER_ID, str(hermes["apiKey"]))
        else:
            self.clear_credential(HERMES_PROVIDER_ID)

        codex_model = str(settings.get("codexAnalysisModel") or settings.get("codex_model") or "gpt-5.4-mini")
        codex_path = str(settings.get("codexCliPath") or settings.get("codex_cli_path") or "codex")
        codex_timeout = settings.get("codexAnalysisTimeout") or settings.get("codex_timeout") or 180
        codex_provider = self.save_provider(
            {
                "id": "codex-cli",
                "name": "Codex CLI",
                "provider_type": "codex_cli",
                "timeout_seconds": codex_timeout,
                "enabled": True,
            },
            "codex-cli",
        )
        codex_profile = self.save_model_profile(
            {
                "id": "codex-cli-analysis",
                "provider_id": codex_provider["id"],
                "name": "Codex CLI 分析",
                "model_name": codex_model,
                "extra_options": {"executable": codex_path},
                "enabled": True,
            },
            "codex-cli-analysis",
        )
        self.save_agent_profile(
            {
                "agent_key": "benchmarkAnalysis",
                "name": "对标作品分析",
                "execution_mode": "structured",
                "primary_model_profile_id": codex_profile["id"],
                "timeout_seconds": codex_timeout,
            },
            "benchmarkAnalysis",
        )

        desired_model_ids = set()
        for model in settings.get("agentModels") or []:
            if not isinstance(model, dict):
                continue
            model_id = str(model.get("id") or "").strip()
            profile = self.save_model_profile(
                {
                    "id": model_id or None,
                    "provider_id": HERMES_PROVIDER_ID,
                    "name": model.get("name"),
                    "model_name": model.get("model"),
                    "reasoning_effort": model.get("reasoningEffort"),
                    "service_tier": model.get("serviceTier"),
                    "extra_options": {"gateway_provider": model.get("provider") or "gateway-default"},
                    "enabled": model.get("enabled", True),
                },
                model_id or None,
            )
            desired_model_ids.add(profile["id"])
        for profile in repository.list_model_profiles(self.db_path):
            if profile["provider_id"] == HERMES_PROVIDER_ID and profile["id"] not in desired_model_ids:
                repository.delete_model_profile(self.db_path, profile["id"])

        task_models = settings.get("taskModels") if isinstance(settings.get("taskModels"), dict) else {}
        for agent_key, model_id in task_models.items():
            if model_id and not repository.get_model_profile(self.db_path, model_id):
                raise ValueError("Agent 绑定的模型不存在或已停用")
            existing = repository.get_agent_profile(self.db_path, agent_key) or {}
            self.save_agent_profile(
                {
                    "agent_key": agent_key,
                    "name": existing.get("name") or agent_key,
                    "execution_mode": existing.get("execution_mode") or "structured",
                    "primary_model_profile_id": model_id or None,
                    "fallback_model_profile_id": existing.get("fallback_model_profile_id"),
                    "timeout_seconds": existing.get("timeout_seconds") or 300,
                    "max_steps": existing.get("max_steps") or 8,
                    "enabled": existing.get("enabled", True),
                },
                agent_key,
            )

        reserved = {"hermes", "agentModels", "taskModels"}
        for key, value in settings.items():
            if key not in reserved:
                repository.set_app_setting(self.db_path, key, value)
        return self.legacy_settings()

    def legacy_migration_status(self):
        if repository.get_app_setting(
            self.db_path, LEGACY_MIGRATION_KEY
        ) == LEGACY_MIGRATION_VERSION:
            return {"status": "complete", "message": "旧配置已迁移"}
        error = repository.get_app_setting(
            self.db_path, LEGACY_MIGRATION_ERROR_KEY, {}
        )
        if isinstance(error, dict) and error.get("message"):
            return {"status": "failed", "message": error["message"]}
        return {"status": "pending", "message": "尚未发现需要迁移的旧配置"}

    def migrate_legacy_settings(self, settings_path, *, remove_source=False):
        settings_path = Path(settings_path)
        if repository.get_app_setting(self.db_path, LEGACY_MIGRATION_KEY) == LEGACY_MIGRATION_VERSION:
            if remove_source and settings_path.exists():
                settings_path.unlink()
            return False
        if not settings_path.exists():
            repository.set_app_setting(
                self.db_path, LEGACY_MIGRATION_KEY, LEGACY_MIGRATION_VERSION, "integer"
            )
            return False
        try:
            source_text = settings_path.read_text(encoding="utf-8-sig")
            source_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
            previous_error = repository.get_app_setting(
                self.db_path, LEGACY_MIGRATION_ERROR_KEY, {}
            )
            if (
                isinstance(previous_error, dict)
                and previous_error.get("sourceHash") == source_hash
            ):
                return False
            settings = json.loads(source_text)
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("旧 settings.json 无法读取，未执行数据库迁移") from exc
        if not isinstance(settings, dict):
            raise RuntimeError("旧 settings.json 格式无效，未执行数据库迁移")

        try:
            self.apply_legacy_settings(settings)
        except (ValueError, RuntimeError) as exc:
            repository.set_app_setting(
                self.db_path,
                LEGACY_MIGRATION_ERROR_KEY,
                {"message": str(exc), "sourceHash": source_hash},
            )
            return False
        repository.set_app_setting(
            self.db_path, LEGACY_MIGRATION_KEY, LEGACY_MIGRATION_VERSION, "integer"
        )
        if remove_source:
            settings_path.unlink()
        return True
