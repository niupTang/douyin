import threading

from flask import Blueprint, jsonify, request

from backend_app.modules.browser_settings.service import require_download_directory

from . import repository
from .accounts import (
    DataAccountError,
    get_douyin_data_account,
    list_douyin_data_accounts,
    resolve_douyin_data_account,
)
from .importer import parse_own_douyin_import


def create_own_content_blueprint(
    get_db_path, base_dir, save_import, list_videos, list_all_videos,
    analysis_is_running, analyze_video, export_account, log,
):
    blueprint = Blueprint("own_content_review", __name__)

    @blueprint.route('/own/douyin/import/preview', methods=['POST'])
    def preview_own_douyin_import():
        try:
            if 'file' not in request.files:
                return jsonify({"code": 400, "msg": "请上传 CSV 或 XLSX 文件", "data": None}), 400
            account = resolve_douyin_data_account(
                get_db_path(), request.form.get("userInfoId") or request.form.get("user_info_id"), base_dir
            )
            parsed = parse_own_douyin_import(request.files['file'])
            return jsonify({
                "code": 200,
                "msg": "success",
                "data": {
                    "headers": parsed["headers"],
                    "field_map": parsed["field_map"],
                    "raw_count": parsed["raw_count"],
                    "valid_count": parsed["valid_count"],
                    "preview_rows": parsed["rows"][:10],
                }
            }), 200
        except DataAccountError as e:
            return jsonify({"code": e.status_code, "msg": str(e), "data": None}), e.status_code
        except Exception as e:
            return jsonify({"code": 500, "msg": str(e), "data": None}), 500


    @blueprint.route('/own/douyin/import', methods=['POST'])
    def import_own_douyin_videos():
        try:
            if 'file' not in request.files:
                return jsonify({"code": 400, "msg": "请上传 CSV 或 XLSX 文件", "data": None}), 400
            account = resolve_douyin_data_account(
                get_db_path(), request.form.get("userInfoId") or request.form.get("user_info_id"), base_dir
            )
            parsed = parse_own_douyin_import(request.files['file'])
            result = save_import(parsed["rows"], account)
            result.update({
                "raw_count": parsed["raw_count"],
                "valid_count": parsed["valid_count"],
                "field_map": parsed["field_map"],
            })
            return jsonify({"code": 200, "msg": "success", "data": result}), 200
        except DataAccountError as e:
            return jsonify({"code": e.status_code, "msg": str(e), "data": None}), e.status_code
        except Exception as e:
            return jsonify({"code": 500, "msg": str(e), "data": None}), 500


    @blueprint.route('/own/douyin/accounts', methods=['GET'])
    def get_own_douyin_data_accounts():
        try:
            return jsonify({"code": 200, "msg": "success", "data": list_douyin_data_accounts(get_db_path())}), 200
        except Exception as e:
            return jsonify({"code": 500, "msg": str(e), "data": None}), 500


    @blueprint.route('/own/douyin/videos', methods=['GET'])
    def get_own_douyin_videos():
        try:
            account = get_douyin_data_account(get_db_path(), request.args.get("userInfoId"))
            limit = request.args.get("limit", 100)
            videos = list_videos(account["id"], limit)
            return jsonify({"code": 200, "msg": "success", "data": videos}), 200
        except DataAccountError as e:
            return jsonify({"code": e.status_code, "msg": str(e), "data": None}), e.status_code
        except Exception as e:
            return jsonify({"code": 500, "msg": str(e), "data": None}), 500


    @blueprint.route('/own/douyin/videos/all', methods=['GET'])
    def get_all_own_douyin_videos():
        try:
            videos = list_all_videos(request.args.get("limit", 100))
            return jsonify({"code": 200, "msg": "success", "data": videos}), 200
        except Exception as e:
            return jsonify({"code": 500, "msg": str(e), "data": None}), 500


    @blueprint.route('/own/douyin/videos/<int:video_id>/analysis', methods=['POST'])
    def analyze_own_douyin_video(video_id):
        payload = request.get_json(silent=True) or {}
        force = bool(payload.get("force"))

        def runner():
            try:
                analyze_video(video_id, force=force)
            except Exception as exc:
                log(f"Own video analysis failed for {video_id}: {exc}")

        video = repository.get_video(get_db_path(), video_id)
        if not video:
            return jsonify({"code": 404, "msg": "作品不存在", "data": None}), 404
        if force or not analysis_is_running(video):
            threading.Thread(target=runner, name=f"own-video-analysis-{video_id}", daemon=True).start()
        return jsonify({"code": 202, "msg": "已开始分析", "data": {"video_id": video_id, "status": "running"}}), 202


    @blueprint.route('/own/douyin/export/status', methods=['GET'])
    def get_own_douyin_export_status():
        try:
            account = get_douyin_data_account(get_db_path(), request.args.get("userInfoId"))
            data = repository.get_latest_export_run(get_db_path(), account["id"])
            return jsonify({"code": 200, "msg": "success", "data": data}), 200
        except DataAccountError as e:
            return jsonify({"code": e.status_code, "msg": str(e), "data": None}), e.status_code


    @blueprint.route('/own/douyin/export/run', methods=['POST'])
    def run_own_douyin_export_now():
        payload = request.get_json(silent=True) or {}
        try:
            require_download_directory(get_db_path())
        except ValueError as e:
            return jsonify({"code": 400, "msg": str(e), "data": None}), 400
        try:
            account = resolve_douyin_data_account(get_db_path(), payload.get("userInfoId"), base_dir)
            run_id = repository.create_export_run(
                get_db_path(), account["id"], account.get("userName")
            )
        except DataAccountError as e:
            return jsonify({"code": e.status_code, "msg": str(e), "data": None}), e.status_code
        except ValueError as e:
            return jsonify({"code": 409, "msg": str(e), "data": None}), 409

        def runner():
            try:
                export_account(account, run_id=run_id)
            except Exception:
                pass
        thread = threading.Thread(target=runner, name=f"douyin-export-{account['id']}", daemon=True)
        thread.start()
        return jsonify({
            "code": 202,
            "msg": "已开始同步",
            "data": {"runId": run_id, "userInfoId": account["id"], "status": "running"},
        }), 202


    @blueprint.route('/own/douyin/export/login', methods=['POST'])
    def open_own_douyin_creator_login():
        return jsonify({"code": 410, "msg": "请到账号管理重新登录对应抖音账号", "data": None}), 410

    return blueprint
