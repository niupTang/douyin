import io
from unittest.mock import Mock

import pytest
from flask import Flask

from backend_app.agent.tool_registry import ToolRegistry
from backend_app.common.database import connect, ensure_core_tables
from backend_app.common.tool_gateway import ToolExecutionGateway, ToolExecutionError
from backend_app.modules.ai_publish.repository import ensure_tables as ensure_publish_tables
from backend_app.modules.benchmark.repository import ensure_tables as ensure_benchmark_tables
from backend_app.modules.chat import repository
from backend_app.modules.chat.routes import create_chat_blueprint
from backend_app.modules.chat.service import ChatService
from backend_app.modules.chat.tools import register_chat_tools


class ImmediateExecutor:
    def submit(self, handler, *args):
        handler(*args)


@pytest.fixture
def workbench(tmp_path):
    db = tmp_path / 'database.db'
    ensure_core_tables(db)
    ensure_benchmark_tables(db)
    ensure_publish_tables(db)
    with connect(db) as conn:
        conn.execute("INSERT INTO user_info(id,type,filePath,userName,status) VALUES (1,3,'secret.json','太阳鸟',1)")
        conn.execute("INSERT INTO user_info(id,type,filePath,userName,status) VALUES (2,2,'other.json','视频号',1)")
        conn.execute("INSERT INTO user_info(id,type,filePath,userName,status) VALUES (3,3,'expired.json','过期账号',0)")
        conn.execute("INSERT INTO file_records(id,filename,file_path) VALUES (1,'test.mp4','test.mp4')")
        conn.execute("INSERT INTO douyin_benchmark_accounts(id,homepage_url,nickname) VALUES (1,'https://www.douyin.com/user/test','对标')")
    root = tmp_path / 'videoFile'
    root.mkdir()
    (root / 'test.mp4').write_bytes(b'test')
    runtime = Mock()
    runtime.submit.return_value = {'id': 'run-1', 'status': 'queued'}
    runtime.get_run.return_value = {'id': 'run-1', 'status': 'running'}
    runtime.get_events.return_value = [{'id': 1, 'event_type': 'tool_call', 'payload': {'tool': 'query_workbench_data'}}]
    gateway = ToolExecutionGateway()
    publisher = Mock(return_value={'record_id': 123, 'status': 'success'})
    gateway.register('publish_video', 'test', {'type': 'object', 'additionalProperties': True}, publisher, entitlement='publishing')
    service = ChatService(db, tmp_path, lambda: runtime, gateway)
    executor = service.executor
    service.executor = ImmediateExecutor()
    conversation = repository.create_conversation(db)['id']
    app = Flask(__name__)
    app.register_blueprint(create_chat_blueprint(service))
    yield service, conversation, runtime, publisher, app.test_client()
    executor.shutdown()


def publish_payload(**changes):
    return {'confirmed': True, 'request_id': 'a' * 32, 'title': '实战案例',
            'account_ids': [1], 'material_ids': [1], 'tags': ['AI'], **changes}


def test_send_persists_and_restores_real_run_output(workbench):
    service, cid, runtime, _, client = workbench
    response = client.post(f'/api/chat/conversations/{cid}/messages', json={'prompt': '查询账号'})
    assert response.status_code == 202
    assert len(response.json['data']) == 2
    assert response.json['data'][-1]['events'][0]['payload']['tool'] == 'query_workbench_data'
    runtime.get_run.return_value = {'status': 'succeeded', 'output': {'content': '查到 3 个账号'}}
    restored = service.get_messages(cid)
    assert restored[-1]['content'] == '查到 3 个账号'
    assert repository.messages(service.db_path, cid)[-1]['status'] == 'succeeded'
    service.send(cid, '其中有几个抖音账号？')
    args = runtime.submit.call_args.args
    assert args[0] == 'piOperations'
    assert '查到 3 个账号' in args[1]['prompt']
    assert repository.conversations(service.db_path)[0]['title'] == '查询账号'


def test_busy_conversation_rejects_second_run_and_can_cancel(workbench):
    service, cid, runtime, _, client = workbench
    service.send(cid, '同步对标')
    response = client.post(f'/api/chat/conversations/{cid}/messages', json={'prompt': '再同步一次'})
    assert response.status_code == 400
    assert runtime.submit.call_count == 1
    client.post(f'/api/chat/conversations/{cid}/cancel')
    runtime.cancel.assert_called_once_with('run-1')


def test_failed_run_and_missing_conversation(workbench):
    service, cid, runtime, _, client = workbench
    service.send(cid, '查询')
    runtime.get_run.return_value = {'status': 'failed', 'error_message': '尚未配置模型'}
    assert service.get_messages(cid)[-1]['content'] == '尚未配置模型'
    assert client.get('/api/chat/conversations/missing/messages').status_code == 404
    assert client.post(f'/api/chat/conversations/{cid}/messages', json={'prompt': ' '}).status_code == 400


def test_missing_run_does_not_leave_conversation_busy_forever(workbench):
    service, cid, runtime, _, _ = workbench
    service.send(cid, '查询')
    runtime.get_run.return_value = None
    assert service.get_messages(cid)[-1]['status'] == 'interrupted'
    service.send(cid, '重新查询')
    assert runtime.submit.call_count == 2


