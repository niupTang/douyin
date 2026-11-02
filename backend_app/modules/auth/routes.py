from flask import Blueprint, jsonify, request


def create_auth_blueprint(auth_required):
    blueprint = Blueprint("auth", __name__)

    @blueprint.route("/auth/me", methods=["GET"])
    @auth_required
    def auth_me():
        admin = request.current_admin
        return jsonify({
            "code": 200,
            "message": None,
            "data": {
                "id": admin["id"],
                "username": admin["username"],
                "displayName": admin["display_name"],
            },
        })


    @blueprint.route("/auth/logout", methods=["POST"])
    def auth_logout():
        return jsonify({"code": 200, "message": "已退出", "data": None})

    return blueprint
