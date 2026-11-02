import os
import secrets
from functools import wraps
from types import SimpleNamespace

from flask import jsonify, request


def configure_auth_policy(app, token_serializer, auth_token_max_age, license_registry):

    def parse_auth_token():
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        token = auth_header.removeprefix("Bearer ").strip()
        if not token:
            return None
        try:
            admin = token_serializer.loads(token, max_age=auth_token_max_age)
        except Exception:
            return None
        return admin if str(admin.get("id") or "").startswith("license:") else None


    def auth_required(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            admin = parse_auth_token()
            if not admin:
                return jsonify({"code": 401, "message": "未登录或登录已过期", "data": None}), 401
            request.current_admin = admin
            return fn(*args, **kwargs)
        return wrapper


    @app.before_request
    def require_local_login():
        if request.method == "OPTIONS":
            return None
        public_paths = {
            "/",
            "/favicon.ico",
            "/login",
            "/runtime/identity",
            "/runtime/douyin/session",
            "/runtime/license/install",
            "/runtime/license/status",
            "/runtime/license/clear",
            "/runtime/ai/pi-credential",
        }
        if request.path in public_paths or request.path.startswith("/assets/"):
            return None
        if request.path.startswith("/auth/"):
            return None
        if request.path.startswith("/api/koubo/"):
            return None
        admin = parse_auth_token()
        if not admin:
            return jsonify({"code": 401, "message": "未登录或登录已过期", "data": None}), 401
        request.current_admin = admin
        entitlement = required_entitlement(request.path, request.method)
        if entitlement:
            allowed, status = license_registry.require(entitlement)
            if not allowed:
                return jsonify({
                    "code": 403,
                    "message": status["message"],
                    "data": {"reasonCode": status["reasonCode"], "entitlement": entitlement},
                }), 403
        return None


    def required_entitlement(path, method):
        if path.startswith("/script-generation/"):
            return "scriptStudio"
        if path.startswith("/idea-radar/") and method == "POST":
            return "aiAnalysis"
        if path.startswith("/benchmark/") and method == "POST":
            return "aiAnalysis" if path.endswith("/analysis") or path.endswith("/pi-analysis") else "benchmarkCollect"
        if path.startswith("/publish/") and method == "POST":
            return "publishing"
        if path in {"/postVideo", "/postVideoBatch"} and method == "POST":
            return "publishing"
        # MCP tool permissions are checked by the execution gateway per tool.
        if path.startswith("/own/douyin/") and method == "POST":
            return "metricsSync"
        return None


    def valid_instance_token():
        expected = os.environ.get("SAU_INSTANCE_TOKEN", "")
        provided = request.headers.get("X-SAU-Instance-Token", "")
        return bool(expected and secrets.compare_digest(expected, provided))

    return SimpleNamespace(
        auth_required=auth_required,
        parse_auth_token=parse_auth_token,
        valid_instance_token=valid_instance_token,
    )
