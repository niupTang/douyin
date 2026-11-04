import asyncio
import inspect
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock

import pytest
from flask import Flask

from backend_app.modules.benchmark import operations, repository, routes, video_import


def detail(video_id='123'):
    return {'aweme_id': video_id, 'desc': '单条视频标题',
            'author': {'sec_uid': 'test-author', 'nickname': '作者'},
            'statistics': {'digg_count': 0, 'comment_count': 2},
            'video': {'cover': {'url_list': ['https://images.example/cover.jpg']}}}


@pytest.mark.parametrize('value,identity', [
    ('https://www.douyin.com/video/123?from=share', ('123', 'video')),
    ('https://www.douyin.com/note/456', ('456', 'note')),
    ('https://www.douyin.com/user/test?modal_id=123', ('123', 'video')),
    ('https://www.douyin.com/?vid=789', ('789', 'video')),
    ('https://www.douyin.com/user/test', None),
])
def test_video_identity(value, identity):
    assert video_import.video_identity(value) == identity


def test_share_text_extracts_short_link():
    assert video_import.extract_link('复制打开抖音，看作品 https://v.douyin.com/AbCd/，分享给你') == 'https://v.douyin.com/AbCd/'


@pytest.mark.parametrize('url', ['https://douyin.com.evil.test/video/123', 'https://notdouyin.com/video/123',
                                     'https://user@www.douyin.com/video/123', '没有链接'])
def test_invalid_links_are_rejected(url):
    with pytest.raises(ValueError):
        video_import.extract_link(url)


def test_detail_parser_selects_requested_video_not_recommendations():
    payload = {'recommended': [detail('999')], 'detail': detail()}
    selected = video_import.find_video_detail(payload, '123')
    profile = video_import.profile_from_detail(selected, '123')
    assert profile['homepage_url'] == 'https://www.douyin.com/user/test-author'
    assert len(profile['videos']) == 1
    assert profile['videos'][0]['like_count'] == 0
    assert profile['videos'][0]['video_url'] == 'https://www.douyin.com/video/123'
    assert video_import.find_video_detail(payload, '000') is None


def test_video_import_preserves_account_profile_and_deduplicates(tmp_path, monkeypatch):
    db = tmp_path / 'benchmark.db'
    account_id = repository.upsert_account(db, 'https://www.douyin.com/user/test-author', lambda value: value)
    repository.save_sync(db, account_id, {
        'nickname': '作者', 'followers_count': '10万', 'bio': '已有简介',
        'video_count': '100', 'videos': [{'video_url': 'https://www.douyin.com/video/999', 'title': '已有作品'}],
    })
    inspect_link = AsyncMock(return_value={'kind': 'video', 'profile': video_import.profile_from_detail(detail(), '123')})
    scrape = AsyncMock()
    monkeypatch.setattr(operations, 'inspect_shared_link', inspect_link)
    monkeypatch.setattr(operations, 'scrape_douyin_benchmark', scrape)
    service = operations.create_benchmark_operations(lambda: db, Mock(), Mock())
    for expected in ['inserted', 'updated']:
        result = service.sync_account('https://www.douyin.com/video/123', 'cookie.json')
        assert result['id'] == account_id
        assert result['sync'][expected] == 1
        assert result['input_type'] == 'video'
    scrape.assert_not_awaited()
    assert len(repository.list_videos(db, account_id)) == 2
    account = repository.list_accounts(db)[0]
    assert account['followers_count'] == '10万'
    assert account['bio'] == '已有简介'
    assert account['video_count'] == '100'


def test_homepage_import_keeps_existing_feed_sync(tmp_path, monkeypatch):
    db = tmp_path / 'benchmark.db'
    scrape = AsyncMock(return_value={'nickname': '作者', 'videos': []})
    inspect_link = AsyncMock()
    monkeypatch.setattr(operations, 'scrape_douyin_benchmark', scrape)
    monkeypatch.setattr(operations, 'inspect_shared_link', inspect_link)
    service = operations.create_benchmark_operations(lambda: db, Mock(), Mock())
    result = service.sync_account('https://www.douyin.com/user/test-author', None)
    assert result['input_type'] == 'profile'
    inspect_link.assert_not_awaited()
    assert scrape.await_count == 1


@pytest.mark.parametrize('resolved,embedded,expected', [
    ('https://www.douyin.com/video/123', [detail()], 'video'),
    ('https://www.douyin.com/user/test-author', [], 'profile'),
])
def test_short_links_resolve_in_browser(monkeypatch, resolved, embedded, expected):
    page = Mock()
    page.url = resolved
    page.goto = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.evaluate = AsyncMock(return_value=embedded)

    @asynccontextmanager
    async def session(_spec):
        yield Mock(), page

    monkeypatch.setattr(video_import, 'BrowserEngine', lambda **kwargs: Mock(session=session))
    monkeypatch.setattr(video_import, 'collection_browser_spec', lambda state: state)
    monkeypatch.setattr(video_import, 'resolve_storage_state', lambda state: state)
    monkeypatch.setattr(video_import, 'dismiss_douyin_login_popup', AsyncMock())
    result = asyncio.run(video_import.inspect_shared_link.__wrapped__('https://v.douyin.com/short/', None))
    assert result['kind'] == expected
    if expected == 'video':
        assert len(result['profile']['videos']) == 1
    page.remove_listener.assert_called_once()


@pytest.mark.parametrize('key', ['homepageUrl', 'homepage_url', 'url', 'link'])
def test_sync_route_accepts_video_links(key):
    dependencies = {name: Mock() for name, parameter in inspect.signature(routes.create_benchmark_blueprint).parameters.items()
                    if parameter.default is inspect.Parameter.empty}
    dependencies['sync_one_douyin_benchmark'].return_value = {'id': 1, 'sync': {'inserted': 1}, 'input_type': 'video'}
    app = Flask(__name__)
    app.register_blueprint(routes.create_benchmark_blueprint(**dependencies, candidate_discovery=Mock()))
    client = app.test_client()
    response = client.post('/benchmark/douyin/accounts', json={key: 'https://www.douyin.com/video/123'})
    assert response.status_code == 200
    assert response.json['data']['input_type'] == 'video'
    dependencies['sync_one_douyin_benchmark'].side_effect = ValueError('视频无法解析')
    failed = client.post('/benchmark/douyin/accounts', json={key: 'https://www.douyin.com/video/123'})
    assert failed.status_code == 400
    dependencies['upsert_douyin_benchmark'].assert_not_called()


def test_failed_single_video_save_rolls_back_new_author(tmp_path, monkeypatch):
    db = tmp_path / 'benchmark.db'
    def fail(*args, **kwargs):
        raise RuntimeError('disk failure')
    monkeypatch.setattr(repository, 'save_sync', fail)
    with pytest.raises(RuntimeError, match='disk failure'):
        repository.save_single_video(db, video_import.profile_from_detail(detail(), '123'))
    assert repository.list_accounts(db) == []


def test_dom_only_reimport_retains_existing_video_metrics(tmp_path):
    db = tmp_path / 'benchmark.db'
    profile = video_import.profile_from_detail(detail(), '123')
    result = repository.save_single_video(db, profile)
    repository.save_single_video(db, {
        'homepage_url': profile['homepage_url'],
        'videos': [{'video_url': profile['videos'][0]['video_url'], 'title': '更新标题'}],
    })
    video = repository.list_videos(db, result['id'])[0]
    assert video['comment_count'] == '2'
    assert video['like_count'] == '0'
    assert video['title'] == '更新标题'
