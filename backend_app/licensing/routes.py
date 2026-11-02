from flask import Blueprint, jsonify, request

from .service import LicenseValidationError


def create_license_blueprint(valid_instance_token, license_registry, token_serializer):
    blueprint = Blueprint("licensing", __name__)

    @blueprint.route("/runtime/license/install", methods=["POST"])
    def runtime_license_install():
        if not valid_instance_token():
            return jsonify({"code": 403, "message": "无效的桌面运行时令牌", "data": None}), 403
        payload = request.get_json(silent=True) or {}
        try:
            context = license_registry.install(payload.get("license"), str(payload.get("deviceId") or ""))
        except LicenseValidationError as exc:
            license_registry.clear()
            return jsonify({"code": 403, "message": str(exc), "data": {"reasonCode": exc.code}}), 403
        local_user = {
            "id": f"license:{context.payload.get('credentialId')}",
            "username": "licensed-device",
            "display_name": "已授权设备",
        }
        token = token_serializer.dumps(local_user)
        return jsonify({
            "code": 200,
            "message": "许可证已安装",
            "data": {
                "token": token,
                "user": {"id": local_user["id"], "username": local_user["username"], "displayName": local_user["display_name"]},
                "license": license_registry.public_status(),
            },
        })


    @blueprint.route("/runtime/license/status", methods=["GET"])
    def runtime_license_status():
        return jsonify({"code": 200, "message": None, "data": license_registry.public_status()})


    @blueprint.route("/runtime/license/clear", methods=["POST"])
    def runtime_license_clear():
        if not valid_instance_token():
            return jsonify({"code": 403, "message": "无效的桌面运行时令牌", "data": None}), 403
        license_registry.clear()
        return jsonify({"code": 200, "message": "本地许可证已清除", "data": None})

    return blueprint
