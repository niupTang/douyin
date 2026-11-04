class AgentRuntimeError(RuntimeError):
    code = "agent_runtime_error"


class AgentConfigurationError(AgentRuntimeError):
    code = "agent_configuration_error"


class ProviderError(AgentRuntimeError):
    code = "provider_error"


class ProviderAuthenticationError(ProviderError):
    code = "provider_authentication_error"


class ProviderUnavailableError(ProviderError):
    code = "provider_unavailable"


class ProviderRateLimitError(ProviderError):
    code = "provider_rate_limit"


class ProviderResponseError(ProviderError):
    code = "provider_response_error"


class ModelCapabilityError(AgentRuntimeError):
    code = "model_capability_error"


class AgentCancelledError(AgentRuntimeError):
    code = "agent_cancelled"
