"""Bounded, resumable CDN transfers using the browser's authenticated request context."""
import asyncio
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


class MediaTransferError(RuntimeError):
    pass


def media_candidates(current_src, captured):
    candidates = []
    for url in [current_src, *reversed(captured)]:
        if isinstance(url, str) and urlsplit(url).scheme in ('http', 'https') and url not in candidates:
            candidates.append(url)
    if not candidates:
        return []
    # Preloaded recommendation videos may share this page's network context.
    # Alternate CDN hosts must refer to the same immutable video object.
    def asset_key(url):
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        if query.get('video_id'):
            return ('video_id', query['video_id'][0])
        return ('path', parsed.path.rstrip('/').rsplit('/', 1)[-1])

    asset = asset_key(candidates[0])
    return [url for url in candidates if url == candidates[0] or (
        asset[1] and asset_key(url) == asset
    )][:5]


async def download_media_candidates(request_context, urls, referer, output_path,
                                    progress_callback=None, *, chunk_size=1024 * 1024, attempts=3):
    output = Path(output_path)
    part = output.with_name(output.name + '.part')
    last_error = None
    try:
        for url in urls:
            offset = 0
            total = None
            part.write_bytes(b'')
            while total is None or offset < total:
                chunk = None
                for attempt in range(attempts):
                    response = None
                    try:
                        response = await request_context.get(url, headers={
                            'Referer': referer, 'Origin': 'https://www.douyin.com',
                            'Accept-Encoding': 'identity',
                            'Range': f'bytes={offset}-{min(offset + chunk_size, total) - 1 if total else offset + chunk_size - 1}',
                        }, timeout=45000, max_retries=2)
                        if response.status not in (200, 206):
                            raise MediaTransferError(f'媒体服务器返回 HTTP {response.status}')
                        headers = {key.lower(): value for key, value in response.headers.items()}
                        content_type = headers.get('content-type', '').lower()
                        if content_type and not (content_type.startswith('video/') or 'octet-stream' in content_type):
                            raise MediaTransferError('媒体服务器未返回视频内容')
                        data = await response.body()
                        if not data:
                            raise MediaTransferError('媒体服务器返回空文件')
                        if response.status == 206:
                            match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', headers.get('content-range', ''))
                            if not match:
                                raise MediaTransferError('视频分段响应缺少有效的 Content-Range')
                            start, end, size = map(int, match.groups())
                            if start != offset or end < start or end >= size or len(data) != end - start + 1:
                                raise MediaTransferError('视频分段不完整或位置不匹配')
                            if total is not None and size != total:
                                raise MediaTransferError('传输中视频文件大小发生变化')
                            total = size
                            chunk = data
                        else:
                            # Some CDNs ignore Range and return the complete file.
                            expected = headers.get('content-length')
                            if expected and len(data) != int(expected):
                                raise MediaTransferError('视频文件传输不完整')
                            if offset:
                                part.write_bytes(b'')
                                offset = 0
                            total = len(data)
                            chunk = data
                        break
                    except Exception as exc:
                        last_error = exc
                        permanent = response is not None and response.status in (400, 401, 403, 404, 410, 416)
                        if permanent or attempt == attempts - 1:
                            break
                        if progress_callback:
                            progress_callback(45 + 50 * offset / total if total else 45,
                                              f'连接中断，正在重试当前视频分段（{attempt + 1}/{attempts - 1}）')
                        await asyncio.sleep(min(attempt + 1, 2))
                    finally:
                        if response is not None:
                            try:
                                await response.dispose()
                            except Exception:
                                pass
                if chunk is None:
                    break
                with part.open('ab') as stream:
                    stream.write(chunk)
                offset += len(chunk)
                if progress_callback:
                    progress_callback(min(95, 45 + 50 * offset / total), '备用下载：正在接收视频')
            if total is not None and offset == total and offset > 0:
                part.replace(output)
                return output
        reason = str(last_error).splitlines()[0][:180] if last_error else '没有可用的视频地址'
        raise MediaTransferError(f'视频下载失败，已重试可用地址：{reason}') from last_error
    finally:
        part.unlink(missing_ok=True)
