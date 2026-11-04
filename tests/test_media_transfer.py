import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from backend_app.modules.idea_radar import media, media_transfer


def response(data=b'abcd', status=206, content_range='bytes 0-3/8', **headers):
    item = Mock()
    item.status = status
    item.headers = {'content-type': 'video/mp4', **headers}
    if content_range:
        item.headers['content-range'] = content_range
    item.body = AsyncMock(return_value=data)
    item.dispose = AsyncMock()
    return item


@pytest.fixture(autouse=True)
def no_retry_wait(monkeypatch):
    monkeypatch.setattr(media_transfer.asyncio, 'sleep', AsyncMock())


def run_download(tmp_path, replies, urls=None):
    client = Mock(get=AsyncMock(side_effect=replies))
    output = tmp_path / 'source.mp4'
    result = asyncio.run(media_transfer.download_media_candidates(
        client, urls or ['https://cdn.example/video'], 'https://www.douyin.com/video/123',
        output, chunk_size=4,
    ))
    return result, client


def test_reset_resumes_same_chunk_without_duplicate_bytes(tmp_path):
    first = response()
    final = response(b'efgh', content_range='bytes 4-7/8')
    result, client = run_download(tmp_path, [first, ConnectionResetError('ECONNRESET'), final])
    assert result.read_bytes() == b'abcdefgh'
    assert [call.kwargs['headers']['Range'] for call in client.get.call_args_list] == [
        'bytes=0-3', 'bytes=4-7', 'bytes=4-7',
    ]
    assert all(call.kwargs['max_retries'] == 2 for call in client.get.call_args_list)
    first.dispose.assert_awaited_once()
    final.dispose.assert_awaited_once()
    assert not result.with_name('source.mp4.part').exists()


def test_reset_while_reading_200_body_is_retried(tmp_path):
    broken = response(status=200, content_range=None)
    broken.body.side_effect = ConnectionResetError('ECONNRESET')
    result, _ = run_download(tmp_path, [broken, response(b'complete', 200, None, **{'content-length': '8'})])
    assert result.read_bytes() == b'complete'
    broken.dispose.assert_awaited_once()


def test_partial_transfer_switches_url_and_restarts_cleanly(tmp_path):
    denied = response(status=403)
    result, client = run_download(tmp_path, [response(), denied, response(b'new!', 200, None)],
                                  ['https://cdn.example/old', 'https://cdn.example/new'])
    assert result.read_bytes() == b'new!'
    assert [call.args[0] for call in client.get.call_args_list] == [
        'https://cdn.example/old', 'https://cdn.example/old', 'https://cdn.example/new',
    ]
    denied.dispose.assert_awaited_once()


def test_ignored_range_replaces_partial_file_with_complete_body(tmp_path):
    result, _ = run_download(tmp_path, [response(), response(b'abcdefgh', 200, None, **{'content-length': '8'})])
    assert result.read_bytes() == b'abcdefgh'


@pytest.mark.parametrize('item', [
    response(b'ab', content_range='bytes 0-3/8'),
    response(b'abcd', content_range='bytes 4-7/8'),
    response(b'abcd', status=200, content_range=None, **{'content-length': '8'}),
    response(b'<html>', status=200, content_range=None, **{'content-type': 'text/html'}),
])
def test_corrupt_responses_never_replace_existing_output(tmp_path, item):
    output = tmp_path / 'source.mp4'
    output.write_bytes(b'previous complete file')
    client = Mock(get=AsyncMock(return_value=item))
    with pytest.raises(media_transfer.MediaTransferError):
        asyncio.run(media_transfer.download_media_candidates(
            client, ['https://cdn.example/video'], 'https://www.douyin.com/video/123', output, chunk_size=4,
        ))
    assert output.read_bytes() == b'previous complete file'
    assert not output.with_name('source.mp4.part').exists()
    assert client.get.await_count == 3


def test_exhausted_reset_retries_are_bounded_and_do_not_leave_partial_file(tmp_path):
    client = Mock(get=AsyncMock(side_effect=ConnectionResetError('ECONNRESET\nCall log: signed-secret-url')))
    output = tmp_path / 'source.mp4'
    with pytest.raises(media_transfer.MediaTransferError, match='ECONNRESET') as error:
        asyncio.run(media_transfer.download_media_candidates(client, ['https://cdn.example/video'], '', output))
    assert client.get.await_count == 3
    assert 'signed-secret-url' not in str(error.value)
    assert not output.exists() and not output.with_name('source.mp4.part').exists()


def test_candidates_ignore_blob_and_duplicate_urls():
    assert media_transfer.media_candidates('blob:browser-source', [
        'https://cdn.example/a', 'https://cdn.example/b', 'https://cdn.example/a', 'data:garbage'
    ]) == ['https://cdn.example/a']


def test_strategy_refreshes_expired_address_and_removes_listener(tmp_path, monkeypatch):
    page = Mock(goto=AsyncMock(), reload=AsyncMock(), wait_for_timeout=AsyncMock(),
                evaluate=AsyncMock(side_effect=['https://cdn.example/expired', 'https://cdn.example/fresh']))
    transfer = AsyncMock(side_effect=[media_transfer.MediaTransferError('expired'), tmp_path / 'source.mp4'])
    monkeypatch.setattr(media_transfer, 'download_media_candidates', transfer)
    progress = Mock()
    result = asyncio.run(media.DouyinMediaDownloadStrategy().execute(Mock(), page, {
        'video_url': 'https://www.douyin.com/video/123', 'output_path': tmp_path / 'source.mp4',
        'progress_callback': progress,
    }))
    assert result == tmp_path / 'source.mp4'
    assert transfer.await_count == 2
    assert transfer.call_args_list[1].args[1] == ['https://cdn.example/fresh']
    page.reload.assert_awaited_once()
    page.remove_listener.assert_called_once()
    assert progress.call_args.args == (100, '备用方式下载完成')


def test_strategy_failure_removes_response_listener(tmp_path, monkeypatch):
    page = Mock(goto=AsyncMock(side_effect=RuntimeError('page failure')))
    with pytest.raises(RuntimeError, match='page failure'):
        asyncio.run(media.DouyinMediaDownloadStrategy().execute(Mock(), page, {
            'video_url': 'https://www.douyin.com/video/123', 'output_path': tmp_path / 'source.mp4',
            'progress_callback': None,
        }))
    page.remove_listener.assert_called_once()


def test_candidates_only_switch_cdn_hosts_for_the_same_video():
    assert media_transfer.media_candidates('https://first.example/video/target/', [
        'https://second.example/video/target/?token=fresh',
        'https://second.example/video/recommendation/',
    ]) == ['https://first.example/video/target/', 'https://second.example/video/target/?token=fresh']


def test_play_endpoints_with_different_video_ids_are_not_alternates():
    source = 'https://www.douyin.com/aweme/v1/play/?video_id=target'
    assert media_transfer.media_candidates(source, [
        'https://www.douyin.com/aweme/v1/play/?video_id=recommendation',
    ]) == [source]
