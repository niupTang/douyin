import json
import os
import secrets
from pathlib import Path

from flask import Blueprint, jsonify, request


def create_runtime_blueprint(base_dir):
    blueprint = Blueprint("runtime", __name__)

    @blueprint.route("/runtime/identity", methods=["GET"])
    def runtime_identity():
        response = jsonify({
            "code": 200,
            "data": {
                "service": "sunbird-os-backend",
                "packaged": os.environ.get("SAU_PACKAGED") == "1",
            },
        })
        response.headers["X-SAU-Instance-Token"] = os.environ.get("SAU_INSTANCE_TOKEN", "")
        return response


    @blueprint.route("/runtime/douyin/session", methods=["POST"])
    def runtime_douyin_session():
        expected = os.environ.get("SAU_INSTANCE_TOKEN", "")
        provided = request.headers.get("X-SAU-Instance-Token", "")
        if not expected or not secrets.compare_digest(expected, provided):
            return jsonify({"code": 403, "message": "无效的桌面运行时令牌", "data": None}), 403
        payload = request.get_json(silent=True) or {}
        source_cookies = payload.get("cookies") if isinstance(payload.get("cookies"), list) else []
        cookies = []
        for item in source_cookies:
            domain = str(item.get("domain") or "")
            if "douyin" not in domain:
                continue
            cookie = {
                "name": str(item.get("name") or ""),
                "value": str(item.get("value") or ""),
                "domain": domain,
                "path": str(item.get("path") or "/"),
                "httpOnly": bool(item.get("httpOnly")),
                "secure": bool(item.get("secure")),
                "sameSite": item.get("sameSite") if item.get("sameSite") in {"Strict", "Lax", "None"} else "Lax",
            }
            if item.get("expirationDate"):
                cookie["expires"] = float(item["expirationDate"])
            if cookie["name"]:
                cookies.append(cookie)
        state_path = Path(base_dir / "cookiesFile" / "douyin-electron-session.json")
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"cookies": cookies, "origins": []}, ensure_ascii=False, indent=2), encoding="utf-8")
        return jsonify({"code": 200, "message": "抖音会话已同步", "data": {"cookieCount": len(cookies)}}), 200

    return blueprint
