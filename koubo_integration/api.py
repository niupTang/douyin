import hashlib
import hmac
import os
import uuid
from functools import wraps
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file
from werkzeug.utils import secure_filename
from PIL import Image
from .cover import render_cover
from .templates import TEMPLATE_DEFINITIONS, template_snapshot


def response(data=None, message=None, status=200):
    return jsonify({"code": status, "success": status < 400, "message": message, "data": data}), status


def bearer_token():
    value = request.headers.get("Authorization", "")
    return value[7:].strip() if value.startswith("Bearer ") else ""


def create_koubo_blueprint(store, storage_root=None, admin_token=None, allow_unsafe_dev_admin=False):
    blueprint = Blueprint("koubo", __name__, url_prefix="/api/koubo")
    storage_root = Path(
        storage_root
        or os.environ.get("KOUBO_STORAGE_ROOT")
        or store.database_path.parent.parent / "koubo_data"
    )
    admin_token = admin_token or os.environ.get("KOUBO_ADMIN_TOKEN")

    def device_required(device_type=None):
        def decorator(handler):
            @wraps(handler)
            def wrapped(*args, **kwargs):
                device = store.authenticate(bearer_token(), device_type)
                if not device:
                    return response(message="设备令牌无效或已撤销", status=401)
                return handler(device, *args, **kwargs)
            return wrapped
        return decorator

    def admin_required(handler):
        @wraps(handler)
        def wrapped(*args, **kwargs):
            supplied = bearer_token() or request.args.get("token", "")
            if not admin_token:
                if allow_unsafe_dev_admin:
                    return handler(*args, **kwargs)
                return response(message="未配置口播管理员令牌", status=503)
            if not hmac.compare_digest(supplied, admin_token):
                return response(message="管理员令牌无效", status=401)
            return handler(*args, **kwargs)
        return wrapped

    @blueprint.get("/health")
    def health():
        return response({"service": "koubo", "status": "ok"})

    @blueprint.get("/projects")
    @admin_required
    def list_projects():
        return response(store.list_projects())

    @blueprint.get("/templates")
    @admin_required
    def list_templates():
        return response(list(TEMPLATE_DEFINITIONS.values()))

    @blueprint.post("/projects")
    @admin_required
    def create_project():
        payload = request.get_json(silent=True) or {}
        return response(store.create_project(payload), status=201)

    @blueprint.get("/projects/<project_id>")
    @admin_required
    def get_project(project_id):
        project = store.get_project(project_id)
        return response(project) if project else response(message="项目不存在", status=404)

    @blueprint.put("/projects/<project_id>/script")
    @admin_required
    def update_script(project_id):
        payload = request.get_json(silent=True) or {}
        script = str(payload.get("script", "")).strip()
        if not script:
            return response(message="口播文案不能为空", status=400)
        project = store.update_script(project_id, script)
        return response(project) if project else response(message="项目不存在", status=404)

    @blueprint.post("/devices/binding-code")
    @admin_required
    def binding_code():
        payload = request.get_json(silent=True) or {}
        device_type = payload.get("type", "mobile")
        if device_type not in {"mobile", "worker"}:
            return response(message="设备类型无效", status=400)
        return response(store.create_binding_code(device_type=device_type), status=201)

    @blueprint.get("/devices")
    @admin_required
    def list_devices():
        return response(store.list_devices())

    @blueprint.delete("/devices/<device_id>")
    @admin_required
    def revoke_device(device_id):
        if not store.revoke_device(device_id):
            return response(message="设备不存在或已撤销", status=404)
        return response({"id": device_id, "revoked": True})

    @blueprint.post("/devices/claim")
    def claim_device():
        payload = request.get_json(silent=True) or {}
        claimed = store.claim_binding_code(
            str(payload.get("code", "")),
            str(payload.get("name", "我的手机")).strip() or "我的手机",
            str(payload.get("type", "mobile")),
        )
        return response(claimed, status=201) if claimed else response(
            message="绑定码无效、已使用或已过期", status=400
        )

    @blueprint.get("/mobile/latest")
    @device_required("mobile")
    def mobile_latest(device):
        projects = store.list_projects()
        return response({"device": device, "project": projects[0] if projects else None})

    @blueprint.post("/mobile/projects/<project_id>/raw-video")
    @device_required("mobile")
    def upload_raw_video(device, project_id):
        project = store.get_project(project_id)
        if not project:
            return response(message="项目不存在", status=404)
        uploaded = request.files.get("file")
        if not uploaded or not uploaded.filename:
            return response(message="请选择视频文件", status=400)
        safe_name = secure_filename(uploaded.filename) or f"raw-{uuid.uuid4().hex}.mp4"
        target_dir = storage_root / "projects" / project_id / "raw"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{uuid.uuid4().hex}-{safe_name}"
        digest = hashlib.sha256()
        size = 0
        with target.open("wb") as output:
            while True:
                chunk = uploaded.stream.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        asset = store.add_asset(
            project_id,
            "raw_video",
            str(target.relative_to(storage_root)),
            uploaded.filename,
            size,
            digest.hexdigest(),
        )
        return response(asset, status=201)

    @blueprint.post("/mobile/projects/<project_id>/uploads")
    @device_required("mobile")
    def initialize_upload(device, project_id):
        if not store.get_project(project_id):
            return response(message="项目不存在", status=404)
        payload = request.get_json(silent=True) or {}
        try:
            total_size = int(payload["total_size"])
            chunk_size = int(payload.get("chunk_size", 5 * 1024 * 1024))
            total_chunks = int(payload["total_chunks"])
        except (KeyError, TypeError, ValueError):
            return response(message="上传参数不完整", status=400)
        if total_size <= 0 or chunk_size <= 0 or total_chunks <= 0:
            return response(message="上传参数无效", status=400)
        session = store.create_upload_session(
            project_id,
            device["id"],
            str(payload.get("filename", "raw-video.mov")),
            total_size,
            chunk_size,
            total_chunks,
        )
        (storage_root / "uploads" / session["id"]).mkdir(parents=True, exist_ok=True)
        return response(session, status=201)

    @blueprint.get("/mobile/uploads/<session_id>")
    @device_required("mobile")
    def upload_status(device, session_id):
        session = store.get_upload_session(session_id)
        if not session or session["device_id"] != device["id"]:
            return response(message="上传任务不存在", status=404)
        return response(session)

    @blueprint.put("/mobile/uploads/<session_id>/chunks/<int:chunk_index>")
    @device_required("mobile")
    def upload_chunk(device, session_id, chunk_index):
        session = store.get_upload_session(session_id)
        if not session or session["device_id"] != device["id"] or session["status"] != "uploading":
            return response(message="上传任务不存在或已结束", status=404)
        if chunk_index < 0 or chunk_index >= session["total_chunks"]:
            return response(message="分片序号无效", status=400)
        content = request.get_data(cache=False)
        expected_max = session["chunk_size"]
        if not content or len(content) > expected_max:
            return response(message="分片为空或超过限制", status=400)
        chunk_dir = storage_root / "uploads" / session_id
        chunk_dir.mkdir(parents=True, exist_ok=True)
        temporary = chunk_dir / f"{chunk_index:08d}.part.tmp"
        final = chunk_dir / f"{chunk_index:08d}.part"
        temporary.write_bytes(content)
        temporary.replace(final)
        updated = store.mark_chunk_received(session_id, device["id"], chunk_index)
        return response(
            {
                "session_id": session_id,
                "chunk_index": chunk_index,
                "received_count": len(updated["received_chunks"]),
                "total_chunks": updated["total_chunks"],
            }
        )

    @blueprint.post("/mobile/uploads/<session_id>/complete")
    @device_required("mobile")
    def complete_upload(device, session_id):
        session = store.get_upload_session(session_id)
        if not session or session["device_id"] != device["id"] or session["status"] != "uploading":
            return response(message="上传任务不存在或已结束", status=404)
        expected = set(range(session["total_chunks"]))
        if set(session["received_chunks"]) != expected:
            return response(
                {
                    "missing_chunks": sorted(expected - set(session["received_chunks"])),
                },
                message="仍有分片未上传",
                status=409,
            )
        chunk_dir = storage_root / "uploads" / session_id
        project_dir = storage_root / "projects" / session["project_id"] / "raw"
        project_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(session["original_name"]).suffix or ".mov"
        target = project_dir / f"{uuid.uuid4().hex}{suffix}"
        digest = hashlib.sha256()
        actual_size = 0
        with target.open("wb") as output:
            for chunk_index in range(session["total_chunks"]):
                part = chunk_dir / f"{chunk_index:08d}.part"
                with part.open("rb") as source:
                    while True:
                        block = source.read(1024 * 1024)
                        if not block:
                            break
                        output.write(block)
                        digest.update(block)
                        actual_size += len(block)
        if actual_size != session["total_size"]:
            target.unlink(missing_ok=True)
            return response(message="合并文件大小校验失败", status=422)
        asset = store.add_asset(
            session["project_id"],
            "raw_video",
            str(target.relative_to(storage_root)),
            session["original_name"],
            actual_size,
            digest.hexdigest(),
        )
        store.complete_upload_session(session_id, device["id"])
        for part in chunk_dir.glob("*.part"):
            part.unlink(missing_ok=True)
        chunk_dir.rmdir()
        return response(asset, status=201)

    @blueprint.get("/projects/<project_id>/assets")
    @admin_required
    def project_assets(project_id):
        return response(store.list_assets(project_id))

    @blueprint.post("/projects/<project_id>/cover")
    @admin_required
    def create_cover(project_id):
        project = store.get_project(project_id)
        if not project:
            return response(message="项目不存在", status=404)
        payload = request.get_json(silent=True) or {}
        template = payload.get("template", project.get("edit_template") or "knowledge")
        if template not in {"knowledge", "business"}:
            return response(message="封面模板无效", status=400)
        title = str(payload.get("title") or project["title"] or project["topic"]).strip()
        if not title:
            return response(message="封面标题不能为空", status=400)
        target_dir = storage_root / "projects" / project_id / "cover"
        target = target_dir / f"{uuid.uuid4().hex}.png"
        portrait = next(
            (
                item
                for item in reversed(store.list_assets(project_id))
                if item["kind"] == "portrait"
            ),
            None,
        )
        portrait_path = storage_root / portrait["storage_path"] if portrait else None
        render_cover(
            target,
            title,
            template,
            str(payload.get("author", "")).strip(),
            portrait_path,
        )
        content = target.read_bytes()
        asset = store.add_asset(
            project_id,
            "cover",
            str(target.relative_to(storage_root)),
            target.name,
            len(content),
            hashlib.sha256(content).hexdigest(),
        )
        return response(asset, status=201)

    @blueprint.post("/projects/<project_id>/portrait")
    @admin_required
    def upload_portrait(project_id):
        if not store.get_project(project_id):
            return response(message="项目不存在", status=404)
        uploaded = request.files.get("file")
        if not uploaded or not uploaded.filename:
            return response(message="请选择人物照片", status=400)
        suffix = Path(uploaded.filename).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
            return response(message="仅支持 JPG、PNG 或 WebP 图片", status=400)
        target_dir = storage_root / "projects" / project_id / "cover"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"portrait-{uuid.uuid4().hex}{suffix}"
        digest = hashlib.sha256()
        size = 0
        with target.open("wb") as output:
            while True:
                block = uploaded.stream.read(1024 * 1024)
                if not block:
                    break
                output.write(block)
                digest.update(block)
                size += len(block)
        try:
            with Image.open(target) as image:
                image.verify()
        except Exception:
            target.unlink(missing_ok=True)
            return response(message="图片文件损坏或格式不支持", status=400)
        asset = store.add_asset(
            project_id,
            "portrait",
            str(target.relative_to(storage_root)),
            uploaded.filename,
            size,
            digest.hexdigest(),
        )
        return response(asset, status=201)

    @blueprint.get("/assets/<asset_id>/content")
    @admin_required
    def asset_content(asset_id):
        asset = store.get_asset(asset_id)
        if not asset:
            return response(message="素材不存在", status=404)
        target = (storage_root / asset["storage_path"]).resolve()
        if storage_root.resolve() not in target.parents or not target.is_file():
            return response(message="素材文件不存在", status=404)
        return send_file(target)

    @blueprint.post("/projects/<project_id>/approve")
    @admin_required
    def approve_project(project_id):
        project = store.get_project(project_id)
        if not project:
            return response(message="项目不存在", status=404)
        assets = store.list_assets(project_id)
        edited = next((item for item in reversed(assets) if item["kind"] == "edited_video"), None)
        cover = next((item for item in reversed(assets) if item["kind"] == "cover"), None)
        if not edited:
            return response(message="尚无剪辑成片，不能提交发布", status=409)
        if not cover:
            return response(message="尚无封面，不能提交发布", status=409)
        store.set_project_status(project_id, "ready_publish")
        package = {
            "project_id": project_id,
            "title": project["title"] or project["topic"],
            "tags": project["tags"],
            "video": {
                **edited,
                "absolute_path": str((storage_root / edited["storage_path"]).resolve()),
                "content_url": f"/api/koubo/assets/{edited['id']}/content",
            },
            "cover": {
                **cover,
                "absolute_path": str((storage_root / cover["storage_path"]).resolve()),
                "content_url": f"/api/koubo/assets/{cover['id']}/content",
            },
        }
        return response(package)

    @blueprint.post("/projects/<project_id>/publish-result")
    @admin_required
    def publish_result(project_id):
        if not store.get_project(project_id):
            return response(message="项目不存在", status=404)
        payload = request.get_json(silent=True) or {}
        status = payload.get("status")
        if status not in {"success", "failed"}:
            return response(message="发布结果状态无效", status=400)
        event = store.record_publish(
            project_id,
            payload.get("platform", "unknown"),
            status,
            payload.get("platform_url"),
            payload.get("error_message"),
        )
        return response(event, status=201)

    @blueprint.get("/worker/assets/<asset_id>/download")
    @device_required("worker")
    def worker_download_asset(device, asset_id):
        asset = store.get_asset(asset_id)
        if not asset:
            return response(message="素材不存在", status=404)
        target = (storage_root / asset["storage_path"]).resolve()
        if storage_root.resolve() not in target.parents or not target.is_file():
            return response(message="素材文件不存在", status=404)
        return send_file(target, as_attachment=True, download_name=asset["original_name"])

    @blueprint.post("/projects/<project_id>/edit-jobs")
    @admin_required
    def create_edit_job(project_id):
        payload = request.get_json(silent=True) or {}
        template = payload.get("template", "knowledge")
        if template not in {"knowledge", "business"}:
            return response(message="仅支持 knowledge 或 business 模板", status=400)
        overrides = payload.get("overrides") if isinstance(payload.get("overrides"), dict) else {}
        snapshot = template_snapshot(template, overrides)
        job = store.create_edit_job(project_id, template, snapshot)
        return response(job, status=201) if job else response(message="项目不存在", status=404)

    @blueprint.post("/worker/claim")
    @device_required("worker")
    def worker_claim(device):
        return response(store.claim_job(device["id"]))

    @blueprint.put("/worker/jobs/<job_id>")
    @device_required("worker")
    def worker_update_job(device, job_id):
        payload = request.get_json(silent=True) or {}
        status = payload.get("status")
        if status not in {"editing", "completed", "failed"}:
            return response(message="任务状态无效", status=400)
        job = store.update_job(
            job_id,
            device["id"],
            status,
            max(0, min(100, int(payload.get("progress", 0)))),
            payload.get("error_message"),
        )
        return response(job) if job else response(message="任务不存在或不属于当前工作器", status=404)

    @blueprint.post("/worker/jobs/<job_id>/artifacts")
    @device_required("worker")
    def worker_upload_artifact(device, job_id):
        job = store.get_job(job_id)
        if not job or job["worker_id"] != device["id"]:
            return response(message="任务不存在或不属于当前工作器", status=404)
        kind = request.form.get("kind", "")
        if kind not in {"edited_video", "subtitle", "preview", "cover"}:
            return response(message="产物类型无效", status=400)
        uploaded = request.files.get("file")
        if not uploaded or not uploaded.filename:
            return response(message="请选择产物文件", status=400)
        project_dir = storage_root / "projects" / job["project_id"] / "edit"
        project_dir.mkdir(parents=True, exist_ok=True)
        safe_name = secure_filename(uploaded.filename) or f"{kind}-{uuid.uuid4().hex}"
        target = project_dir / f"{uuid.uuid4().hex}-{safe_name}"
        digest = hashlib.sha256()
        size = 0
        with target.open("wb") as output:
            while True:
                block = uploaded.stream.read(1024 * 1024)
                if not block:
                    break
                output.write(block)
                digest.update(block)
                size += len(block)
        asset = store.add_asset(
            job["project_id"],
            kind,
            str(target.relative_to(storage_root)),
            uploaded.filename,
            size,
            digest.hexdigest(),
        )
        return response(asset, status=201)

    return blueprint
