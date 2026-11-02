import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from playwright.async_api import Error as PlaywrightError

from backend_app.common.browser_engine import BrowserEngine, BrowserSpec
from backend_app.common.browser_engine import engine as engine_module
from backend_app.common.browser_engine import presentation
from backend_app.modules.idea_radar.media import DouyinMediaDownloadStrategy
from backend_app.modules.own_content_review.exporter import DouyinCreatorExportStrategy
from myUtils import douyin_benchmark


@pytest.fixture
def floating_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("SAU_BASE_DIR", str(tmp_path))
    monkeypatch.setenv("SAU_BROWSER_PRESENTATION", "floating")
    monkeypatch.setenv("DISPLAY", ":test")
    for key in ("TEMP", "TMP", "TMPDIR"):
        monkeypatch.setenv(key, str(tmp_path))


def test_floating_launch_preserves_proxy_and_keeps_driver_temp_on_data_drive(floating_environment):
    original = {"proxy": {"server": "http://localhost:8080"}, "args": ["--window-size=1440,1200"]}
    headless, options = presentation.prepare_floating_launch(original)
    assert headless is False
    assert options["proxy"] == original["proxy"]
    assert "--window-size=900,700" in options["args"]
    assert original["args"] == ["--window-size=1440,1200"]
    assert Path(options["downloads_path"]).is_dir()
    assert options["env"]["TEMP"] == options["downloads_path"]
    assert presentation.os.environ["TEMP"] == options["downloads_path"]
    assert Path(options["downloads_path"]).drive.upper() != "C:"


def test_collection_defaults_to_headless_on_desktop(monkeypatch, floating_environment):
    monkeypatch.delenv("SAU_BROWSER_PRESENTATION", raising=False)
    monkeypatch.setattr(presentation.sys, "platform", "win32")
    assert presentation.floating_enabled() is False
    spec = douyin_benchmark.collection_browser_spec()
    assert spec.headless is True
    assert Path(spec.launch_options["downloads_path"]).drive.upper() != "C:"


def test_headless_override_and_no_display_server(monkeypatch, floating_environment):
    monkeypatch.setenv("SAU_BROWSER_PRESENTATION", "headless")
    headless, options = presentation.prepare_floating_launch({})
    assert headless is True
    assert "args" not in options
    monkeypatch.setenv("SAU_BROWSER_PRESENTATION", "floating")
    monkeypatch.setattr(presentation.sys, "platform", "linux")
    monkeypatch.delenv("DISPLAY")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    assert presentation.floating_enabled() is False


def test_presentation_scales_without_changing_extraction_viewport(monkeypatch):
    calls = []

    class Session:
        async def send(self, method, params=None):
            calls.append((method, params))
            return {"windowId": 8}

    class Context:
        browser = None

        async def new_cdp_session(self, page):
            return Session()

    asyncio.run(presentation.configure_floating_page(Context(), object(), {"width": 1440, "height": 1200}))
    metrics = next(params for method, params in calls if method == "Emulation.setDeviceMetricsOverride")
    assert (metrics["width"], metrics["height"]) == (1440, 1200)
    assert 0 < metrics["scale"] < 1
    assert metrics["mobile"] is False
    assert calls[1][1]["bounds"] == {"windowState": "normal"}


def fake_browser_factory(events, *, fail_on_navigation=False):
    class Page:
        closed = False

        async def goto(self, *_args, **_kwargs):
            if fail_on_navigation:
                raise RuntimeError("navigation failed")

        def is_closed(self):
            return self.closed

    class Context:
        pages = []

        async def new_page(self):
            return Page()

        async def add_init_script(self, **_kwargs):
            events.append("init-script")

        async def close(self):
            events.append("close-context")

    class Browser:
        async def new_context(self, **kwargs):
            events.append(("context", kwargs))
            return Context()

        async def close(self):
            events.append("close-browser")

    class Chromium:
        async def launch(self, **kwargs):
            events.append(("launch", kwargs))
            return Browser()

    class Manager:
        async def __aenter__(self):
            return SimpleNamespace(chromium=Chromium())

        async def __aexit__(self, *_):
            events.append("close-playwright")

    return Manager


@pytest.fixture
def fake_presentation(monkeypatch):
    async def configure(*_):
        pass
    monkeypatch.setattr(engine_module, "configure_floating_page", configure)


@pytest.mark.parametrize("outcome", ["success", "failure", "cancel", "window-closed"])
def test_floating_session_always_closes_owned_resources(outcome, floating_environment, fake_presentation):
    events = []

    async def run():
        engine = BrowserEngine(playwright_factory=fake_browser_factory(events))
        async with engine.session(BrowserSpec(presentation="floating")) as (_, page):
            if outcome == "failure":
                raise RuntimeError("failed")
            if outcome == "cancel":
                raise asyncio.CancelledError()
            if outcome == "window-closed":
                page.closed = True
                raise PlaywrightError("Target page, context or browser has been closed")

    if outcome == "success":
        asyncio.run(run())
    elif outcome == "cancel":
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(run())
    else:
        with pytest.raises(RuntimeError, match="浮窗已关闭" if outcome == "window-closed" else "failed"):
            asyncio.run(run())
    assert events[0][1]["headless"] is False
    assert events[-3:] == ["close-context", "close-browser", "close-playwright"]


@pytest.mark.parametrize("operation", ["sync", "discover", "search"])
def test_existing_collection_entrypoints_use_shared_session(
    operation, monkeypatch, floating_environment, fake_presentation,
):
    events = []
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def session(_self, spec):
        events.append(spec)
        raise RuntimeError("navigation failed")
        yield

    monkeypatch.setattr(BrowserEngine, "session", session)
    calls = {
        "sync": lambda: douyin_benchmark.scrape_douyin_benchmark("https://www.douyin.com/user/test"),
        "discover": lambda: douyin_benchmark.discover_douyin_benchmark_accounts(["test"]),
        "search": lambda: douyin_benchmark.search_douyin_content(["test"]),
    }
    with pytest.raises(RuntimeError, match="navigation failed"):
        asyncio.run(calls[operation]())
    assert events[0].headless is False
    assert events[0].context_options["viewport"] == {"width": 1440, "height": 1200}
    assert events[0].shared_key.startswith("douyin:")


def test_download_is_headless_while_export_keeps_its_presentation(tmp_path):
    cookie = tmp_path / "account.json"
    cookie.write_text('{"cookies": [], "origins": []}', encoding="utf-8")
    media = DouyinMediaDownloadStrategy().browser_spec({"storage_state_path": cookie})
    export = DouyinCreatorExportStrategy().browser_spec({"cookie_path": cookie, "download_dir": tmp_path})
    assert media.headless is True
    assert media.shared_key is None
    assert media.presentation is None
    assert export.presentation == "floating"
    for spec in (media, export):
        assert spec.context_options["storage_state"] == str(cookie)
    assert export.download_dir == tmp_path


def test_headless_download_uses_latest_live_login_state(tmp_path):
    cookie = tmp_path / "account.json"
    cookie.write_text('{"cookies": [], "origins": []}', encoding="utf-8")
    live_state = {"cookies": [{"name": "login", "value": "latest"}], "origins": []}
    spec = DouyinMediaDownloadStrategy().browser_spec({
        "storage_state_path": cookie, "session_storage_state": live_state,
    })
    assert spec.headless and spec.shared_key is None
    assert spec.context_options["storage_state"] == live_state
