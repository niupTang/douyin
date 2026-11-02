import asyncio
import sqlite3
from pathlib import Path

import pytest
from flask import Flask

from backend_app.common.browser_engine import (
    BrowserEngine,
    BrowserSpec,
    BrowserStrategyRegistry,
    validate_download_directory,
)
from backend_app.modules.browser_settings.routes import create_browser_settings_blueprint
from backend_app.modules.browser_settings.service import (
    get_download_directory,
    require_download_directory,
)


def test_user_selected_download_directory_is_saved_and_validated(tmp_path):
    db_path = tmp_path / "settings.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute("""
            CREATE TABLE app_settings (
                key TEXT PRIMARY KEY, value_json TEXT NOT NULL,
                value_type TEXT NOT NULL, updated_at TEXT
            )
        """)
    directory = tmp_path / "downloads"
    directory.mkdir()
    app = Flask(__name__)
    app.register_blueprint(create_browser_settings_blueprint(lambda: db_path))
    client = app.test_client()

    assert client.get("/api/browser/download-directory").get_json()["data"]["valid"] is False
    saved = client.put("/api/browser/download-directory", json={"path": str(directory)})
    assert saved.status_code == 200
    assert saved.get_json()["data"]["path"] == str(directory.resolve())
    assert require_download_directory(db_path) == directory.resolve()

    markdown = client.post("/api/browser/download-markdown", json={
        "filename": "../观点雷达.md", "content": "# 测试\n",
    })
    assert markdown.status_code == 200
    saved_markdown = Path(markdown.get_json()["data"]["path"])
    assert saved_markdown.parent == directory
    assert saved_markdown.read_text(encoding="utf-8") == "# 测试\n"
    saved_markdown.unlink()

    directory.rmdir()
    assert get_download_directory(db_path)["valid"] is False
    assert client.put("/api/browser/download-directory", json={"path": str(directory)}).status_code == 400


def test_c_drive_and_relative_download_paths_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="绝对路径"):
        validate_download_directory("downloads")
    if tmp_path.drive.upper() != "C:":
        with pytest.raises(ValueError, match="C 盘"):
            validate_download_directory("C:\\")


def test_browser_engine_dispatches_strategy_and_closes_on_failure():
    closed = []

    class FakeContext:
        pages = []

        async def new_page(self):
            return object()

        async def close(self):
            closed.append("context")

    class FakeBrowser:
        async def new_context(self, **kwargs):
            assert kwargs["locale"] == "zh-CN"
            return FakeContext()

        async def close(self):
            closed.append("browser")

    class FakeChromium:
        async def launch(self, **kwargs):
            assert kwargs["headless"] is True
            return FakeBrowser()

    class FakeManager:
        async def __aenter__(self):
            return type("Playwright", (), {"chromium": FakeChromium()})()

        async def __aexit__(self, *_):
            closed.append("playwright")

    class FailingStrategy:
        platform = "douyin"
        operation = "collect"

        def browser_spec(self, _request):
            return BrowserSpec(context_options={"locale": "zh-CN"})

        async def execute(self, _context, _page, _request):
            raise RuntimeError("page changed")

    registry = BrowserStrategyRegistry()
    registry.register(FailingStrategy())
    with pytest.raises(ValueError, match="已存在"):
        registry.register(FailingStrategy())
    with pytest.raises(ValueError, match="不支持"):
        registry.get("tencent", "collect")

    engine = BrowserEngine(registry, playwright_factory=FakeManager)
    with pytest.raises(RuntimeError, match="page changed"):
        asyncio.run(engine.run("douyin", "collect", {}))
    assert closed == ["context", "browser", "playwright"]


def test_browser_engine_uses_persistent_profile_without_browser_instance(tmp_path):
    calls = []

    class FakeContext:
        pages = [object()]

        async def close(self):
            calls.append("close-context")

    class FakeChromium:
        async def launch_persistent_context(self, profile, **options):
            assert profile == str(tmp_path / "profile")
            assert options["headless"] is False
            assert options["locale"] == "zh-CN"
            calls.append("launch-profile")
            return FakeContext()

    class FakeManager:
        async def __aenter__(self):
            return type("Playwright", (), {"chromium": FakeChromium()})()

        async def __aexit__(self, *_):
            calls.append("close-playwright")

    class LoginStrategy:
        platform = "douyin"
        operation = "login"

        def browser_spec(self, _request):
            return BrowserSpec(
                headless=False,
                persistent_profile=str(tmp_path / "profile"),
                context_options={"locale": "zh-CN"},
            )

        async def execute(self, _context, _page, _request):
            calls.append("execute")
            return "ok"

    registry = BrowserStrategyRegistry()
    registry.register(LoginStrategy())
    result = asyncio.run(BrowserEngine(registry, playwright_factory=FakeManager).run("douyin", "login", {}))
    assert result == "ok"
    assert calls == ["launch-profile", "execute", "close-context", "close-playwright"]
