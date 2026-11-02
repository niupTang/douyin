import time
import inspect
from unittest.mock import Mock
from unittest.mock import AsyncMock

import pytest

from backend_app.modules.benchmark.discovery import CandidateDiscovery, connect
from backend_app.modules.benchmark import repository


def make_service(tmp_path, *, fail=False):
    db = tmp_path / 'discovery.db'
    discover = AsyncMock(return_value=[{
        'homepage_url': 'https://www.douyin.com/user/test-author',
        'nickname': '候选作者', 'source_keyword': 'Codex',
    }])
    profile = {
        'homepage_url': 'https://www.douyin.com/user/test-author',
        'nickname': '候选作者', 'bio': '分享自动化案例',
        'videos': [{'video_url': 'https://www.douyin.com/video/123', 'title': 'Codex 实战演示', 'like_count': '100'}],
    }
    inspect_account = AsyncMock(side_effect=RuntimeError('验证码') if fail else None, return_value=profile)
    return CandidateDiscovery(lambda: db, discover, inspect_account), db


def wait(service, task_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        task = service.get(task_id)
        if task['status'] not in ('queued', 'running'):
            return task
        time.sleep(0.01)
    pytest.fail('discovery did not finish')


def test_candidate_search_reads_works_without_adding_accounts(tmp_path):
    service, db = make_service(tmp_path)
    task = wait(service, service.start(['Codex'], 5, 10, None)['id'])
    assert task['status'] == 'completed'
    assert task['candidates'][0]['status'] == 'ready'
    assert len(task['candidates'][0]['videos']) == 1
    assert repository.list_accounts(db) == []
    service.inspect_account.assert_awaited_once_with(
        'https://www.douyin.com/user/test-author', cookie_file=None, max_videos=10)


def test_import_uses_snapshot_and_repeated_click_does_not_duplicate(tmp_path):
    service, db = make_service(tmp_path)
    task = wait(service, service.start(['Codex'], 5, 10, None)['id'])
    candidate = task['candidates'][0]
    result = service.import_candidate(task['id'], candidate['id'])
    repeated = service.import_candidate(task['id'], candidate['id'])
    assert result['id'] == repeated['id'] and repeated['alreadyImported']
    assert len(repository.list_accounts(db)) == 1
    assert len(repository.list_videos(db, result['id'])) == 1
    assert service.inspect_account.await_count == 1
    assert service.get(task['id'])['summary']['imported'] == 1


def test_failed_inspection_cannot_enter_library(tmp_path):
    service, db = make_service(tmp_path, fail=True)
    task = wait(service, service.start(['Codex'], 5, 10, None)['id'])
    candidate = task['candidates'][0]
    assert candidate['status'] == 'failed' and '验证码' in candidate['error']
    with pytest.raises(ValueError):
        service.import_candidate(task['id'], candidate['id'])
    assert repository.list_accounts(db) == []


def test_import_rolls_back_account_and_works_on_save_failure(tmp_path, monkeypatch):
    service, db = make_service(tmp_path)
    task = wait(service, service.start(['Codex'], 5, 10, None)['id'])
    candidate = task['candidates'][0]

    def fail_save(db_path, account_id, profile, *, connection):
        connection.execute('UPDATE douyin_benchmark_accounts SET nickname=? WHERE id=?', ('partial', account_id))
        raise RuntimeError('storage failure')

    monkeypatch.setattr(repository, 'save_sync', fail_save)
    with pytest.raises(RuntimeError):
        service.import_candidate(task['id'], candidate['id'])
    assert repository.list_accounts(db) == []
    assert service.get(task['id'])['candidates'][0]['status'] == 'ready'


def test_saved_candidates_survive_a_new_service_instance(tmp_path):
    service, db = make_service(tmp_path)
    task = wait(service, service.start(['Codex'], 5, 10, None)['id'])
    restored = CandidateDiscovery(lambda: db, AsyncMock(), AsyncMock())
    assert restored.get(task['id'])['candidates'][0]['videos'] == task['candidates'][0]['videos']
    assert repository.list_accounts(db) == []


def test_empty_results_report_error_instead_of_silent_success(tmp_path):
    service, db = make_service(tmp_path)
    service.discover.return_value = []
    task = wait(service, service.start(['Codex'], 5, 10, None)['id'])
    assert task['status'] == 'failed' and '未找到' in task['error']
    assert repository.list_accounts(db) == []


def test_candidate_from_another_task_cannot_be_imported(tmp_path):
    service, _ = make_service(tmp_path)
    task = wait(service, service.start(['Codex'], 5, 10, None)['id'])
    with pytest.raises(LookupError):
        service.import_candidate('another-task', task['candidates'][0]['id'])


@pytest.mark.parametrize('path,payload', [
    ('/benchmark/douyin/discovery-tasks', {'keywords': 'Codex', 'limit': 5, 'maxVideos': 10}),
    ('/benchmark/douyin/auto-discover', {'keyword': 'Codex', 'limit': 5, 'max_videos': 10}),
])
def test_both_discovery_routes_only_start_candidates(monkeypatch, path, payload):
    from flask import Flask
    from backend_app.modules.benchmark import routes

    discovery = Mock()
    discovery.start.return_value = {'id': 'candidate-task', 'status': 'queued', 'candidates': []}
    monkeypatch.setattr(routes, 'CandidateDiscovery', Mock(return_value=discovery))
    dependencies = {name: Mock() for name, parameter in inspect.signature(routes.create_benchmark_blueprint).parameters.items()
                    if parameter.default is inspect.Parameter.empty}
    dependencies['parse_keywords_payload'].return_value = ['Codex']
    dependencies['latest_douyin_cookie_file'].return_value = 'selected-account.json'
    app = Flask(__name__)
    app.register_blueprint(routes.create_benchmark_blueprint(**dependencies))
    response = app.test_client().post(path, json=payload)
    assert response.status_code == 202
    assert response.json['data']['id'] == 'candidate-task'
    discovery.start.assert_called_once_with(['Codex'], 5, 10, 'selected-account.json')
    dependencies['sync_one_douyin_benchmark'].assert_not_called()
    dependencies['upsert_douyin_benchmark'].assert_not_called()
    dependencies['save_douyin_benchmark_sync'].assert_not_called()
