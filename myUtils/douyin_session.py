"""Shared Douyin collection and preview sessions, isolated by cookie file."""
from pathlib import Path
from urllib.parse import urlsplit

from backend_app.common.browser_engine import BrowserEngine
from backend_app.common.browser_engine.shared import on_browser_worker, shared_contexts
from conf import BASE_DIR


def resolve_storage_state(cookie_file=None):
    # An explicitly selected account always wins over the legacy Electron session.
    if cookie_file:
        path = Path(BASE_DIR) / "cookiesFile" / cookie_file
        if not path.is_file():
            raise FileNotFoundError("当前抖音账号的会话文件不存在，请重新登录该账号")
        return path
    path = Path(BASE_DIR) / "cookiesFile" / "douyin-electron-session.json"
    return path if path.is_file() else None


def session_key(storage_state):
    path = storage_state or Path(BASE_DIR) / "cookiesFile" / "douyin-electron-session.json"
    return "douyin:" + str(Path(path).resolve())


def validate_preview_url(url):
    value = str(url or "").strip()
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower()
    if (parsed.scheme != "https" or parsed.username or parsed.password
            or parsed.port not in (None, 443)
            or not (host == "douyin.com" or host.endswith(".douyin.com"))):
        raise ValueError("仅支持 HTTPS 抖音作品或主页链接")
    return value


@on_browser_worker
async def open_preview(url, cookie_file=None):
    from myUtils.douyin_benchmark import collection_browser_spec
    from utils.base_social_media import set_init_script

    url = validate_preview_url(url)
    spec = collection_browser_spec(resolve_storage_state(cookie_file))
    engine = BrowserEngine(init_context=set_init_script)
    context = await shared_contexts.get(engine, spec)
    page = await context.new_page()
    try:
        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.bring_to_front()
    except BaseException:
        await page.close()
        raise
    return {"url": page.url, "sharedSession": True}


@on_browser_worker
async def save_session(cookie_file=None):
    from myUtils.douyin_benchmark import collection_browser_spec
    from utils.base_social_media import set_init_script

    state = resolve_storage_state(cookie_file)
    spec = collection_browser_spec(state)
    context = await shared_contexts.get(BrowserEngine(init_context=set_init_script), spec)
    destination = state or Path(BASE_DIR) / "cookiesFile" / "douyin-electron-session.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = await context.storage_state(path=str(destination))
    return {"cookieCount": len(result["cookies"])}