def test_runtime_submit_error_is_saved_as_failed_message(workbench):
    service, cid, runtime, _, _ = workbench
    runtime.submit.side_effect = RuntimeError('模型不可用')
    with pytest.raises(RuntimeError, match='模型不可用'):
        service.send(cid, '查询')
    assert repository.messages(service.db_path, cid)[-1]['status'] == 'failed'


def test_upload_stays_in_material_directory_and_conversation(workbench):
    service, cid, _, _, client = workbench
    response = client.post(f'/api/chat/conversations/{cid}/upload',
                           data={'file': (io.BytesIO(b'video'), '../../sample.mp4')})
    assert response.status_code == 201
    assert response.json['data']['filename'] == 'sample.mp4'
    item = repository.messages(service.db_path, cid)[-1]
    assert item['kind'] == 'upload'
    with connect(service.db_path) as conn:
        row = conn.execute('SELECT file_path FROM file_records WHERE id=?', (response.json['data']['material_id'],)).fetchone()
    assert (service.base_dir / 'videoFile' / row['file_path']).is_file()
    assert client.post(f'/api/chat/conversations/{cid}/upload',
                       data={'file': (io.BytesIO(b'x'), 'run.exe')}).status_code == 400


@pytest.mark.parametrize('changes', [
    {'confirmed': False}, {'account_ids': [1, 2]}, {'account_ids': [3]},
    {'material_ids': [999]}, {'title': ''}, {'request_id': 'invalid'},
    {'account_ids': [True]}, {'tags': 'AI'},
])
def test_publish_rejects_unconfirmed_or_invalid_targets(workbench, changes):
    service, cid, _, publisher, client = workbench
    response = client.post(f'/api/chat/conversations/{cid}/publish', json=publish_payload(**changes))
    assert response.status_code == 400
    publisher.assert_not_called()


def test_confirmed_publish_is_idempotent_and_uses_database_paths(workbench):
    service, cid, _, publisher, client = workbench
    for _ in range(2):
        response = client.post(f'/api/chat/conversations/{cid}/publish', json=publish_payload())
        assert response.status_code == 202
    publisher.assert_called_once_with(platform_type=3, title='实战案例', tags=['AI'],
                                      file_list=['test.mp4'], account_list=['secret.json'])
    items = service.get_messages(cid)
    assert len(items) == 1 and items[0]['status'] == 'succeeded'
    assert 'secret.json' not in items[0]['content']


def test_publish_denied_by_gateway_is_visible_and_not_executed(workbench):
    service, cid, _, publisher, _ = workbench
    def deny(tool, context):
        assert context.source == 'chat-confirmed'
        raise ToolExecutionError('DENIED', '没有发布权限', 403)
    service.gateway.authorize = deny
    service.publish(cid, publish_payload())
    publisher.assert_not_called()
    assert service.get_messages(cid)[-1]['status'] == 'failed'
    assert '没有发布权限' in service.get_messages(cid)[-1]['content']


def test_publish_rejects_file_outside_material_root(workbench):
    service, cid, _, publisher, _ = workbench
    outside = service.base_dir / 'outside.mp4'
    outside.write_bytes(b'video')
    with connect(service.db_path) as conn:
        conn.execute("UPDATE file_records SET file_path='../outside.mp4' WHERE id=1")
    with pytest.raises(ValueError, match='路径'):
        service.publish(cid, publish_payload())
    publisher.assert_not_called()


def test_chat_tools_read_only_columns_and_sync_through_gateway(workbench):
    service, _, _, _, _ = workbench
    registry = ToolRegistry(service.gateway)
    collect = Mock(return_value={'synced': 3})
    service.gateway.register('collect_douyin_account', 'test', {'type': 'object', 'additionalProperties': True}, collect)
    register_chat_tools(registry, service.db_path)
    result = registry.execute('query_workbench_data', {'entity': 'accounts'})
    assert len(result['items']) == 3
    assert 'filePath' not in result['items'][0]
    assert registry.execute('sync_benchmark_account', {'account_id': 1}) == {'synced': 3}
    collect.assert_called_once_with(homepage_url='https://www.douyin.com/user/test', max_videos=20)
    with pytest.raises(ToolExecutionError):
        registry.execute('publish_video', {})


def test_options_do_not_reveal_account_cookie_paths(workbench):
    service, _, _, _, client = workbench
    response = client.get('/api/chat/options')
    assert response.status_code == 200
    assert 'secret.json' not in response.get_data(as_text=True)
    assert response.json['data']['materials'][0]['id'] == 1


def test_video_links_use_stored_urls_and_report_missing_records(workbench):
    service, _, _, _, _ = workbench
    with connect(service.db_path) as conn:
        conn.execute("""INSERT INTO douyin_benchmark_videos(id,account_id,title,video_url)
            VALUES (123,1,'Codex 实战','https://www.douyin.com/video/987654321')""")
    registry = ToolRegistry(service.gateway)
    register_chat_tools(registry, service.db_path)
    result = registry.execute('get_video_links', {'video_ids': [123, 999]})
    assert result['items'] == [{'id': 123, 'title': 'Codex 实战',
                                'video_url': 'https://www.douyin.com/video/987654321'}]
    assert result['missing_ids'] == [999]
    assert registry.execute('get_video_links', {'video_ids': [123], 'source': 'publish'})['items'] == []
