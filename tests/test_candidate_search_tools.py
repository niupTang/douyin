from unittest.mock import Mock

import pytest
from flask import Flask

from backend_app.agent.tool_registry import ToolRegistry
from backend_app.common.tool_gateway import ToolExecutionGateway, ToolExecutionError
from backend_app.modules.mcp_server.handlers import create_mcp_handlers
from backend_app.modules.mcp_server.routes import create_mcp_blueprint
from backend_app.modules.tool_execution.search_tools import register_candidate_search_tools


def make_tools(authorize=None):
    discovery = Mock()
    discovery.start.return_value = {'id': 'search-123', 'status': 'queued'}
    discovery.get.return_value = {
        'id': 'search-123', 'status': 'completed', 'keywords': ['Codex'],
        'summary': {'found': 1, 'ready': 1},
        'candidates': [{'id': 'candidate-a', 'status': 'ready',
                        'videos': [{'title': str(i)} for i in range(10)]}],
    }
    gateway = ToolExecutionGateway(authorize=authorize)
    names = register_candidate_search_tools(gateway, discovery, lambda: 'account.json')
    agent = ToolRegistry(gateway)
    for name in names:
        agent.expose(name)
    mcp = create_mcp_handlers(*([None] * 10), gateway=gateway, extra_tool_names=names)
    return gateway, discovery, agent, mcp


def test_agent_can_start_and_read_the_same_search_as_mcp():
    gateway, discovery, agent, mcp = make_tools()
    started = agent.execute('search_benchmark_candidates', '{"keywords":"Codex，AI 自动化,Codex"}')
    discovery.start.assert_called_once_with(['Codex', 'AI 自动化'], 5, 10, 'account.json')
    assert started['task_id'] == 'search-123' and started['requires_manual_import']
    result = mcp()['get_benchmark_search']({'task_id': started['task_id']})
    assert result['review_page'] == '/#/benchmark-search?discovery_task_id=search-123'
    assert len(result['candidates'][0]['videos']) == 5
    assert result['candidates'][0]['videos_truncated']
    assert result['candidates'][0]['video_count_collected'] == 10
    discovery.import_candidate.assert_not_called()
    assert agent.gateway is mcp.gateway is gateway
    assert 'search_benchmark_candidates' in [tool['name'] for tool in mcp.describe_tools()]


@pytest.mark.parametrize('arguments', [
    {'keywords': []}, {'keywords': '   '}, {'keywords': ['Codex'], 'limit': 21},
    {'keywords': ['Codex'], 'max_videos': True}, {'keywords': ['Codex'], 'auto_import': True},
    {'keywords': ','.join(str(i) for i in range(21))},
])
def test_invalid_search_cannot_start_collection(arguments):
    gateway, discovery, _, _ = make_tools()
    with pytest.raises(ToolExecutionError):
        gateway.execute('search_benchmark_candidates', arguments)
    discovery.start.assert_not_called()


def test_permission_denial_prevents_search():
    def deny(tool, context):
        assert tool.entitlement == 'benchmarkCollect'
        raise ToolExecutionError('DENIED', 'no permission', 403)

    gateway, discovery, _, _ = make_tools(authorize=deny)
    with pytest.raises(ToolExecutionError) as error:
        gateway.execute('search_benchmark_candidates', {'keywords': ['Codex']})
    assert error.value.status == 403
    discovery.start.assert_not_called()


def test_mcp_http_search_can_be_called_as_tool_method():
    _, discovery, _, mcp = make_tools()
    app = Flask(__name__)
    app.register_blueprint(create_mcp_blueprint(mcp))
    result = app.test_client().post('/mcp/invoke', json={
        'name': 'search_benchmark_candidates', 'arguments': {'keywords': ['Codex'], 'limit': 3},
    })
    assert result.status_code == 200
    assert result.json['data']['task_id'] == 'search-123'
    discovery.start.assert_called_once_with(['Codex'], 3, 10, 'account.json')


def test_missing_search_returns_a_stable_404():
    gateway, discovery, _, _ = make_tools()
    discovery.get.return_value = None
    with pytest.raises(ToolExecutionError) as error:
        gateway.execute('get_benchmark_search', {'task_id': 'missing'})
    assert error.value.code == 'SEARCH_TASK_NOT_FOUND' and error.value.status == 404


def test_application_ui_agent_and_mcp_share_candidate_service():
    from sau_backend import app, candidate_discovery, agent_tool_registry, mcp_tool_handlers

    assert app.blueprints['benchmark'].candidate_discovery is candidate_discovery
    assert agent_tool_registry.gateway is mcp_tool_handlers.gateway
    assert 'search_benchmark_candidates' in [tool['function']['name'] for tool in agent_tool_registry.schemas()]
