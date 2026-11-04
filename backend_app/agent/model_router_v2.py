from dataclasses import dataclass

from backend_app.agent.errors import AgentConfigurationError
from backend_app.modules.ai_settings import repository


@dataclass(frozen=True)
class ModelRoute:
    agent_profile: dict
    model_profile: dict
    provider: dict
    api_key: str


class ModelRouter:
    def __init__(self, db_path, settings_service):
        self.db_path = db_path
        self.settings_service = settings_service

    def resolve(self, agent_key, model_profile_id=None, fallback=False):
        agent_profile = repository.get_agent_profile(self.db_path, agent_key)
        if not agent_profile:
            raise AgentConfigurationError(f"Agent 尚未配置：{agent_key}")
        if not agent_profile.get("enabled"):
            raise AgentConfigurationError(f"Agent 已停用：{agent_key}")
        selected_id = model_profile_id
        if not selected_id:
            selected_id = (
                agent_profile.get("fallback_model_profile_id")
                if fallback
                else agent_profile.get("primary_model_profile_id")
            )
        if not selected_id:
            raise AgentConfigurationError(f"Agent 尚未绑定可用模型：{agent_key}")
        model_profile = repository.get_model_profile(self.db_path, selected_id)
        if not model_profile or not model_profile.get("enabled"):
            raise AgentConfigurationError("Agent 绑定的模型不存在或已停用")
        provider = repository.get_provider(self.db_path, model_profile["provider_id"])
        if not provider or not provider.get("enabled"):
            raise AgentConfigurationError("模型对应的 Provider 不存在或已停用")
        api_key = self.settings_service.get_credential_secret(provider["id"])
        return ModelRoute(agent_profile, model_profile, provider, api_key)
