import re
import uuid


def normalize_agent_model(payload, existing_id=None):
    name = re.sub(r"\s+", " ", str(payload.get("name") or "")).strip()
    provider = str(payload.get("provider") or "").strip()
    model = str(payload.get("model") or "").strip()
    if not name or not provider or not model:
        raise ValueError("名称、Provider 和 Model 均不能为空")
    reasoning = str(payload.get("reasoningEffort") or "").strip().lower()
    if reasoning not in {"", "low", "medium", "high"}:
        raise ValueError("推理强度只能是 low、medium 或 high")
    service_tier = str(payload.get("serviceTier") or "").strip()
    return {
        "id": existing_id or str(payload.get("id") or uuid.uuid4().hex),
        "name": name,
        "provider": provider,
        "model": model,
        "reasoningEffort": reasoning,
        "serviceTier": service_tier,
        "enabled": bool(payload.get("enabled", True)),
    }


def get_agent_models(settings=None):
    settings = settings or {}
    models = settings.get("agentModels")
    return models if isinstance(models, list) else []


def get_task_agent_model(task_name="viralAnalysis", settings=None):
    settings = settings or {}
    task_models = settings.get("taskModels") if isinstance(settings.get("taskModels"), dict) else {}
    selected_id = task_models.get(task_name)
    models = get_agent_models(settings)
    selected = next(
        (item for item in models if item.get("id") == selected_id and item.get("enabled", True)), None
    )
    if not selected:
        selected = next((item for item in models if item.get("enabled", True)), None)
    if not selected:
        raise RuntimeError("尚未配置可用的 Agent 模型，请先前往 Agent 模型设置")
    return selected
