import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
from flask import Flask

from backend_app.agent.tool_registry import ToolRegistry
from backend_app.common.tool_gateway import (
    ToolExecutionContext, ToolExecutionError, ToolExecutionGateway, execution_context,
)
from backend_app.modules.mcp_server.handlers import create_mcp_handlers
from backend_app.modules.mcp_server.routes import create_mcp_blueprint
from backend_app.modules.tool_execution.policy import create_application_gateway


@pytest.fixture
def sample_tool():
    handler = Mock(return_value={"accepted": True})
    gateway = ToolExecutionGateway()
    gateway.register("sample", "sample", {
        "type": "object", "required": ["count"],
        "properties": {
            "count": {"type": "integer", "minimum": 1, "maximum": 5},
            "items": {"type": "array", "items": {"type": "string"}},
        },
    }, handler)
    return gateway, handler


@pytest.mark.parametrize("arguments", [
    {}, {"count": True}, {"count": "2"}, {"count": 0}, {"count": 6},
    {"count": 1, "extra": True}, {"count": 1, "items": [123]},
    [], False, "not-json", '{"count": NaN}', {"count": float("inf")},
])
def test_invalid_arguments_never_reach_business_handler(sample_tool, arguments):
    gateway, handler = sample_tool
    with pytest.raises(ToolExecutionError) as error:
        gateway.execute("sample", arguments)
    assert error.value.code == "TOOL_ARGUMENTS_INVALID"
    assert error.value.invocation_id
    handler.assert_not_called()


def test_json_and_object_calls_have_same_validation_and_result(sample_tool):
    gateway, handler = sample_tool
    assert gateway.execute("sample", '{"count":2}') == gateway.execute("sample", {"count": 2})
    assert handler.call_count == 2


def make_mcp(gateway, publish=None):
    return create_mcp_handlers(
        None, None, None, None, None, None, None, None,
        lambda limit: [{"id": 7, "title": "test", "play_count": 1}],
        publish or Mock(), gateway=gateway,
    )


def test_mcp_checks_publish_entitlement_before_side_effect():
    license_registry = Mock()
    license_registry.require.return_value = (False, {"reasonCode": "DENIED", "message": "denied"})
    gateway = create_application_gateway(license_registry, Mock())
    publish = Mock()
    handlers = make_mcp(gateway, publish)
    with pytest.raises(ToolExecutionError) as error:
        handlers()["publish_video"]({
            "platform_type": 3, "file_list": ["video.mp4"],
            "account_list": ["account"], "title": "title",
        })
    assert error.value.status == 403
    license_registry.require.assert_called_once_with("publishing")
    publish.assert_not_called()


def test_agent_view_cannot_invoke_mcp_only_tools():
    gateway = ToolExecutionGateway()
    make_mcp(gateway)
    registry = ToolRegistry(gateway)
    registry.register("safe_read", "Read", {"type": "object"}, lambda: 1)
    with pytest.raises(ToolExecutionError) as error:
        registry.execute("publish_video", {})
    assert error.value.code == "TOOL_NOT_FOUND"
    assert [schema["function"]["name"] for schema in registry.schemas()] == ["safe_read"]


def test_mcp_http_preserves_result_and_returns_validation_errors():
    events = []
    gateway = ToolExecutionGateway(audit=lambda event, metadata: events.append((event, metadata)))
    handlers = make_mcp(gateway)
    app = Flask(__name__)
    app.register_blueprint(create_mcp_blueprint(handlers))
    client = app.test_client()
    response = client.post('/mcp/invoke', json={
        "name": "review_published_content", "arguments": {"limit": 5},
    })
    assert response.status_code == 200
    assert response.json["data"]["summary"]["total"] == 1
    assert events[-1][1]["source"] == "mcp"
    response = client.post('/mcp/invoke', json={
        "name": "analyze_benchmark_video", "arguments": {"video_id": 1, "force": "false"},
    })
    assert response.status_code == 400
    assert response.json["error_code"] == "TOOL_ARGUMENTS_INVALID"
    assert client.post('/mcp/invoke', json=[]).status_code == 400
    assert client.post('/mcp/invoke', json={"name": "publish_video", "arguments": []}).status_code == 400
    definition = next(tool for tool in client.get('/mcp/tools').json["data"]
                      if tool["name"] == "publish_video")
    assert definition["effect_type"] == "publish"
    assert definition["input_schema"]["additionalProperties"] is False


def test_audit_has_correlation_but_no_arguments_or_results():
    events = []
    gateway = ToolExecutionGateway(audit=lambda event, metadata: events.append((event, metadata)))
    gateway.register("read", "Read", {"type": "object", "properties": {"token": {"type": "string"}}},
                     lambda token: {"secret": token})

    def run(run_id):
        token = execution_context.set(ToolExecutionContext(source="agent", run_id=run_id))
        try:
            return gateway.execute("read", {"token": "private-value"})
        finally:
            execution_context.reset(token)

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(run, ["run-a", "run-b"]))
    completed = [item for event, item in events if event == "tool_succeeded"]
    assert {item["run_id"] for item in completed} == {"run-a", "run-b"}
    assert len({item["invocation_id"] for item in completed}) == 2
    assert "private-value" not in json.dumps(events)


def test_audit_failure_does_not_retry_or_hide_completed_write():
    gateway = ToolExecutionGateway(audit=Mock(side_effect=OSError("log unavailable")))
    handler = Mock(return_value={"saved": True})
    gateway.register("save", "Save", {"type": "object"}, handler, side_effect=True)
    assert gateway.execute("save", {}) == {"saved": True}
    handler.assert_called_once()


def test_business_errors_are_normalized_and_redacted():
    gateway = ToolExecutionGateway()
    gateway.register("fail", "Fail", {"type": "object"},
                     Mock(side_effect=RuntimeError("Authorization=secret-token")))
    with pytest.raises(ToolExecutionError) as error:
        gateway.execute("fail", {})
    assert error.value.code == "TOOL_EXECUTION_FAILED"
    assert "secret-token" not in str(error.value)


def test_application_agent_and_mcp_use_the_same_gateway():
    from sau_backend import agent_tool_registry, mcp_tool_handlers, tool_execution_gateway

    assert agent_tool_registry.gateway is tool_execution_gateway
    assert mcp_tool_handlers.gateway is tool_execution_gateway
    assert tool_execution_gateway.get("list_account_benchmark_videos") is not None
    assert tool_execution_gateway.get("list_benchmark_videos") is not None
    assert tool_execution_gateway.get("search_douyin_content").entitlement == "benchmarkCollect"
    assert tool_execution_gateway.get("publish_video").entitlement == "publishing"
