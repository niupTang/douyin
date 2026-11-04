"""Import exactly one shared Douyin work without scanning its author's feed."""
import asyncio
import json
import re
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright

from backend_app.common.browser_engine import BrowserEngine
from backend_app.common.browser_engine.shared import on_browser_worker
from myUtils.douyin_benchmark import (
    collection_browser_spec, dismiss_douyin_login_popup, normalize_douyin_user_url,
)
from myUtils.douyin_session import resolve_storage_state
from utils.base_social_media import set_init_script


def extract_link(value):
    match = re.search(r'https?://[^\s<>"\u3000，。；！）】]+', str(value or ''))
    if not match:
        raise ValueError('请提供抖音用户主页或视频链接')
    url = match.group().rstrip('.,;!，。；！)）]】')
    parsed = urlparse(url)
    host = (parsed.hostname or '').lower()
    if parsed.scheme not in ('https', 'http') or not (host == 'douyin.com' or host.endswith('.douyin.com')):
        raise ValueError('请提供 douyin.com 的用户主页或视频链接')
    if parsed.username or parsed.password or parsed.port not in (None, 80, 443):
        raise ValueError('无效的抖音链接')
    return url


def video_identity(url):
    parsed = urlparse(url)
    match = re.search(r'/(video|note)/(\d+)(?:/|$)', parsed.path)
    if match:
        return match.group(2), match.group(1)
    query = parse_qs(parsed.query)
    for key in ('modal_id', 'vid', 'item_id'):
        value = (query.get(key) or [''])[0]
        if value.isdigit():
            return value, 'video'
    return None


def find_video_detail(payload, video_id):
    pending = [payload]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            identity = str(item.get('aweme_id') or item.get('awemeId') or '')
            if identity == video_id and (item.get('desc') or item.get('description')):
                return item
            pending.extend(value for value in item.values() if isinstance(value, (dict, list)))
        elif isinstance(item, list):
            pending.extend(item)
    return None


def _image(value):
    if isinstance(value, dict):
        urls = value.get('url_list') or value.get('urlList') or []
        return urls[0] if urls else ''
    return ''


def profile_from_detail(detail, video_id, kind='video'):
    author = detail.get('author') or {}
    sec_uid = author.get('sec_uid') or author.get('secUid')
    homepage = normalize_douyin_user_url(f'https://www.douyin.com/user/{sec_uid}') if sec_uid else ''
    if not homepage:
        raise ValueError('未解析到视频作者，请确认链接可访问并完成抖音登录后重试')
    stats = detail.get('statistics') or {}
    media = detail.get('video') or {}
    return {
        'homepage_url': homepage,
        'nickname': author.get('nickname'),
        'avatar': _image(author.get('avatar_thumb') or author.get('avatarThumb')),
        'bio': author.get('signature'),
        'videos': [{
            'video_url': f'https://www.douyin.com/{kind}/{video_id}',
            'title': detail.get('desc') or detail.get('description'),
            'cover_url': _image(media.get('cover') or media.get('origin_cover')),
            'like_count': stats.get('digg_count', stats.get('diggCount')),
            'comment_count': stats.get('comment_count', stats.get('commentCount')),
            'share_count': stats.get('share_count', stats.get('shareCount')),
            'collect_count': stats.get('collect_count', stats.get('collectCount')),
            'author_name': author.get('nickname'), 'author_url': homepage,
        }],
        'raw_data': {'import_type': 'video', 'video_id': video_id},
    }


@on_browser_worker
async def inspect_shared_link(url, cookie_file=None):
    payloads = []
    tasks = set()
    engine = BrowserEngine(playwright_factory=async_playwright, init_context=set_init_script)
    async with engine.session(collection_browser_spec(resolve_storage_state(cookie_file))) as (_context, page):
        async def capture(response):
            try:
                payloads.append(await response.json())
            except Exception:
                pass

        def on_response(response):
            if any(token in response.url for token in ('/aweme/v1/web/aweme/detail', '/aweme/v1/web/im/item/info', '/web/api/v2/aweme/iteminfo')):
                task = asyncio.create_task(capture(response))
                tasks.add(task)
                task.add_done_callback(tasks.discard)

        page.on('response', on_response)
        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            await page.wait_for_timeout(5000)
            await dismiss_douyin_login_popup(page)
            resolved = extract_link(page.url)
            identity = video_identity(resolved) or video_identity(url)
            if not identity:
                homepage = normalize_douyin_user_url(resolved)
                if homepage:
                    return {'kind': 'profile', 'homepage_url': homepage}
                raise ValueError('链接未解析到用户主页或视频，请检查分享链接是否有效')
            video_id, kind = identity
            if tasks:
                await asyncio.wait_for(asyncio.gather(*list(tasks), return_exceptions=True), timeout=15)
            embedded = await page.evaluate(r'''() => {
                const values = [window._ROUTER_DATA, window.__INITIAL_STATE__, window.__NEXT_DATA__].filter(Boolean);
                const render = document.querySelector('#RENDER_DATA')?.textContent;
                if (render) { try { values.push(JSON.parse(decodeURIComponent(render))); } catch (_) {} }
                return values;
            }''')
            for payload in [*payloads, embedded]:
                detail = find_video_detail(payload, video_id)
                if detail:
                    return {'kind': 'video', 'profile': profile_from_detail(detail, video_id, kind)}
            # Read only the work header; recommendation cards must never become imports.
            dom = await page.evaluate(r'''() => {
                const desc = document.querySelector('[data-e2e="video-desc"]');
                const author = document.querySelector('[data-e2e="video-author"] a[href*="/user/"], a[data-e2e="video-author-name"][href*="/user/"]');
                return {title: desc?.textContent?.trim(), author_url: author?.href, nickname: author?.textContent?.trim()};
            }''')
            homepage = normalize_douyin_user_url(dom.get('author_url'))
            if not homepage or not dom.get('title'):
                raise ValueError('未读取到该视频的完整信息，请在抖音预览中完成登录或验证后重试')
            return {'kind': 'video', 'profile': {
                'homepage_url': homepage, 'nickname': dom.get('nickname'),
                'videos': [{'video_url': f'https://www.douyin.com/{kind}/{video_id}', 'title': dom['title']}],
                'raw_data': {'import_type': 'video', 'video_id': video_id},
            }}
        finally:
            page.remove_listener('response', on_response)
            for task in list(tasks):
                task.cancel()
            if tasks:
                await asyncio.gather(*list(tasks), return_exceptions=True)
