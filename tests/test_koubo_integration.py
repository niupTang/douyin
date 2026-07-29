import io
from pathlib import Path

from flask import Flask
from PIL import Image

from koubo_integration import KouboStore, create_koubo_blueprint


def make_client(tmp_path):
    store = KouboStore(Path(tmp_path) / "koubo.db")
    store.initialize()
    app = Flask(__name__)
    app.register_blueprint(create_koubo_blueprint(store, Path(tmp_path) / "files"))
    app.testing = True
    return app.test_client(), store


def test_project_script_sync_and_mobile_binding(tmp_path):
    client, _ = make_client(tmp_path)
    created = client.post(
        "/api/koubo/projects",
        json={"topic": "AI 提效", "script": "初稿", "tags": ["AI"]},
    )
    assert created.status_code == 201
    project = created.get_json()["data"]

    updated = client.put(
        f"/api/koubo/projects/{project['id']}/script",
        json={"script": "同步到手机的新文案"},
    )
    assert updated.status_code == 200
    assert updated.get_json()["data"]["script_version"] == 2

    binding = client.post("/api/koubo/devices/binding-code").get_json()["data"]
    claimed = client.post(
        "/api/koubo/devices/claim",
        json={"code": binding["code"], "name": "iPhone", "type": "mobile"},
    )
    assert claimed.status_code == 201
    token = claimed.get_json()["data"]["token"]

    latest = client.get(
        "/api/koubo/mobile/latest",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert latest.status_code == 200
    assert latest.get_json()["data"]["project"]["script"] == "同步到手机的新文案"


def test_binding_code_is_single_use(tmp_path):
    client, _ = make_client(tmp_path)
    binding = client.post("/api/koubo/devices/binding-code").get_json()["data"]
    payload = {"code": binding["code"], "name": "iPhone", "type": "mobile"}
    assert client.post("/api/koubo/devices/claim", json=payload).status_code == 201
    assert client.post("/api/koubo/devices/claim", json=payload).status_code == 400


def test_worker_claims_each_job_once(tmp_path):
    client, store = make_client(tmp_path)
    project = client.post("/api/koubo/projects", json={"topic": "商业观点"}).get_json()["data"]
    job = client.post(
        f"/api/koubo/projects/{project['id']}/edit-jobs",
        json={"template": "business"},
    )
    assert job.status_code == 201

    binding = store.create_binding_code(device_type="worker")
    worker = store.claim_binding_code(binding["code"], "Windows", "worker")
    headers = {"Authorization": f"Bearer {worker['token']}"}
    first = client.post("/api/koubo/worker/claim", headers=headers)
    second = client.post("/api/koubo/worker/claim", headers=headers)
    assert first.get_json()["data"]["template_snapshot"]["id"] == "business"
    assert second.get_json()["data"] is None


def test_mobile_uploads_raw_video(tmp_path):
    client, store = make_client(tmp_path)
    project = client.post("/api/koubo/projects", json={"topic": "上传测试"}).get_json()["data"]
    binding = store.create_binding_code()
    mobile = store.claim_binding_code(binding["code"], "iPhone", "mobile")
    uploaded = client.post(
        f"/api/koubo/mobile/projects/{project['id']}/raw-video",
        headers={"Authorization": f"Bearer {mobile['token']}"},
        data={"file": (io.BytesIO(b"fake-video-content"), "take.mov")},
        content_type="multipart/form-data",
    )
    assert uploaded.status_code == 201
    assert uploaded.get_json()["data"]["size"] == len(b"fake-video-content")
    assert store.get_project(project["id"])["status"] == "uploaded"


def test_mobile_resumes_chunked_upload_and_worker_returns_artifact(tmp_path):
    client, store = make_client(tmp_path)
    project = client.post("/api/koubo/projects", json={"topic": "分片上传"}).get_json()["data"]
    mobile_binding = store.create_binding_code()
    mobile = store.claim_binding_code(mobile_binding["code"], "iPhone", "mobile")
    mobile_headers = {"Authorization": f"Bearer {mobile['token']}"}
    content = b"0123456789ABCDEF"
    initialized = client.post(
        f"/api/koubo/mobile/projects/{project['id']}/uploads",
        headers=mobile_headers,
        json={"filename": "take.mov", "total_size": len(content), "chunk_size": 8, "total_chunks": 2},
    ).get_json()["data"]
    for index, chunk in [(1, content[8:]), (0, content[:8])]:
        uploaded = client.put(
            f"/api/koubo/mobile/uploads/{initialized['id']}/chunks/{index}",
            headers={**mobile_headers, "Content-Type": "application/octet-stream"},
            data=chunk,
        )
        assert uploaded.status_code == 200
    completed = client.post(
        f"/api/koubo/mobile/uploads/{initialized['id']}/complete",
        headers=mobile_headers,
    )
    assert completed.status_code == 201
    assert completed.get_json()["data"]["checksum"]

    client.post(
        f"/api/koubo/projects/{project['id']}/edit-jobs",
        json={"template": "knowledge"},
    )
    worker_binding = store.create_binding_code(device_type="worker")
    worker = store.claim_binding_code(worker_binding["code"], "Windows", "worker")
    worker_headers = {"Authorization": f"Bearer {worker['token']}"}
    job = client.post("/api/koubo/worker/claim", headers=worker_headers).get_json()["data"]
    artifact = client.post(
        f"/api/koubo/worker/jobs/{job['id']}/artifacts",
        headers=worker_headers,
        data={"kind": "edited_video", "file": (io.BytesIO(b"final-video"), "final.mp4")},
        content_type="multipart/form-data",
    )
    assert artifact.status_code == 201
    finished = client.put(
        f"/api/koubo/worker/jobs/{job['id']}",
        headers=worker_headers,
        json={"status": "completed", "progress": 100},
    )
    assert finished.status_code == 200
    assert store.get_project(project["id"])["status"] == "waiting_cover"


def test_generates_1080_by_1920_cover(tmp_path):
    client, store = make_client(tmp_path)
    project = client.post(
        "/api/koubo/projects",
        json={"topic": "AI 提效", "title": "普通人如何用 AI 提升效率"},
    ).get_json()["data"]
    generated = client.post(
        f"/api/koubo/projects/{project['id']}/cover",
        json={"template": "business", "author": "SUN"},
    )
    assert generated.status_code == 201
    asset = generated.get_json()["data"]
    target = Path(tmp_path) / "files" / asset["storage_path"]
    with Image.open(target) as image:
        assert image.size == (1080, 1920)


def test_requires_video_and_cover_before_publish_approval(tmp_path):
    client, store = make_client(tmp_path)
    project = client.post(
        "/api/koubo/projects", json={"topic": "发布闭环", "title": "发布标题", "tags": ["AI"]}
    ).get_json()["data"]
    assert client.post(f"/api/koubo/projects/{project['id']}/approve").status_code == 409
    video_path = Path(tmp_path) / "files" / "projects" / project["id"] / "edit" / "final.mp4"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.write_bytes(b"video")
    store.add_asset(
        project["id"], "edited_video", str(video_path.relative_to(Path(tmp_path) / "files")),
        "final.mp4", 5, "checksum"
    )
    client.post(f"/api/koubo/projects/{project['id']}/cover", json={"template": "knowledge"})
    approved = client.post(f"/api/koubo/projects/{project['id']}/approve")
    assert approved.status_code == 200
    assert approved.get_json()["data"]["video"]["absolute_path"].endswith("final.mp4")
    assert store.get_project(project["id"])["status"] == "ready_publish"


def test_admin_token_protects_control_plane(tmp_path):
    store = KouboStore(Path(tmp_path) / "secure.db")
    store.initialize()
    app = Flask(__name__)
    app.register_blueprint(
        create_koubo_blueprint(store, Path(tmp_path) / "secure-files", admin_token="secret")
    )
    client = app.test_client()
    assert client.get("/api/koubo/projects").status_code == 401
    authorized = client.get(
        "/api/koubo/projects", headers={"Authorization": "Bearer secret"}
    )
    assert authorized.status_code == 200


def test_binding_code_locks_device_type_and_admin_can_revoke(tmp_path):
    client, store = make_client(tmp_path)
    binding = client.post(
        "/api/koubo/devices/binding-code", json={"type": "worker"}
    ).get_json()["data"]
    wrong_type = client.post(
        "/api/koubo/devices/claim",
        json={"code": binding["code"], "name": "iPhone", "type": "mobile"},
    )
    assert wrong_type.status_code == 400
    worker = client.post(
        "/api/koubo/devices/claim",
        json={"code": binding["code"], "name": "Windows", "type": "worker"},
    ).get_json()["data"]
    devices = client.get("/api/koubo/devices").get_json()["data"]
    assert devices[0]["type"] == "worker"
    assert client.delete(f"/api/koubo/devices/{worker['device_id']}").status_code == 200
    assert store.authenticate(worker["token"], "worker") is None


def test_publish_result_updates_project_status(tmp_path):
    client, store = make_client(tmp_path)
    project = client.post("/api/koubo/projects", json={"topic": "发布结果"}).get_json()["data"]
    result = client.post(
        f"/api/koubo/projects/{project['id']}/publish-result",
        json={"platform": 3, "status": "success"},
    )
    assert result.status_code == 201
    assert store.get_project(project["id"])["status"] == "published"


def test_portrait_can_be_uploaded_and_used_for_cover(tmp_path):
    client, _ = make_client(tmp_path)
    project = client.post("/api/koubo/projects", json={"topic": "人物封面"}).get_json()["data"]
    portrait_buffer = io.BytesIO()
    Image.new("RGB", (600, 900), (120, 80, 60)).save(portrait_buffer, "JPEG")
    portrait_buffer.seek(0)
    uploaded = client.post(
        f"/api/koubo/projects/{project['id']}/portrait",
        data={"file": (portrait_buffer, "portrait.jpg")},
        content_type="multipart/form-data",
    )
    assert uploaded.status_code == 201
    cover = client.post(
        f"/api/koubo/projects/{project['id']}/cover",
        json={"template": "knowledge"},
    )
    assert cover.status_code == 201


def test_edit_job_freezes_template_parameters(tmp_path):
    client, _ = make_client(tmp_path)
    project = client.post("/api/koubo/projects", json={"topic": "模板快照"}).get_json()["data"]
    created = client.post(
        f"/api/koubo/projects/{project['id']}/edit-jobs",
        json={
            "template": "knowledge",
            "overrides": {"broll_level": 3, "target_duration_seconds": 45},
        },
    )
    snapshot = created.get_json()["data"]["template_snapshot"]
    assert snapshot["version"] == 1
    assert snapshot["parameters"]["broll_level"] == 3
    assert snapshot["parameters"]["target_duration_seconds"] == 45


def test_full_project_lifecycle(tmp_path):
    client, store = make_client(tmp_path)
    project = client.post(
        "/api/koubo/projects",
        json={"topic": "完整闭环", "title": "AI 口播闭环", "script": "第一版文案"},
    ).get_json()["data"]
    synced = client.put(
        f"/api/koubo/projects/{project['id']}/script",
        json={"script": "同步到手机的最终文案"},
    ).get_json()["data"]
    assert synced["status"] == "synced"

    mobile_code = client.post(
        "/api/koubo/devices/binding-code", json={"type": "mobile"}
    ).get_json()["data"]
    mobile = client.post(
        "/api/koubo/devices/claim",
        json={"code": mobile_code["code"], "name": "iPhone", "type": "mobile"},
    ).get_json()["data"]
    mobile_headers = {"Authorization": f"Bearer {mobile['token']}"}
    latest = client.get("/api/koubo/mobile/latest", headers=mobile_headers).get_json()["data"]
    assert latest["project"]["script"] == "同步到手机的最终文案"

    raw_content = b"raw-video"
    uploaded = client.post(
        f"/api/koubo/mobile/projects/{project['id']}/raw-video",
        headers=mobile_headers,
        data={"file": (io.BytesIO(raw_content), "take.mov")},
        content_type="multipart/form-data",
    )
    assert uploaded.status_code == 201

    job = client.post(
        f"/api/koubo/projects/{project['id']}/edit-jobs",
        json={"template": "knowledge"},
    ).get_json()["data"]
    worker_code = client.post(
        "/api/koubo/devices/binding-code", json={"type": "worker"}
    ).get_json()["data"]
    worker = client.post(
        "/api/koubo/devices/claim",
        json={"code": worker_code["code"], "name": "Windows", "type": "worker"},
    ).get_json()["data"]
    worker_headers = {"Authorization": f"Bearer {worker['token']}"}
    claimed = client.post("/api/koubo/worker/claim", headers=worker_headers).get_json()["data"]
    assert claimed["id"] == job["id"]
    client.post(
        f"/api/koubo/worker/jobs/{job['id']}/artifacts",
        headers=worker_headers,
        data={"kind": "edited_video", "file": (io.BytesIO(b"edited"), "final.mp4")},
        content_type="multipart/form-data",
    )
    client.put(
        f"/api/koubo/worker/jobs/{job['id']}",
        headers=worker_headers,
        json={"status": "completed", "progress": 100},
    )
    assert store.get_project(project["id"])["status"] == "waiting_cover"

    client.post(
        f"/api/koubo/projects/{project['id']}/cover",
        json={"template": "knowledge"},
    )
    assert store.get_project(project["id"])["status"] == "waiting_review"
    assert client.post(f"/api/koubo/projects/{project['id']}/approve").status_code == 200
    assert store.get_project(project["id"])["status"] == "ready_publish"
    client.post(
        f"/api/koubo/projects/{project['id']}/publish-result",
        json={"platform": 3, "status": "success"},
    )
    assert store.get_project(project["id"])["status"] == "published"
