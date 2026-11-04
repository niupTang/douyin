from flask import Flask

from backend_app.agent.runtime import AgentRuntime
from backend_app.agent.secret_store import MemoryMasterKeyProvider, SecretStore
from backend_app.agent.tool_registry import ToolRegistry
from backend_app.modules.agent_runs.routes import create_agent_runs_blueprint
from backend_app.modules.ai_settings import AiSettingsService
from backend_app.modules.ai_settings.routes import create_ai_settings_blueprint


class TextAdapter:
    def complete(self, messages, *, tools=None, timeout=None):
        return {"content": '{"result":"OK"}'}


def configured_runtime(tmp_path):
    service = AiSettingsService(
        tmp_path / "database.db",
        secret_store=SecretStore(MemoryMasterKeyProvider()),
    )
    provider = service.save_provider(
        {
            "id": "provider",
            "name": "Mock",
            "provider_type": "openai_compatible",
            "base_url": "https://example.invalid",
            "capabilities": {"tools": True},
        },
        "provider",
    )
    profile = service.save_model_profile(
        {
            "id": "model",
            "provider_id": provider["id"],
            "name": "Mock model",
            "model_name": "mock",
        },
        "model",
    )
    service.save_agent_profile(
        {
            "agent_key": "test-agent",
            "name": "Test agent",
            "execution_mode": "structured",
            "primary_model_profile_id": profile["id"],
        },
        "test-agent",
    )
    runtime = AgentRuntime(
        service.db_path,
        settings_service=service,
        tool_registry=ToolRegistry(),
        adapter_factory=lambda _route: TextAdapter(),
    )
    return service, runtime


def test_agent_run_routes_create_and_read_run(tmp_path):
    _service, runtime = configured_runtime(tmp_path)
    app = Flask(__name__)
    app.register_blueprint(create_agent_runs_blueprint(lambda: runtime))
    client = app.test_client()
    try:
        created = client.post("/api/agents/test-agent/runs", json={"prompt": "test"})
        run_id = created.get_json()["data"]["id"]
        runtime.executor.shutdown(wait=True)
        read = client.get(f"/api/agent-runs/{run_id}")
    finally:
        runtime.shutdown(wait=False)

    assert created.status_code == 202
    assert read.status_code == 200
    assert read.get_json()["data"]["status"] == "succeeded"


def test_provider_api_never_returns_secret(tmp_path):
    service = AiSettingsService(
        tmp_path / "database.db",
        secret_store=SecretStore(MemoryMasterKeyProvider()),
    )
    app = Flask(__name__)
    app.register_blueprint(create_ai_settings_blueprint(lambda: service))
    client = app.test_client()

    created = client.post(
        "/api/ai/providers",
        json={
            "id": "provider",
            "name": "Gateway",
            "providerType": "openai_compatible",
            "baseUrl": "https://example.invalid",
        },
    )
    saved = client.put("/api/ai/providers/provider/credential", json={"apiKey": "sk-private"})
    listed = client.get("/api/ai/providers")

    assert created.status_code == 200
    assert saved.status_code == 200
    assert b"sk-private" not in listed.data
    assert listed.get_json()["data"][0]["credentialConfigured"] is True


def test_provider_with_bound_models_cannot_be_deleted(tmp_path):
    service = AiSettingsService(
        tmp_path / "database.db",
        secret_store=SecretStore(MemoryMasterKeyProvider()),
    )
    provider = service.save_provider(
        {
            "id": "provider",
            "name": "Gateway",
            "providerType": "openai_compatible",
            "baseUrl": "https://example.invalid",
        },
        "provider",
    )
    service.save_model_profile(
        {
            "id": "model",
            "providerId": provider["id"],
            "name": "Model",
            "modelName": "model-name",
        },
        "model",
    )
    app = Flask(__name__)
    app.register_blueprint(create_ai_settings_blueprint(lambda: service))

    response = app.test_client().delete("/api/ai/providers/provider")

    assert response.status_code == 409
    assert response.get_json()["message"] == "Provider 已被模型使用，请先调整或删除相关模型"
