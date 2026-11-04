import hashlib
import uuid
from pathlib import Path

from flask import request

from . import service


def register_material_routes(blueprint, store, storage_root, admin_required, response):
    def source_asset(asset_id):
        asset = store.get_asset(asset_id)
        if not asset or asset["kind"] not in {"raw_video", "edited_video"}:
            raise ValueError("请选择视频素材")
        path = (storage_root / asset["storage_path"]).resolve()
        if storage_root.resolve() not in path.parents or not path.is_file():
            raise ValueError("视频文件不存在")
        return asset, path

    @blueprint.post("/projects/<project_id>/videos")
    @admin_required
    def upload_video(project_id):
        if not store.get_project(project_id):
            return response(message="项目不存在", status=404)
        uploaded = request.files.get("file")
        if not uploaded or Path(uploaded.filename or "").suffix.lower() not in {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}:
            return response(message="请选择 MP4、MOV、MKV、WebM、AVI 或 M4V 视频", status=400)
        folder = storage_root / "projects" / project_id / "raw"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{uuid.uuid4()}{Path(uploaded.filename).suffix.lower()}"
        try:
            uploaded.save(target)
            info = service.probe(target)
            return response(store.add_asset(
                project_id, "raw_video", str(target.relative_to(storage_root)),
                uploaded.filename, target.stat().st_size, metadata=info,
            ), status=201)
        except ValueError as exc:
            target.unlink(missing_ok=True)
            return response(message=str(exc), status=422)
        except Exception:
            target.unlink(missing_ok=True)
            raise

    @blueprint.get("/assets/<asset_id>/video-info")
    @admin_required
    def video_info(asset_id):
        try:
            _, path = source_asset(asset_id)
            return response(service.probe(path))
        except ValueError as exc:
            return response(message=str(exc), status=422)

    @blueprint.post("/assets/<asset_id>/frames")
    @admin_required
    def save_frame(asset_id):
        target = None
        try:
            asset, path = source_asset(asset_id)
            payload = request.get_json(silent=True) or {}
            folder = storage_root / "projects" / asset["project_id"] / "frames"
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / f"{uuid.uuid4()}.png"
            seconds = service.extract_frame(path, target, payload.get("seconds"))
            metadata = {"source_asset_id": asset_id, "source_name": asset["original_name"], "seconds": seconds}
            saved = store.add_asset(
                asset["project_id"], "frame", str(target.relative_to(storage_root)),
                f"{Path(asset['original_name']).stem}_{seconds:.3f}s.png", target.stat().st_size,
                hashlib.sha256(target.read_bytes()).hexdigest(), metadata=metadata,
            )
            return response(saved, status=201)
        except ValueError as exc:
            if target:
                target.unlink(missing_ok=True)
            return response(message=str(exc), status=422)
        except Exception:
            if target:
                target.unlink(missing_ok=True)
            raise
