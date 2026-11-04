import io
import shutil
import subprocess

import pytest
from PIL import Image

from test_koubo_integration import make_client, make_session_client
from backend_app.modules.video_materials import service


@pytest.fixture
def video_bytes(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg is required for media integration tests")
    path = tmp_path / "sample.mp4"
    subprocess.run([
        shutil.which("ffmpeg"), "-v", "error", "-f", "lavfi", "-i",
        "testsrc2=size=320x240:rate=25:duration=2", "-c:v", "libx264", "-y", str(path),
    ], check=True, capture_output=True)
    return path.read_bytes()


def test_upload_extract_and_source_metadata(tmp_path, video_bytes):
    client, store = make_client(tmp_path)
    project = store.create_project({"topic": "素材测试"})
    uploaded = client.post(f"/api/koubo/projects/{project['id']}/videos", data={
        "file": (io.BytesIO(video_bytes), "中文视频.mp4"),
    })
    assert uploaded.status_code == 201
    video = uploaded.get_json()["data"]
    info = client.get(f"/api/koubo/assets/{video['id']}/video-info").get_json()["data"]
    assert (info["width"], info["height"], info["fps"]) == (320, 240, 25)
    extracted = client.post(f"/api/koubo/assets/{video['id']}/frames", json={"seconds": 0.72})
    assert extracted.status_code == 201
    frame = extracted.get_json()["data"]
    assert frame["metadata"] == {"source_asset_id": video["id"], "source_name": "中文视频.mp4", "seconds": 0.72}
    image = client.get(f"/api/koubo/assets/{frame['id']}/content")
    assert Image.open(io.BytesIO(image.data)).size == (320, 240)
    assert store.get_asset(frame["id"])["metadata"] == frame["metadata"]
    assert client.get(f"/api/koubo/projects/{project['id']}/assets").get_json()["data"][-1]["metadata"] == frame["metadata"]
    for seconds in [-1, 2, "bad", None, "NaN", "Infinity"]:
        assert client.post(f"/api/koubo/assets/{video['id']}/frames", json={"seconds": seconds}).status_code == 422
    assert len(store.list_assets(project["id"])) == 2


def test_upload_rejects_invalid_media_and_missing_project(tmp_path):
    client, store = make_client(tmp_path)
    project = store.create_project({})
    url = f"/api/koubo/projects/{project['id']}/videos"
    assert client.post(url, data={"file": (io.BytesIO(b"bad"), "bad.mp4")}).status_code == 422
    assert client.post(url, data={"file": (io.BytesIO(b"bad"), "bad.txt")}).status_code == 400
    assert client.post("/api/koubo/projects/missing/videos").status_code == 404
    assert not store.list_assets(project["id"])
    assert not list((tmp_path / "files").rglob("*.mp4"))


def test_missing_ffmpeg_has_actionable_error(monkeypatch):
    monkeypatch.delenv("SAU_FFMPEG_DIR", raising=False)
    monkeypatch.setattr(service.shutil, "which", lambda _: None)
    with pytest.raises(ValueError, match="SAU_FFMPEG_DIR"):
        service.run_media("ffmpeg", [])


def test_material_endpoints_require_admin(tmp_path):
    client, _, _ = make_session_client(tmp_path)
    for method, url in [("post", "/projects/id/videos"), ("post", "/assets/id/frames"), ("get", "/assets/id/video-info")]:
        assert getattr(client, method)(f"/api/koubo{url}").status_code == 401


def test_existing_assets_receive_empty_metadata_on_upgrade(tmp_path):
    from koubo_integration import KouboStore
    store = KouboStore(tmp_path / "legacy.db")
    with store.connect() as connection:
        connection.execute("""CREATE TABLE koubo_assets (
            id TEXT PRIMARY KEY, project_id TEXT, kind TEXT, storage_path TEXT,
            original_name TEXT, size INTEGER, checksum TEXT, created_at TEXT)""")
        connection.execute("INSERT INTO koubo_assets VALUES ('old', 'project', 'raw_video', 'old.mp4', 'old.mp4', 1, NULL, '2026')")
    store.initialize()
    store.initialize()
    assert store.get_asset("old")["metadata"] == {}
