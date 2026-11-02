import sqlite3
import json

import pytest
from flask import Flask

from backend_app.modules.own_content_review import repository
from backend_app.modules.own_content_review.accounts import DataAccountError, resolve_douyin_data_account
from backend_app.modules.own_content_review.exporter import export_creator_content
from backend_app.modules.own_content_review.routes import create_own_content_blueprint
from backend_app.modules.browser_settings.service import save_download_directory


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "own-content.db"
    with sqlite3.connect(path) as conn:
        conn.execute("""
            CREATE TABLE user_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type INTEGER NOT NULL,
                filePath TEXT NOT NULL,
                userName TEXT NOT NULL,
                status INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE app_settings (
                key TEXT PRIMARY KEY, value_json TEXT NOT NULL,
                value_type TEXT NOT NULL, updated_at TEXT
            )
        """)
        conn.executemany(
            "INSERT INTO user_info (type, filePath, userName, status) VALUES (3, ?, ?, 1)",
            [("first.json", "账号一"), ("second.json", "账号二")],
        )
    return path


def test_imported_works_are_isolated_by_selected_account(db):
    rows = [{"title": "同一条作品", "video_url": "https://douyin.example/video/1", "play_count": 100}]
    source_key = lambda item: f"url:{item['video_url']}"

    first = repository.save_import(db, rows, 1, "账号一", source_key)
    second = repository.save_import(db, rows, 2, "账号二", source_key)

    first_videos = repository.list_videos(db, 1, 100)
    second_videos = repository.list_videos(db, 2, 100)

    assert first["account_id"] != second["account_id"]
    assert [item["account_name"] for item in first_videos] == ["账号一"]
    assert [item["account_name"] for item in second_videos] == ["账号二"]
    assert first_videos[0]["play_count"] == 100
    assert second_videos[0]["play_count"] == 100


def test_selected_account_resolves_cookie_only_from_cookie_directory(db, tmp_path):
    cookies_dir = tmp_path / "cookiesFile"
    cookies_dir.mkdir()
    cookie_file = cookies_dir / "first.json"
    cookie_file.write_text(json.dumps({"cookies": [], "origins": []}), encoding="utf-8")

    account = resolve_douyin_data_account(db, 1, tmp_path)

    assert account["id"] == 1
    assert account["userName"] == "账号一"
    assert account["cookie_path"] == cookie_file.resolve()


def test_sync_rejects_expired_account_cookie(db, tmp_path):
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE user_info SET status = 0 WHERE id = 1")

    with pytest.raises(DataAccountError, match="重新登录") as error:
        resolve_douyin_data_account(db, 1, tmp_path)

    assert error.value.status_code == 409


def test_sync_rejects_cookie_path_outside_cookie_directory(db, tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps({"cookies": [], "origins": []}), encoding="utf-8")
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE user_info SET filePath = '../outside.json' WHERE id = 1")

    with pytest.raises(DataAccountError, match="路径无效"):
        resolve_douyin_data_account(db, 1, tmp_path)


def test_export_status_and_running_guard_are_scoped_by_account(db):
    run_id = repository.create_export_run(db, 1, "账号一")

    assert repository.get_latest_export_run(db, 1)["id"] == run_id
    assert repository.get_latest_export_run(db, 2) is None
    with pytest.raises(ValueError, match="正在同步"):
        repository.create_export_run(db, 1, "账号一")

    other_run_id = repository.create_export_run(db, 2, "账号二")
    assert other_run_id != run_id


def test_own_content_routes_can_read_and_create_export_runs(db, tmp_path, monkeypatch):
    cookies_dir = tmp_path / "cookiesFile"
    cookies_dir.mkdir()
    (cookies_dir / "first.json").write_text(
        json.dumps({"cookies": [], "origins": []}), encoding="utf-8"
    )
    app = Flask(__name__)
    app.register_blueprint(create_own_content_blueprint(
        get_db_path=lambda: db,
        base_dir=tmp_path,
        save_import=lambda *_: None,
        list_videos=lambda *_: [],
        list_all_videos=lambda *_: [],
        analysis_is_running=lambda *_: False,
        analyze_video=lambda *_: None,
        export_account=lambda *_, **__: None,
        log=lambda *_: None,
    ))
    monkeypatch.setattr("backend_app.modules.own_content_review.routes.threading.Thread.start", lambda self: None)
    client = app.test_client()

    missing_video = client.post("/own/douyin/videos/999/analysis")
    assert missing_video.status_code == 404

    assert client.post("/own/douyin/export/run", json={"userInfoId": 1}).status_code == 400
    save_download_directory(db, tmp_path)
    started = client.post("/own/douyin/export/run", json={"userInfoId": 1})
    assert started.status_code == 202
    run_id = started.get_json()["data"]["runId"]

    status = client.get("/own/douyin/export/status?userInfoId=1")
    assert status.status_code == 200
    assert status.get_json()["data"]["id"] == run_id


def test_export_uses_selected_cookie_in_temporary_browser_context(tmp_path, monkeypatch):
    monkeypatch.setenv("SAU_BROWSER_PRESENTATION", "headless")
    cookie_path = tmp_path / "cookiesFile" / "selected.json"
    cookie_path.parent.mkdir()
    (tmp_path / "downloads").mkdir()
    cookie_path.write_text(json.dumps({"cookies": [], "origins": []}), encoding="utf-8")
    captured = {}

    class FakeDownload:
        suggested_filename = "creator.xlsx"

        async def save_as(self, target):
            captured["target"] = target
            target.write_bytes(b"xlsx")

    class DownloadContext:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        @property
        async def value(self):
            return FakeDownload()

    class FakeLocator:
        async def count(self):
            return 1

        @property
        def first(self):
            return self

        async def click(self):
            return None

        async def inner_text(self, **_):
            return "作品管理 导出"

        def filter(self, **_):
            return self

    class FakePage:
        async def goto(self, *_args, **_kwargs):
            return None

        async def wait_for_timeout(self, *_):
            return None

        def locator(self, *_):
            return FakeLocator()

        def get_by_role(self, *_args, **_kwargs):
            return FakeLocator()

        def expect_download(self, **_):
            return DownloadContext()

    class FakeContext:
        pages = []

        async def new_page(self):
            return FakePage()

        async def storage_state(self, path):
            captured["state_path"] = path
            path.write_text(json.dumps({"cookies": [{"name": "fresh"}], "origins": []}), encoding="utf-8")

        async def close(self):
            captured["context_closed"] = True

    class FakeBrowser:
        async def new_context(self, **kwargs):
            captured["context_options"] = kwargs
            return FakeContext()

        async def close(self):
            captured["browser_closed"] = True

    class FakeChromium:
        async def launch(self, **options):
            captured["launch_options"] = options
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakePlaywrightManager:
        async def __aenter__(self):
            return FakePlaywright()

        async def __aexit__(self, *_):
            return False

    async def passthrough(context):
        return context

    target = export_creator_content(
        cookie_path,
        download_dir=tmp_path / "downloads",
        playwright_factory=FakePlaywrightManager,
        init_context=passthrough,
    )

    assert captured["context_options"]["storage_state"] == str(cookie_path)
    assert captured["launch_options"]["downloads_path"] == str((tmp_path / "downloads").resolve())
    assert captured["context_closed"] is True
    assert captured["browser_closed"] is True
    assert target.read_bytes() == b"xlsx"
    assert json.loads(cookie_path.read_text(encoding="utf-8"))["cookies"][0]["name"] == "fresh"
