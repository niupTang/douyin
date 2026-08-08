import json
import urllib.error
import urllib.request


def get_hermes_settings(settings=None):
    settings = settings or {}
    hermes = settings.get("hermes") if isinstance(settings.get("hermes"), dict) else {}
    return {
        "gatewayUrl": str(hermes.get("gatewayUrl") or "http://127.0.0.1:8642").rstrip("/"),
        "apiKey": str(hermes.get("apiKey") or ""),
        "timeout": max(10, min(int(hermes.get("timeout") or 300), 1800)),
    }


def public_hermes_settings(settings=None):
    hermes = get_hermes_settings(settings)
    return {
        "gatewayUrl": hermes["gatewayUrl"],
        "apiKeyConfigured": bool(hermes["apiKey"]),
        "timeout": hermes["timeout"],
    }


def hermes_request(path, method="GET", payload=None, timeout=None, settings=None):
    hermes = get_hermes_settings(settings)
    url = f"{hermes['gatewayUrl']}/{path.lstrip('/')}"
    headers = {"Accept": "application/json"}
    if hermes["apiKey"]:
        headers["Authorization"] = f"Bearer {hermes['apiKey']}"
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout or hermes["timeout"]) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[-1000:]
        if exc.code == 401:
            raise RuntimeError("Hermes Gateway 鉴权失败，请检查 API Key") from exc
        raise RuntimeError(f"Hermes Gateway 请求失败（HTTP {exc.code}）：{detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"无法连接 Hermes Gateway：{exc.reason}") from exc
