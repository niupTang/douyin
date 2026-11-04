import time

from backend_app.agent.errors import ProviderUnavailableError
from backend_app.agent.runtime import AgentRuntime
from backend_app.agent.secret_store import MemoryMasterKeyProvider, SecretStore
from backend_app.agent.tool_registry import ToolRegistry
from backend_app.modules.ai_settings import AiSettingsService


class FakeAdapter:
    def __init__(self, actions):
        self.actions = actions
        self.calls = 0

    def complete(self, messages, *, tools=None, timeout=None):
        action = self.actions[self.calls]
        self.calls += 1
        if isinstance(action, Exception):
            raise action
        return action


def configured_service(tmp_path, *, execution_mode="structured", fallback=False):
    service = AiSettingsService(
        tmp_path / "database.db",
        secret_store=SecretStore(MemoryMasterKeyProvider()),
    )
    provider = service.save_provider(
        {
            "id": "provider",
            "name": "Mock Provider",
            "provider_type": "openai_compatible",
            "base_url": "https://example.invalid",
            "timeout_seconds": 30,
            "capabilities": {"tools": True},
        },
        "provider",
    )
    primary = service.save_model_profile(
        {
            "id": "primary",
            "provider_id": provider["id"],
            "name": "Primary",
            "model_name": "primary-model",
        },
        "primary",
    )
    fallback_profile = None
    if fallback:
        fallback_profile = service.save_model_profile(
            {
                "id": "fallback",
                "provider_id": provider["id"],
                "name": "Fallback",
                "model_name": "fallback-model",
            },
            "fallback",
        )
    service.save_agent_profile(
        {
            "agent_key": "test-agent",
            "name": "Test Agent",
            "execution_mode": execution_mode,
            "primary_model_profile_id": primary["id"],
            "fallback_model_profile_id": fallback_profile["id"] if fallback_profile else None,
            "max_steps": 4,
        },
        "test-agent",
    )
    return service


def test_structured_runtime_repairs_one_invalid_json(tmp_path):
    service = configured_service(tmp_path)
    adapter = FakeAdapter(
        [
            {"content": "not json"},
            {"content": '{"result":"OK"}'},
        ]
    )
    runtime = AgentRuntime(
        service.db_path,
        settings_service=service,
        adapter_factory=lambda _route: adapter,
    )
    try:
        result = runtime.run_structured(
            "test-agent",
            "return ok",
            {"type": "object", "properties": {"result": {"type": "string"}}},
        )
    finally:
        runtime.shutdown()

    assert result == {"result": "OK"}
    assert adapter.calls == 2


def test_runtime_uses_fallback_only_for_provider_availability(tmp_path):
    service = configured_service(tmp_path, fallback=True)
    adapters = {
        "primary-model": FakeAdapter([ProviderUnavailableError("offline")]),
        "fallback-model": FakeAdapter([{"content": '{"result":"fallback"}'}]),
    }
    runtime = AgentRuntime(
        service.db_path,
        settings_service=service,
        adapter_factory=lambda route: adapters[route.model_profile["model_name"]],
    )
    try:
        result = runtime.run_structured("test-agent", "run", {"type": "object"})
    finally:
        runtime.shutdown()

    assert result == {"result": "fallback"}


def test_tool_agent_executes_registered_tool_and_persists_run(tmp_path):
    service = configured_service(tmp_path, execution_mode="tool_loop")
    registry = ToolRegistry()
    registry.register(
        "add_numbers",
        "Add two numbers",
        {
            "type": "object",
            "required": ["a", "b"],
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
        },
        lambda a, b: {"sum": a + b},
    )
    adapter = FakeAdapter(
        [
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {"name": "add_numbers", "arguments": '{"a":2,"b":3}'},
                    }
                ],
            },
            {"content": "结果是 5"},
        ]
    )
    runtime = AgentRuntime(
        service.db_path,
        settings_service=service,
        tool_registry=registry,
        adapter_factory=lambda _route: adapter,
    )
    try:
        run = runtime.submit("test-agent", {"prompt": "2+3 等于多少"})
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            saved = runtime.get_run(run["id"])
            if saved["status"] in {"succeeded", "failed"}:
                break
            time.sleep(0.02)
        events = runtime.get_events(run["id"])
    finally:
        runtime.shutdown()

    assert saved["status"] == "succeeded"
    assert saved["output"]["content"] == "结果是 5"
    assert [event["event_type"] for event in events] == [
        "run_started",
        "model_call",
        "tool_call",
        "tool_result",
        "model_call",
        "run_succeeded",
    ]
