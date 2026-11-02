import asyncio
import inspect
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from backend_app.common.browser_engine import BrowserSpec
from backend_app.common.browser_engine.shared import SharedContexts, worker
from myUtils.douyin_session import validate_preview_url


class Page:
    closed = False

    def is_closed(self):
        return self.closed

    async def close(self):
        self.closed = True


class Context:
    def __init__(self):
        self.closed = False
        self.handlers = {}

    def on(self, event, callback):
        self.handlers[event] = callback

    async def new_page(self):
        return Page()


class Engine:
    def __init__(self):
        self.contexts = []

    @asynccontextmanager
    async def session(self, spec):
        context = Context()
        self.contexts.append(context)
        try:
            yield context, Page()
        finally:
            context.closed = True


def test_parallel_tasks_share_context_and_keep_preview_alive():
    async def run():
        pool, engine = SharedContexts(), Engine()
        spec = BrowserSpec(shared_key="account-a")
        context = await pool.get(engine, spec)
        preview = await context.new_page()

        async def collect():
            async with pool.session(engine, spec) as (actual, page):
                assert actual is context
                await asyncio.sleep(0)
            assert page.closed

        await asyncio.gather(collect(), collect())
        assert len(engine.contexts) == 1
        assert not context.closed and not preview.closed
        other = await pool.get(engine, BrowserSpec(shared_key="account-b"))
        assert other is not context
        await pool.close()
        assert context.closed and other.closed

    worker.submit(run()).result(timeout=10)


def test_manually_closed_browser_is_recreated():
    async def run():
        pool, engine = SharedContexts(), Engine()
        spec = BrowserSpec(shared_key="account-a")
        first = await pool.get(engine, spec)
        first.handlers["close"]()
        second = await pool.get(engine, spec)
        assert first is not second and first.closed
        await pool.close()

    worker.submit(run()).result(timeout=10)


@pytest.mark.parametrize("url", [
    "file:///E:/secret", "https://douyin.com.evil.test/", "http://www.douyin.com/",
    "https://user:pass@www.douyin.com/", "https://www.douyin.com:5409/",
])
def test_preview_rejects_non_platform_urls(url):
    with pytest.raises(ValueError):
        validate_preview_url(url)


def test_failed_task_closes_page_but_retains_context():
    async def run():
        pool, engine = SharedContexts(), Engine()
        spec = BrowserSpec(shared_key="account-a")
        with pytest.raises(ValueError, match="collection failed"):
            async with pool.session(engine, spec) as (context, page):
                raise ValueError("collection failed")
        assert page.closed and not context.closed
        assert await pool.get(engine, spec) is context
        await pool.close()

    worker.submit(run()).result(timeout=10)


def test_preview_endpoint_validates_url_and_selects_current_account(monkeypatch):
    from flask import Flask
    from backend_app.modules.benchmark import routes

    dependencies = {name: lambda *args: None
                    for name, parameter in inspect.signature(routes.create_benchmark_blueprint).parameters.items()
                    if parameter.default is inspect.Parameter.empty}
    dependencies["latest_douyin_cookie_file"] = lambda: "current-account.json"
    app = Flask(__name__)
    app.register_blueprint(routes.create_benchmark_blueprint(**dependencies))
    preview = AsyncMock(return_value={"sharedSession": True})
    monkeypatch.setattr(routes, "open_preview", preview)
    client = app.test_client()
    assert client.post('/benchmark/douyin/preview', json={"url": "https://evil.test/"}).status_code == 400
    preview.assert_not_awaited()
    url = "https://www.douyin.com/video/123"
    assert client.post('/benchmark/douyin/preview', json={"url": url}).status_code == 200
    preview.assert_awaited_once_with(url, "current-account.json")


def test_explicit_missing_account_never_uses_another_session(tmp_path, monkeypatch):
    from myUtils import douyin_session

    monkeypatch.setattr(douyin_session, "BASE_DIR", tmp_path)
    cookie_dir = tmp_path / "cookiesFile"
    cookie_dir.mkdir()
    legacy = cookie_dir / "douyin-electron-session.json"
    legacy.write_text('{"cookies": [], "origins": []}', encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        douyin_session.resolve_storage_state("missing-account.json")
    assert douyin_session.resolve_storage_state() == legacy
