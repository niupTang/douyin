import json
import urllib.error
import urllib.request

from backend_app.agent.errors import (
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderUnavailableError,
)


class OpenAICompatibleProviderAdapter:
    def __init__(self, provider, model_profile, api_key=""):
        self.provider = provider
        self.model_profile = model_profile
        self.api_key = api_key

    def complete(self, messages, *, tools=None, timeout=None):
        payload = {
            "model": self.model_profile["model_name"],
            "stream": False,
            "messages": messages,
        }
        extra_options = self.model_profile.get("extra_options") or {}
        gateway_provider = extra_options.get("gateway_provider")
        if self.provider.get("provider_type") == "hermes" and gateway_provider not in {None, "", "gateway-default"}:
            payload["provider"] = gateway_provider
        model_options = dict(extra_options.get("model_options") or {})
        if self.model_profile.get("reasoning_effort"):
            model_options["reasoning_effort"] = self.model_profile["reasoning_effort"]
        if self.model_profile.get("service_tier"):
            model_options["service_tier"] = self.model_profile["service_tier"]
        if model_options:
            payload["model_options"] = model_options
        if self.model_profile.get("temperature") is not None:
            payload["temperature"] = self.model_profile["temperature"]
        if self.model_profile.get("max_tokens") is not None:
            payload["max_tokens"] = self.model_profile["max_tokens"]
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        data = self._request_json("chat/completions", payload=payload, timeout=timeout)
        choices = data.get("choices") if isinstance(data, dict) else None
        message = choices[0].get("message") if choices and isinstance(choices[0], dict) else None
        if not isinstance(message, dict):
            raise ProviderResponseError("模型服务没有返回有效消息")
        return message

    def check_connection(self):
        data = self._request_json("models", timeout=20)
        models = data.get("data") if isinstance(data, dict) else None
        if not isinstance(models, list):
            raise ProviderResponseError("模型服务没有返回有效的模型列表，请检查服务地址")
        return {"connected": True, "modelCount": len(models)}

    def _request_json(self, endpoint, *, payload=None, timeout=None):
        base_url = str(self.provider.get("base_url") or "").rstrip("/")
        api_url = base_url if base_url.endswith("/v1") else f"{base_url}/v1"

        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            f"{api_url}/{endpoint}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None,
            headers=headers,
            method="POST" if payload is not None else "GET",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout or self.provider.get("timeout_seconds") or 300,
            ) as response:
                data = json.loads(response.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[-1000:]
            if exc.code in {401, 403}:
                name = self.provider.get("name") or "当前 Provider"
                reason = "拒绝 API Key" if exc.code == 401 else "拒绝访问，请检查 API Key 权限及服务限制"
                raise ProviderAuthenticationError(
                    f"模型服务「{name}」{reason}（HTTP {exc.code}）。请到模型设置检查该 Provider 的服务地址和凭据。"
                ) from exc
            if exc.code == 429:
                raise ProviderRateLimitError("模型服务请求过于频繁，请稍后重试") from exc
            if exc.code >= 500:
                raise ProviderUnavailableError(f"模型服务暂时不可用（HTTP {exc.code}）") from exc
            raise ProviderResponseError(f"模型服务请求失败（HTTP {exc.code}）：{detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ProviderUnavailableError(f"无法连接模型服务：{getattr(exc, 'reason', exc)}") from exc
        except json.JSONDecodeError as exc:
            raise ProviderResponseError("模型服务返回了无效 JSON") from exc

        return data
