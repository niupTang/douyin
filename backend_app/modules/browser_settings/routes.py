from flask import Blueprint, jsonify, request

from . import service


def create_browser_settings_blueprint(get_db_path):
    blueprint = Blueprint("browser_settings", __name__)

    @blueprint.route("/api/browser/download-directory", methods=["GET", "PUT"])
    def download_directory():
        if request.method == "GET":
            return jsonify({"code": 200, "data": service.get_download_directory(get_db_path())})
        payload = request.get_json(silent=True) or {}
        try:
            result = service.save_download_directory(get_db_path(), payload.get("path"))
        except ValueError as exc:
            return jsonify({"code": 400, "message": str(exc), "data": None}), 400
        return jsonify({"code": 200, "data": result})

    @blueprint.route("/api/browser/download-markdown", methods=["POST"])
    def download_markdown():
        payload = request.get_json(silent=True) or {}
        try:
            result = service.save_markdown_download(
                get_db_path(), payload.get("filename"), payload.get("content")
            )
        except ValueError as exc:
            return jsonify({"code": 400, "message": str(exc), "data": None}), 400
        return jsonify({"code": 200, "data": result})

    return blueprint
