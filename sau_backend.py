import os;

import asyncio
import csv
import hashlib
import io
import json
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import tempfile
import traceback
import uuid
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
from flask_cors import CORS
from functools import wraps
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from myUtils.auth import check_cookie
from myUtils.douyin_benchmark import (
    discover_douyin_benchmark_accounts,
    normalize_douyin_user_url,
    scrape_douyin_benchmark,
)
from flask import Flask, request, jsonify, Response, render_template, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash
from backend_app.agent.gateway_client import (
    get_hermes_settings as agent_get_hermes_settings,
    hermes_request as agent_hermes_request,
    public_hermes_settings as agent_public_hermes_settings,
)
from backend_app.agent.model_registry import (
    get_agent_models as agent_get_agent_models,
    get_task_agent_model as agent_get_task_agent_model,
    normalize_agent_model as agent_normalize_agent_model,
)
from backend_app.agent.structured_runner import (
    call_hermes_structured as agent_call_hermes_structured,
    load_json_object as agent_load_json_object,
    resolve_executable as agent_resolve_executable,
    run_codex_cli_structured as agent_run_codex_cli_structured,
)
from backend_app.modules.benchmark.prompts import build_video_analysis_prompt
from backend_app.modules.benchmark import repository as benchmark_repository
from backend_app.modules.benchmark.schemas import video_analysis_schema
from backend_app.modules.idea_radar.prompts import build_transcript_radar_prompt as build_idea_radar_prompt
from backend_app.modules.idea_radar import repository as idea_radar_repository
from backend_app.modules.idea_radar.jobs import IdeaRadarJobRegistry
from backend_app.modules.idea_radar.service import get_status as get_idea_radar_status_payload
from backend_app.modules.idea_radar.service import start_pipeline_task
from backend_app.modules.idea_radar.pipeline import run_pipeline as run_idea_radar_pipeline_core
from backend_app.modules.idea_radar.schemas import transcript_radar_schema
from backend_app.modules.idea_radar import media as idea_radar_media
from backend_app.modules.script_generation.prompts import build_identity_script_prompt
from backend_app.modules.script_generation.schemas import identity_script_schema
from backend_app.modules.mcp_server.tools import describe_tools as describe_mcp_tools
from backend_app.modules.mcp_server.tools import create_tool_handlers
from backend_app.modules.own_content_review import repository as own_content_repository
from backend_app.modules.own_content_review.service import review_published_content
from backend_app.modules.ai_publish import repository as publish_repository
from backend_app.modules.ai_publish.service import publish_video as publish_video_service
from backend_app.modules.accounts import repository as account_repository
from backend_app.modules.dashboard.service import get_dashboard_stats as dashboard_stats_service
from conf import BASE_DIR
from myUtils.login import get_tencent_cookie, douyin_cookie_gen, get_ks_cookie, xiaohongshu_cookie_gen
from myUtils.postVideo import post_video_tencent, post_video_DouYin, post_video_ks, post_video_xhs


active_queues = {}
idea_radar_job_registry = IdeaRadarJobRegistry()
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SAU_SECRET_KEY") or secrets.token_hex(32)
AUTH_TOKEN_MAX_AGE = int(os.environ.get("SAU_AUTH_TOKEN_MAX_AGE", str(7 * 24 * 60 * 60)))
token_serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="sau-local-auth")

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(errors="replace")
    except Exception:
        pass

#允许所有来源跨域访问
CORS(app)

# 限制上传文件大小为160MB
app.config['MAX_CONTENT_LENGTH'] = 160 * 1024 * 1024


def get_db_path():
    return Path(BASE_DIR / "db" / "database.db")


def get_settings_path():
    return Path(BASE_DIR / "settings.json")


def load_runtime_settings():
    settings_path = get_settings_path()
    if not settings_path.exists():
        return {}
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_runtime_settings(settings):
    settings_path = get_settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = settings_path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary_path.replace(settings_path)


def get_hermes_settings(settings=None):
    return agent_get_hermes_settings(settings or load_runtime_settings())


def get_agent_models(settings=None):
    return agent_get_agent_models(settings or load_runtime_settings())


def public_hermes_settings(settings=None):
    return agent_public_hermes_settings(settings or load_runtime_settings())


def hermes_request(path, method="GET", payload=None, timeout=None, settings=None):
    return agent_hermes_request(path, method=method, payload=payload, timeout=timeout, settings=settings or load_runtime_settings())


def normalize_agent_model(payload, existing_id=None):
    return agent_normalize_agent_model(payload, existing_id)


def get_runtime_setting(*keys, env=None, default=None):
    if env and os.environ.get(env):
        return os.environ.get(env)
    settings = load_runtime_settings()
    for key in keys:
        value = settings.get(key)
        if value:
            return value
    return default


def resolve_executable(command, label):
    return agent_resolve_executable(command, label, get_settings_path())


def ensure_local_auth_table():
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS local_admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        default_username = os.environ.get("SAU_ADMIN_USER", "admin")
        default_password = os.environ.get("SAU_ADMIN_PASSWORD", "admin123")
        cursor.execute("SELECT id FROM local_admins WHERE username = ?", (default_username,))
        if cursor.fetchone() is None:
            cursor.execute(
                "INSERT INTO local_admins (username, password_hash, display_name) VALUES (?, ?, ?)",
                (default_username, generate_password_hash(default_password), "Administrator"),
            )
        conn.commit()


def ensure_core_tables():
    ensure_local_auth_table()
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type INTEGER NOT NULL,
            filePath TEXT NOT NULL,
            userName TEXT NOT NULL,
            status INTEGER DEFAULT 0,
            follower_count INTEGER DEFAULT 0
        )
        ''')
        user_info_columns = {
            row[1] for row in cursor.execute("PRAGMA table_info(user_info)").fetchall()
        }
        if "follower_count" not in user_info_columns:
            cursor.execute(
                "ALTER TABLE user_info ADD COLUMN follower_count INTEGER DEFAULT 0"
            )
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS file_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            filesize REAL,
            upload_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            file_path TEXT
        )
        ''')
        conn.commit()
    ensure_publish_records_table()
    ensure_douyin_benchmark_tables()
    ensure_douyin_own_tables()


def create_auth_token(admin):
    return token_serializer.dumps({
        "id": admin["id"],
        "username": admin["username"],
        "display_name": admin["display_name"],
    })


def parse_auth_token():
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        token = request.args.get("token")
    if not token:
        return None
    try:
        data = token_serializer.loads(token, max_age=AUTH_TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    return data


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
        "/auth/login",
        "/runtime/identity",
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
    return None


@app.route("/runtime/identity", methods=["GET"])
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


@app.route("/auth/login", methods=["POST"])
def auth_login():
    ensure_local_auth_table()
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"code": 400, "message": "请输入用户名和密码", "data": None}), 400

    with sqlite3.connect(get_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM local_admins WHERE username = ?", (username,))
        admin = cursor.fetchone()

    if not admin or not check_password_hash(admin["password_hash"], password):
        return jsonify({"code": 401, "message": "用户名或密码错误", "data": None}), 401

    user = {
        "id": admin["id"],
        "username": admin["username"],
        "displayName": admin["display_name"],
    }
    return jsonify({"code": 200, "message": "登录成功", "data": {"token": create_auth_token(admin), "user": user}})


@app.route("/auth/me", methods=["GET"])
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


@app.route("/auth/logout", methods=["POST"])
def auth_logout():
    return jsonify({"code": 200, "message": "已退出", "data": None})

@app.route("/settings/hermes", methods=["GET", "PUT"])
def hermes_settings_api():
    settings = load_runtime_settings()
    if request.method == "GET":
        return jsonify({"code": 200, "data": public_hermes_settings(settings)})
    payload = request.get_json(silent=True) or {}
    current = get_hermes_settings(settings)
    gateway_url = str(payload.get("gatewayUrl") or "").strip().rstrip("/")
    if not re.match(r"^https?://", gateway_url, re.IGNORECASE):
        return jsonify({"code": 400, "message": "Gateway 地址必须以 http:// 或 https:// 开头"}), 400
    try:
        timeout = max(10, min(int(payload.get("timeout") or current["timeout"]), 1800))
    except (TypeError, ValueError):
        return jsonify({"code": 400, "message": "超时时间必须是数字"}), 400
    api_key = current["apiKey"]
    if payload.get("clearApiKey"):
        api_key = ""
    elif payload.get("apiKey"):
        api_key = str(payload.get("apiKey")).strip()
    settings["hermes"] = {"gatewayUrl": gateway_url, "apiKey": api_key, "timeout": timeout}
    save_runtime_settings(settings)
    return jsonify({"code": 200, "message": "Hermes 配置已保存", "data": public_hermes_settings(settings)})


@app.route("/settings/hermes/test", methods=["POST"])
def test_hermes_settings():
    try:
        health = hermes_request("/health", timeout=15)
        capabilities = None
        try:
            capabilities = hermes_request("/v1/capabilities", timeout=20)
        except Exception as exc:
            backend_log(f"Hermes capabilities unavailable, using legacy mode: {exc}")
        return jsonify({"code": 200, "message": "Hermes Gateway 连接正常", "data": {
            "health": health, "capabilities": capabilities,
            "legacyMode": capabilities is None,
        }})
    except Exception as exc:
        return jsonify({"code": 502, "message": str(exc), "data": None}), 502


@app.route("/settings/hermes/models", methods=["GET"])
def discover_hermes_models():
    try:
        refresh = request.args.get("refresh") in {"1", "true", "True"}
        path = "/api/model/options?refresh=1" if refresh else "/api/model/options"
        try:
            options = hermes_request(path, timeout=60 if refresh else 30)
        except Exception as exc:
            backend_log(f"Hermes rich model catalog unavailable, using /v1/models: {exc}")
            legacy = hermes_request("/v1/models", timeout=30)
            rows = legacy.get("data") if isinstance(legacy, dict) else []
            options = {
                "legacyMode": True,
                "providers": [{
                    "provider": "gateway-default",
                    "models": [
                        {"id": item.get("id"), "name": item.get("id")}
                        for item in (rows or []) if isinstance(item, dict) and item.get("id")
                    ],
                }],
            }
        return jsonify({"code": 200, "data": options})
    except Exception as exc:
        return jsonify({"code": 502, "message": str(exc), "data": None}), 502


@app.route("/settings/agent-models", methods=["GET", "POST"])
def agent_models_api():
    settings = load_runtime_settings()
    if request.method == "GET":
        task_models = settings.get("taskModels") if isinstance(settings.get("taskModels"), dict) else {}
        return jsonify({"code": 200, "data": {"models": get_agent_models(settings), "taskModels": task_models}})
    try:
        model = normalize_agent_model(request.get_json(silent=True) or {})
        models = get_agent_models(settings)
        models.append(model)
        settings["agentModels"] = models
        save_runtime_settings(settings)
        return jsonify({"code": 200, "message": "Agent 模型已添加", "data": model})
    except ValueError as exc:
        return jsonify({"code": 400, "message": str(exc), "data": None}), 400


@app.route("/settings/agent-models/<model_id>", methods=["PUT", "DELETE"])
def agent_model_api(model_id):
    settings = load_runtime_settings()
    models = get_agent_models(settings)
    index = next((i for i, item in enumerate(models) if item.get("id") == model_id), None)
    if index is None:
        return jsonify({"code": 404, "message": "Agent 模型不存在", "data": None}), 404
    if request.method == "DELETE":
        models.pop(index)
        task_models = settings.get("taskModels") if isinstance(settings.get("taskModels"), dict) else {}
        settings["taskModels"] = {key: value for key, value in task_models.items() if value != model_id}
        settings["agentModels"] = models
        save_runtime_settings(settings)
        return jsonify({"code": 200, "message": "Agent 模型已删除", "data": None})
    try:
        model = normalize_agent_model(request.get_json(silent=True) or {}, existing_id=model_id)
        models[index] = model
        settings["agentModels"] = models
        save_runtime_settings(settings)
        return jsonify({"code": 200, "message": "Agent 模型已更新", "data": model})
    except ValueError as exc:
        return jsonify({"code": 400, "message": str(exc), "data": None}), 400


@app.route("/settings/task-models", methods=["PUT"])
def task_models_api():
    payload = request.get_json(silent=True) or {}
    viral_model_id = str(payload.get("viralAnalysis") or "").strip()
    settings = load_runtime_settings()
    if viral_model_id and not any(
        item.get("id") == viral_model_id and item.get("enabled", True)
        for item in get_agent_models(settings)
    ):
        return jsonify({"code": 400, "message": "所选 Agent 模型不存在或已停用", "data": None}), 400
    task_models = settings.get("taskModels") if isinstance(settings.get("taskModels"), dict) else {}
    task_models["viralAnalysis"] = viral_model_id
    settings["taskModels"] = task_models
    save_runtime_settings(settings)
    return jsonify({"code": 200, "message": "爆款拆解模型已保存", "data": task_models})


@app.route("/settings/agent-models/<model_id>/test", methods=["POST"])
def test_agent_model(model_id):
    settings = load_runtime_settings()
    model = next((item for item in get_agent_models(settings) if item.get("id") == model_id), None)
    if not model:
        return jsonify({"code": 404, "message": "Agent 模型不存在", "data": None}), 404
    started = time.monotonic()
    try:
        result = call_hermes_structured(
            "只返回一个 JSON 对象，字段 result 的值必须是 OK。",
            {"type": "object", "additionalProperties": False, "required": ["result"],
             "properties": {"result": {"type": "string"}}},
            model_config=model, timeout=60,
        )
        return jsonify({"code": 200, "message": "模型测试成功", "data": {
            "result": result, "elapsedMs": int((time.monotonic() - started) * 1000),
            "provider": model.get("provider"), "model": model.get("model"),
        }})
    except Exception as exc:
        return jsonify({"code": 502, "message": str(exc), "data": None}), 502


def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        text = " ".join(str(arg) for arg in args)
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(text.encode(encoding, errors="replace").decode(encoding, errors="replace"), **kwargs)


def backend_log(message):
    try:
        log_dir = Path(BASE_DIR / "logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        with open(log_dir / "backend.log", "a", encoding="utf-8") as file:
            file.write(f"[{datetime.now().isoformat()}] {message}\n")
    except Exception:
        pass

def ensure_publish_records_table():
    publish_repository.ensure_tables(get_db_path())


def ensure_douyin_benchmark_tables():
    benchmark_repository.ensure_tables(get_db_path())


def ensure_douyin_own_tables():
    own_content_repository.ensure_tables(get_db_path())


def latest_douyin_cookie_file():
    return account_repository.latest_douyin_cookie_file(get_db_path())


OWN_DOUYIN_FIELD_ALIASES = {
    "title": ["作品名称", "标题", "title", "作品标题"],
    "video_url": ["作品链接", "视频链接", "video_url", "url", "链接"],
    "published_at": ["发布时间", "published_at", "发布时间 "],
    "content_format": ["体裁", "内容体裁", "content_format"],
    "visibility_status": ["审核状态", "状态", "visibility_status"],
    "play_count": ["播放量", "播放次数", "play_count"],
    "completion_rate": ["完播率", "completion_rate"],
    "five_sec_completion_rate": ["5s完播率", "5秒完播率", "five_sec_completion_rate"],
    "cover_click_rate": ["封面点击率", "cover_click_rate"],
    "two_sec_bounce_rate": ["2s跳出率", "2秒跳出率", "two_sec_bounce_rate"],
    "avg_play_duration": ["平均播放时长", "avg_play_duration"],
    "like_count": ["点赞量", "点赞数", "like_count"],
    "share_count": ["分享量", "分享数", "share_count"],
    "comment_count": ["评论量", "评论数", "comment_count"],
    "collect_count": ["收藏量", "收藏数", "collect_count"],
    "profile_visit_count": ["主页访问量", "profile_visit_count"],
    "follower_delta": ["粉丝增量", "涨粉数", "follower_delta"],
    "transcript": ["作品文案", "文案", "口播文案", "transcript"],
    "notes": ["备注", "notes"],
}

OWN_DOUYIN_INTEGER_FIELDS = {
    "play_count", "like_count", "share_count", "comment_count", "collect_count",
    "profile_visit_count", "follower_delta",
}
OWN_DOUYIN_FLOAT_FIELDS = {
    "completion_rate", "five_sec_completion_rate", "cover_click_rate",
    "two_sec_bounce_rate", "avg_play_duration",
}


def normalize_import_header(value):
    return re.sub(r"\s+", "", str(value or "")).strip().lower()


def build_own_douyin_field_map(headers):
    normalized_headers = {normalize_import_header(header): header for header in headers}
    mapping = {}
    for target, aliases in OWN_DOUYIN_FIELD_ALIASES.items():
        for alias in aliases:
            header = normalized_headers.get(normalize_import_header(alias))
            if header is not None:
                mapping[target] = header
                break
    return mapping


def clean_import_value(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"-", "—", "nan", "NaN", "None"}:
        return None
    return text


def parse_import_int(value):
    text = clean_import_value(value)
    if text is None:
        return None
    text = text.replace(",", "")
    try:
        return int(float(text))
    except Exception:
        return None


def parse_import_float(value):
    text = clean_import_value(value)
    if text is None:
        return None
    text = text.replace(",", "")
    try:
        if text.endswith("%"):
            return float(text[:-1]) / 100
        return float(text)
    except Exception:
        return None


def normalize_import_row(raw_row, field_map):
    item = {}
    for field, header in field_map.items():
        value = raw_row.get(header)
        if field in OWN_DOUYIN_INTEGER_FIELDS:
            item[field] = parse_import_int(value)
        elif field in OWN_DOUYIN_FLOAT_FIELDS:
            item[field] = parse_import_float(value)
        else:
            item[field] = clean_import_value(value)
    item["title"] = item.get("title") or ""
    return item


def own_douyin_source_key(item):
    url = clean_import_value(item.get("video_url"))
    if url:
        return f"url:{url}"
    title = clean_import_value(item.get("title")) or ""
    published_at = clean_import_value(item.get("published_at")) or ""
    digest = hashlib.sha1(f"{title}|{published_at}".encode("utf-8")).hexdigest()
    return f"title_time:{digest}"


def read_own_douyin_import_file(file_storage):
    filename = (file_storage.filename or "").lower()
    payload = file_storage.read()
    rows = []
    if filename.endswith(".xlsx"):
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise RuntimeError("缺少 openpyxl 依赖，请先安装 requirements.txt") from exc
        workbook = load_workbook(io.BytesIO(payload), read_only=True, data_only=True)
        sheet = workbook.active
        values = list(sheet.iter_rows(values_only=True))
        if not values:
            return [], []
        headers = [str(cell).strip() if cell is not None else "" for cell in values[0]]
        for row in values[1:]:
            raw = {headers[index]: value for index, value in enumerate(row) if index < len(headers) and headers[index]}
            if any(clean_import_value(value) for value in raw.values()):
                rows.append(raw)
        return headers, rows
    if filename.endswith(".csv"):
        text = None
        for encoding in ("utf-8-sig", "gb18030"):
            try:
                text = payload.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise ValueError("CSV 编码无法识别，请使用 UTF-8 或 GB18030")
        reader = csv.DictReader(io.StringIO(text))
        headers = reader.fieldnames or []
        rows = [row for row in reader if any(clean_import_value(value) for value in row.values())]
        return headers, rows
    raise ValueError("仅支持 .xlsx 或 .csv 文件")


def parse_own_douyin_import(file_storage):
    headers, raw_rows = read_own_douyin_import_file(file_storage)
    field_map = build_own_douyin_field_map(headers)
    if "title" not in field_map:
        raise ValueError("导入文件缺少作品名称/标题字段")
    normalized_rows = [normalize_import_row(row, field_map) for row in raw_rows]
    valid_rows = [row for row in normalized_rows if row.get("title")]
    return {
        "headers": headers,
        "field_map": field_map,
        "rows": valid_rows,
        "raw_count": len(raw_rows),
        "valid_count": len(valid_rows),
    }


def upsert_own_douyin_account(name="太阳鸟"):
    account_name = clean_import_value(name) or "太阳鸟"
    return own_content_repository.upsert_account(get_db_path(), account_name)


def save_own_douyin_import(rows, account_name="太阳鸟"):
    account_name = clean_import_value(account_name) or "太阳鸟"
    return own_content_repository.save_import(
        get_db_path(),
        rows,
        account_name,
        own_douyin_source_key,
    )


def list_own_douyin_videos(limit=100):
    return own_content_repository.list_videos(get_db_path(), limit)


def get_douyin_benchmark_video_urls(account_id):
    return benchmark_repository.list_video_urls(get_db_path(), account_id)


def upsert_douyin_benchmark(homepage_url):
    return benchmark_repository.upsert_account(
        get_db_path(), homepage_url, normalize_douyin_user_url
    )


def delete_douyin_benchmark(account_id):
    ensure_douyin_benchmark_tables()
    database_path = Path(BASE_DIR / "db" / "database.db")
    with sqlite3.connect(database_path) as conn:
        conn.row_factory = sqlite3.Row
        account = conn.execute(
            "SELECT id, nickname, homepage_url FROM douyin_benchmark_accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
        if not account:
            return None
        video_ids = [
            row[0] for row in conn.execute(
                "SELECT id FROM douyin_benchmark_videos WHERE account_id = ?",
                (account_id,),
            ).fetchall()
        ]

    active_video_ids = idea_radar_job_registry.cancel_many(video_ids)
    cancelled_job_count = len(active_video_ids)

    try:
        with sqlite3.connect(database_path) as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute('''
                DELETE FROM douyin_benchmark_video_analysis
                WHERE video_id IN (
                    SELECT id FROM douyin_benchmark_videos WHERE account_id = ?
                )
            ''', (account_id,))
            analysis_count = max(cursor.rowcount, 0)
            cursor.execute('''
                DELETE FROM douyin_benchmark_video_transcripts
                WHERE video_id IN (
                    SELECT id FROM douyin_benchmark_videos WHERE account_id = ?
                )
            ''', (account_id,))
            transcript_count = max(cursor.rowcount, 0)
            cursor.execute(
                "DELETE FROM douyin_benchmark_videos WHERE account_id = ?",
                (account_id,),
            )
            video_count = max(cursor.rowcount, 0)
            cursor.execute(
                "DELETE FROM douyin_benchmark_accounts WHERE id = ?",
                (account_id,),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("删除对标账号失败")
            conn.commit()
    except Exception:
        idea_radar_job_registry.uncancel_many(active_video_ids)
        raise

    return {
        "id": account_id,
        "nickname": account["nickname"],
        "homepage_url": account["homepage_url"],
        "deleted_videos": video_count,
        "deleted_analyses": analysis_count,
        "deleted_transcripts": transcript_count,
        "cancelled_jobs": cancelled_job_count,
    }


def save_douyin_benchmark_sync(account_id, data):
    return benchmark_repository.save_sync(get_db_path(), account_id, data)


def save_douyin_benchmark_error(account_id, error_message):
    benchmark_repository.save_error(get_db_path(), account_id, error_message)


def sync_one_douyin_benchmark(homepage_url, cookie_file, max_videos=20):
    homepage_url = normalize_douyin_user_url(homepage_url)
    if not homepage_url:
        raise ValueError("无效的抖音用户主页链接")
    account_id = upsert_douyin_benchmark(homepage_url)
    existing_urls = get_douyin_benchmark_video_urls(account_id)
    sync_data = asyncio.run(scrape_douyin_benchmark(
        homepage_url,
        cookie_file=cookie_file,
        max_videos=max_videos,
        existing_video_urls=existing_urls
    ))
    stats = save_douyin_benchmark_sync(account_id, sync_data)
    return {"id": account_id, "sync": stats, "account": sync_data}


def parse_keywords_payload(value):
    if isinstance(value, list):
        keywords = value
    else:
        keywords = re.split(r"[,，\n\r]+", str(value or ""))
    return [item.strip() for item in keywords if item and item.strip()]


def split_title_parts(title):
    text = re.sub(r"\s+", " ", title or "").strip()
    if not text:
        return []
    parts = re.split(r"[，。！？!?；;\n\r]+", text)
    return [part.strip() for part in parts if part.strip()]


def is_count_like_text(value):
    text = re.sub(r"\s+", " ", value or "").strip()
    return bool(re.fullmatch(r"[\d.,]+\s*[万wW]?", text))


def pick_analysis_source_text(video):
    raw_data = {}
    try:
        raw_data = json.loads(video.get("raw_data") or "{}")
    except Exception:
        raw_data = {}
    candidates = [
        video.get("title"),
        raw_data.get("title"),
        raw_data.get("raw_text"),
        raw_data.get("text"),
    ]
    for value in candidates:
        text = re.sub(r"\s+", " ", value or "").strip()
        if text and not is_count_like_text(text) and not text.startswith("热门"):
            return text
    return "该作品暂未同步到标题/文案"


def is_douyin_analysis_stale(analysis, video):
    if not analysis:
        return False
    parsed = parse_douyin_video_analysis(analysis)
    hook = parsed.get("hook") or ""
    summary = parsed.get("summary") or ""
    if is_count_like_text(hook):
        return True
    if re.search(r"围绕「[\d.,]+\s*[万wW]?」", summary):
        return True
    source_text = pick_analysis_source_text(video)
    return source_text != "该作品暂未同步到标题/文案" and hook and hook not in source_text


def pick_keywords(text):
    candidates = [
        "AI", "智能体", "Agent", "Coze", "Obsidian", "Hermes", "Claude", "抖音", "视频号",
        "副业", "自媒体", "知识库", "工作流", "私域", "变现", "获客", "剪辑", "口播",
        "爆款", "账号", "流量", "工具", "教程", "开源", "成本", "模型", "算力", "提示词"
    ]
    found = []
    lower_text = (text or "").lower()
    for word in candidates:
        if word.lower() in lower_text and word not in found:
            found.append(word)
    hashtags = re.findall(r"#([^#\s，。！？!?,;；]+)", text or "")
    for tag in hashtags:
        if tag and tag not in found:
            found.append(tag)
    return found[:8]


def generate_douyin_video_analysis_fallback(video):
    source_text = pick_analysis_source_text(video)
    parts = split_title_parts(source_text)
    keywords = pick_keywords(source_text)
    hook = parts[0] if parts else source_text[:40]
    core = parts[1] if len(parts) > 1 else f"围绕「{hook}」展开观点，用具体问题吸引目标用户继续看。"
    pain_points = [
        "观众可能正在寻找更高效的方法或工具",
        "观众需要把抽象概念变成可执行步骤",
    ]
    if any(word in source_text for word in ["成本", "价格", "便宜", "贵"]):
        pain_points.insert(0, "用户关心成本下降后自己能抓住什么机会")
    if any(word in source_text for word in ["学", "教程", "入门", "路径"]):
        pain_points.insert(0, "用户想知道从哪里开始学、按什么路径学")

    viral_points = [
        "选题有明确对象和具体问题，适合做开头钩子",
        "可以拆成短句字幕和重点弹窗，降低理解成本",
    ]
    if keywords:
        viral_points.append(f"关键词可前置：{' / '.join(keywords[:4])}")

    reusable_points = [
        "用“现象 -> 原因 -> 普通人行动”的结构复刻",
        "保留一个具体例子，再给出三条可执行路径",
        "结尾用清单式行动建议，引导收藏或评论",
    ]
    script_suggestions = [
        f"开头：最近我看到一个信号，{hook}",
        "中段：这件事真正影响普通人的地方，不是新闻本身，而是成本和门槛变化",
        "结尾：如果你也想跟上，可以先从一个工具、一个教程、一个项目开始练",
    ]

    analysis = {
        "basis": "metadata",
        "keywords": keywords,
        "structure": [
            {"label": "开头钩子", "content": hook},
            {"label": "核心观点", "content": core},
            {"label": "论证/案例", "content": "用行业变化、工具案例或个人体验证明观点。"},
            {"label": "行动引导", "content": "给出可执行路径，让用户知道下一步做什么。"},
        ],
        "pain_points": pain_points[:4],
        "viral_points": viral_points[:4],
        "reusable_points": reusable_points,
        "script_suggestions": script_suggestions,
    }

    return {
        "analysis_type": "metadata",
        "summary": f"这是一个围绕「{hook}」展开的知识分享选题，适合复刻为观点口播或教程切片。",
        "hook": hook,
        "core_viewpoint": core,
        "pain_points": pain_points[:4],
        "viral_points": viral_points[:4],
        "reusable_points": reusable_points,
        "script_suggestions": script_suggestions,
        "raw_analysis": analysis,
    }


def build_douyin_analysis_prompt(video):
    raw_data = {}
    try:
        raw_data = json.loads(video.get("raw_data") or "{}")
    except Exception:
        raw_data = {}
    return build_video_analysis_prompt(video, pick_analysis_source_text(video), raw_data)


def get_codex_analysis_schema():
    return video_analysis_schema()


def load_json_object(text):
    return agent_load_json_object(text)


def normalize_text_list(value, limit=5):
    if isinstance(value, list):
        items = value
    elif isinstance(value, str) and value.strip():
        items = re.split(r"[\n；;]+", value)
    else:
        items = []
    result = []
    for item in items:
        text = re.sub(r"\s+", " ", str(item)).strip()
        if text and text not in result:
            result.append(text)
    return result[:limit]


def normalize_codex_video_analysis(video, codex_data):
    source_text = pick_analysis_source_text(video)
    hook = re.sub(r"\s+", " ", str(codex_data.get("hook") or "")).strip()
    if not hook or is_count_like_text(hook):
        parts = split_title_parts(source_text)
        hook = parts[0] if parts else source_text[:40]

    raw_analysis = {
        "basis": "codex_cli",
        "keywords": normalize_text_list(codex_data.get("keywords"), 8),
        "structure": codex_data.get("structure") or [],
        "source_text": source_text,
    }
    return {
        "analysis_type": "codex_cli",
        "summary": re.sub(r"\s+", " ", str(codex_data.get("summary") or "")).strip(),
        "hook": hook,
        "core_viewpoint": re.sub(r"\s+", " ", str(codex_data.get("core_viewpoint") or "")).strip(),
        "pain_points": normalize_text_list(codex_data.get("pain_points"), 5),
        "viral_points": normalize_text_list(codex_data.get("viral_points"), 5),
        "reusable_points": normalize_text_list(codex_data.get("reusable_points"), 5),
        "script_suggestions": normalize_text_list(codex_data.get("script_suggestions"), 5),
        "raw_analysis": raw_analysis,
    }


def generate_douyin_video_analysis_by_codex(video):
    prompt = build_douyin_analysis_prompt(video)
    timeout = int(get_runtime_setting(
        "codexAnalysisTimeout", "codex_timeout", env="CODEX_ANALYSIS_TIMEOUT_SECONDS", default="180"
    ))
    codex_cmd = resolve_executable(
        get_runtime_setting("codexCliPath", "codex_cli_path", env="CODEX_CLI_PATH", default="codex"),
        "Codex CLI",
    )
    codex_model = get_runtime_setting(
        "codexAnalysisModel", "codex_model", env="CODEX_ANALYSIS_MODEL", default="gpt-5.4-mini"
    )

    with tempfile.TemporaryDirectory(prefix="douyin-codex-analysis-") as tmp_dir:
        schema_path = Path(tmp_dir) / "schema.json"
        output_path = Path(tmp_dir) / "result.json"
        schema_path.write_text(json.dumps(get_codex_analysis_schema(), ensure_ascii=False), encoding="utf-8")

        command = [
            codex_cmd,
            "exec",
            "--model",
            codex_model,
            "--sandbox",
            "read-only",
            "--ephemeral",
            "--ignore-rules",
            "--cd",
            str(BASE_DIR),
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            "-",
        ]
        completed = subprocess.run(
            command,
            input=prompt,
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"Codex CLI failed: {completed.stderr[-2000:] or completed.stdout[-2000:]}")

        output_text = output_path.read_text(encoding="utf-8") if output_path.exists() else completed.stdout
        codex_data = load_json_object(output_text)
        return normalize_codex_video_analysis(video, codex_data)


def generate_douyin_video_analysis(video):
    try:
        return generate_douyin_video_analysis_by_codex(video)
    except Exception as e:
        analysis = generate_douyin_video_analysis_fallback(video)
        analysis["analysis_type"] = "metadata_fallback"
        raw_analysis = analysis.get("raw_analysis") or {}
        raw_analysis["codex_error"] = str(e)
        analysis["raw_analysis"] = raw_analysis
        return analysis


def save_douyin_video_analysis(video_id, analysis):
    ensure_douyin_benchmark_tables()
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO douyin_benchmark_video_analysis
            (video_id, analysis_type, summary, hook, core_viewpoint, pain_points,
             viral_points, reusable_points, script_suggestions, raw_analysis)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(video_id) DO UPDATE SET
            analysis_type = excluded.analysis_type,
            summary = excluded.summary,
            hook = excluded.hook,
            core_viewpoint = excluded.core_viewpoint,
            pain_points = excluded.pain_points,
            viral_points = excluded.viral_points,
            reusable_points = excluded.reusable_points,
            script_suggestions = excluded.script_suggestions,
            raw_analysis = excluded.raw_analysis,
            updated_at = CURRENT_TIMESTAMP
        ''', (
            video_id,
            analysis.get("analysis_type") or "metadata",
            analysis.get("summary"),
            analysis.get("hook"),
            analysis.get("core_viewpoint"),
            json.dumps(analysis.get("pain_points") or [], ensure_ascii=False),
            json.dumps(analysis.get("viral_points") or [], ensure_ascii=False),
            json.dumps(analysis.get("reusable_points") or [], ensure_ascii=False),
            json.dumps(analysis.get("script_suggestions") or [], ensure_ascii=False),
            json.dumps(analysis.get("raw_analysis") or {}, ensure_ascii=False),
        ))
        conn.commit()


def parse_douyin_video_analysis(row):
    if not row:
        return None
    item = dict(row)
    for key in ("pain_points", "viral_points", "reusable_points", "script_suggestions"):
        try:
            item[key] = json.loads(item.get(key) or "[]")
        except Exception:
            item[key] = []
    try:
        item["raw_analysis"] = json.loads(item.get("raw_analysis") or "{}")
    except Exception:
        item["raw_analysis"] = {}
    return item


def parse_idea_radar_transcript(row):
    return idea_radar_repository.parse_transcript(row)


def get_idea_radar_transcript(video_id):
    return idea_radar_repository.get_transcript(get_db_path(), video_id)


def update_idea_radar_transcript(video_id, **values):
    idea_radar_repository.update_transcript(get_db_path(), video_id, **values)


def update_idea_radar_progress(video_id, stage, percent, message, status="processing", **values):
    idea_radar_job_registry.ensure_not_cancelled(video_id)
    current = get_idea_radar_transcript(video_id) or {}
    logs = list(current.get("progress_log") or [])
    percent = max(0, min(int(round(percent or 0)), 100))
    last_entry = logs[-1] if logs else {}
    if last_entry.get("message") != message or last_entry.get("percent") != percent:
        logs.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "stage": stage,
            "percent": percent,
            "message": message,
        })
        logs = logs[-60:]
    payload = {
        "status": status,
        "stage": stage,
        "progress_percent": percent,
        "progress_message": message,
        "progress_log": logs,
        **values,
    }
    update_idea_radar_transcript(video_id, **payload)
    print(f"[观点雷达 {video_id}] {percent}% {message}", flush=True)


def write_netscape_cookie_file(storage_state_path, output_path):
    return idea_radar_media.write_netscape_cookie_file(storage_state_path, output_path)


def run_streaming_command(command, timeout, on_line=None, idle_timeout=None):
    backend_log(f"run command: {' '.join(str(item) for item in command)}")
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    line_queue = Queue()

    def read_output():
        try:
            for line in process.stdout or []:
                line_queue.put(line.rstrip())
        finally:
            line_queue.put(None)

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    output = []
    deadline = time.time() + timeout
    last_output_at = time.time()
    stream_closed = False
    while not stream_closed or process.poll() is None:
        if time.time() > deadline:
            process.kill()
            raise subprocess.TimeoutExpired(command, timeout)
        if idle_timeout and time.time() - last_output_at > idle_timeout:
            process.kill()
            raise TimeoutError(f"command produced no output for {idle_timeout} seconds")
        try:
            line = line_queue.get(timeout=0.25)
        except Empty:
            continue
        if line is None:
            stream_closed = True
            continue
        output.append(line)
        last_output_at = time.time()
        backend_log(f"command output: {line}")
        if on_line:
            try:
                on_line(line)
            except Exception:
                process.kill()
                process.wait()
                raise
    return process.wait(), output


def download_douyin_video_with_ytdlp(video_url, output_dir, cookie_file, progress_callback=None):
    output_template = str(Path(output_dir) / "source.%(ext)s")
    command = [
        sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-playlist", "--no-warnings",
        "--socket-timeout", "20", "--retries", "2", "--fragment-retries", "2",
        "--newline", "--progress-template",
        "download:%(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s",
        "--merge-output-format", "mp4", "-o", output_template,
    ]
    ffmpeg_dir = os.environ.get("SAU_FFMPEG_DIR")
    if ffmpeg_dir and Path(ffmpeg_dir).exists():
        command.extend(["--ffmpeg-location", ffmpeg_dir])
    if cookie_file:
        command.extend(["--cookies", str(cookie_file)])
    command.append(video_url)
    def handle_line(line):
        match = re.search(r"download:\s*([\d.]+)%\|([^|]*)\|([^|]*)", line)
        if not match or not progress_callback:
            return
        percent = float(match.group(1))
        speed = match.group(2).strip()
        eta = match.group(3).strip()
        details = [f"下载 {percent:.1f}%"]
        if speed and speed != "N/A":
            details.append(speed)
        if eta and eta != "N/A":
            details.append(f"剩余 {eta}")
        progress_callback(percent, " · ".join(details))

    backend_log(f"yt-dlp ffmpeg dir: {ffmpeg_dir or '<none>'}")
    returncode, output = run_streaming_command(command, timeout=180, idle_timeout=60, on_line=handle_line)
    candidates = sorted(Path(output_dir).glob("source.*"))
    if returncode != 0 or not candidates:
        detail = "\n".join(output[-30:]) or "yt-dlp 下载失败"
        raise RuntimeError(detail)
    if progress_callback:
        progress_callback(100, "视频下载完成")
    return candidates[0]


def download_douyin_video_with_ytdlp(video_url, output_dir, cookie_file, progress_callback=None):
    return idea_radar_media.download_with_ytdlp(
        video_url,
        output_dir,
        cookie_file,
        progress_callback=progress_callback,
        log=backend_log,
    )


async def download_douyin_video_with_playwright(
    video_url, output_path, storage_state_path=None, progress_callback=None
):
    return await idea_radar_media.download_with_playwright(
        video_url,
        output_path,
        storage_state_path=storage_state_path,
        progress_callback=progress_callback,
    )


def download_douyin_video(video_url, work_dir, progress_callback=None):
    return idea_radar_media.download_douyin_video(
        video_url,
        work_dir,
        base_dir=BASE_DIR,
        latest_cookie_file=latest_douyin_cookie_file,
        progress_callback=progress_callback,
        log=backend_log,
    )


def transcribe_idea_radar_media(media_path, progress_callback=None):
    model = os.environ.get("IDEA_RADAR_WHISPER_MODEL", "base")
    script_path = Path(BASE_DIR / "scripts" / "whisper_asr.py")
    command = [
        sys.executable, str(script_path), "--input", str(media_path),
        "--model", model, "--language", "zh", "--device", "cpu", "--compute-type", "int8",
    ]
    result = {}

    def handle_line(line):
        nonlocal result
        try:
            payload = json.loads(line)
        except Exception:
            return
        if payload.get("type") == "progress":
            if progress_callback:
                progress_callback(
                    payload.get("percent") or 0,
                    payload.get("message") or "正在识别视频文案",
                    payload,
                )
        elif "ok" in payload:
            result = payload

    returncode, output = run_streaming_command(command, timeout=1800, on_line=handle_line)
    if returncode != 0 or not result.get("ok"):
        detail = result.get("error") or "\n".join(output[-30:]) or "Whisper 转写失败"
        raise RuntimeError(detail[-2000:])
    return result["data"], model


def transcribe_idea_radar_media(media_path, progress_callback=None):
    return idea_radar_media.transcribe_media(
        media_path,
        progress_callback=progress_callback,
        log=backend_log,
    )


def clean_transcript_text(text):
    return idea_radar_media.clean_transcript_text(text)


def parse_metric_number(value):
    text = re.sub(r"\s+", "", str(value or "")).replace(",", "")
    if not text:
        return 0
    match = re.search(r"([\d.]+)", text)
    if not match:
        return 0
    number = float(match.group(1))
    if "万" in text or "w" in text.lower():
        number *= 10000
    return int(number)


def list_idea_radar_videos(limit=80):
    return benchmark_repository.list_idea_radar_videos(
        get_db_path(), parse_metric_number, limit
    )


def classify_idea_theme(text):
    checks = [
        (["变现", "赚钱", "收入", "交付", "获客", "会员费", "分账"], "AI 变现闭环"),
        (["Skill", "智能体", "Agent", "工作流", "自审", "预测", "蒸馏"], "AI 生产系统"),
        (["开源", "Github", "GitHub", "项目", "CLI", "工具"], "开源工具机会"),
        (["第二大脑", "知识库", "聊天记录", "备份", "数字资产"], "数字资产沉淀"),
        (["入门", "小白", "教程", "学习", "电脑", "配置"], "普通人入门路径"),
        (["职业", "工程师", "GEO", "优化", "部署"], "AI 新职业地图"),
    ]
    for keywords, label in checks:
        if any(keyword.lower() in text.lower() for keyword in keywords):
            return label
    return "AI 机会识别"


def pick_evidence_type(text, like_count):
    types = []
    if parse_metric_number(like_count) >= 10000:
        types.append("高赞验证")
    if any(word in text for word in ["开源", "公开", "收入公开"]):
        types.append("公开证据")
    if any(word in text for word in ["全链路", "拆解", "教程", "指南"]):
        types.append("方法拆解")
    if any(word in text for word in ["我", "自用", "实测", "体验"]):
        types.append("亲身实验")
    return types or ["标题信号"]


def build_migration_angles(theme, text):
    if theme == "AI 变现闭环":
        return [
            "把 AI 热点翻译成普通人能执行的赚钱链路",
            "从工具介绍升级成开发、获客、交付的闭环拆解",
            "用自己的发布和复盘数据证明内容系统能产生反馈",
        ]
    if theme == "AI 生产系统":
        return [
            "把单个工具改写成一套可复用 Skill 资产",
            "用对标研究、观点提炼、发布复盘组成个人内容流水线",
            "展示一个真实任务如何被 AI 工作流接管",
        ]
    if theme == "开源工具机会":
        return [
            "把开源项目从技术新闻改写成普通人的机会窗口",
            "用项目增长速度、使用场景和替代对象讲清趋势",
            "输出一条从发现项目到内容选题的研究路径",
        ]
    if theme == "数字资产沉淀":
        return [
            "把聊天记录、选题、复盘沉淀成未来可调用资产",
            "证明数据不是看板，而是下一条内容的原料",
            "从资料收藏升级成第二大脑的运行机制",
        ]
    if theme == "普通人入门路径":
        return [
            "把入门问题拆成最低成本的第一步",
            "反对先买设备、先报课，强调先跑通一个真实任务",
            "用对标账号样本生成一条新手路线图",
        ]
    return [
        "把抽象趋势改写成普通人的具体行动",
        "从对标账号中提炼可迁移观点，而不是复制标题",
        "把热点变成自己的长期栏目和方法论资产",
    ]


def generate_idea_radar(video, target_direction=None):
    target = target_direction or "AI 生产系统研究员"
    source_text = pick_analysis_source_text(video)
    theme = classify_idea_theme(source_text)
    account = video.get("account_name") or "对标账号"
    like_count = video.get("like_count") or "0"
    evidence_types = pick_evidence_type(source_text, like_count)
    migration_angles = build_migration_angles(theme, source_text)
    hook = split_title_parts(source_text)[0] if split_title_parts(source_text) else source_text[:48]

    audience_anxieties = [
        "收藏了很多 AI 工具，但不知道怎么变成自己的产出",
        "知道热点很热，却不知道普通人能抓住什么机会",
        "会做单点尝试，但缺少从选题、制作、发布到复盘的闭环",
    ]
    if theme == "AI 变现闭环":
        audience_anxieties.insert(0, "想用 AI 赚钱，但不知道从开发、获客到交付怎么串起来")
    elif theme == "AI 生产系统":
        audience_anxieties.insert(0, "想让 AI 真正接管工作流，而不是只停留在工具尝鲜")
    elif theme == "数字资产沉淀":
        audience_anxieties.insert(0, "每天产生很多信息，却没有沉淀成可复用资产")

    asset_label = {
        "AI 变现闭环": "变现闭环",
        "AI 生产系统": "Skill 资产库",
        "开源工具机会": "机会雷达",
        "数字资产沉淀": "第二大脑资产",
        "普通人入门路径": "入门路径",
        "AI 新职业地图": "新职业地图",
        "AI 机会识别": "机会翻译系统",
    }.get(theme, "观点迁移能力")

    contrarian = {
        "AI 变现闭环": "AI 变现的关键不是会多少工具，而是有没有一条从问题到交付的闭环。",
        "AI 生产系统": "真正值钱的不是 AI 工具清单，而是你沉淀下来的 Skill 资产库。",
        "开源工具机会": "开源项目不是技术圈新闻，而是普通人提前发现需求变化的雷达。",
        "数字资产沉淀": "数据不是用来看过去的，而是用来生产下一条内容的。",
        "普通人入门路径": "AI 入门不要先买设备或报课，先跑通一个真实任务。",
    }.get(theme, "爆款不是热点本身，而是把热点翻译成普通人的机会。")

    titles = [
        f"我拆了{account}一条高赞作品，发现爆的不是话题，是{asset_label}",
        f"做 AI 账号没流量，不是工具不够多，是你没有自己的{asset_label}",
        f"别再追 AI 热点了，把热点变成你的{asset_label}才值钱",
        f"为什么这条能拿到{like_count}赞？因为它讲中了普通人的机会焦虑",
        f"普通人做 AI，最该沉淀的不是教程，而是一套可复用流程",
    ]

    opening_script = (
        f"我刚拆了一条对标作品，来自{account}，点赞大约是{like_count}。\n"
        f"表面上它讲的是：{hook}。\n"
        f"但真正让人停下来的，不是这个话题本身，而是它背后的机会翻译：{contrarian}\n"
        f"这给我的启发是，如果我的账号定位是{target}，我就不能只搬运工具，"
        "而要把对标、观点、证据和行动路径串成一条内容生产系统。"
    )
    personalized_script = (
        f"最近我拆了一条来自{account}的高赞作品，点赞大约是{like_count}。\n"
        f"它表面讲的是：{hook}。\n\n"
        f"但如果站在我这个「{target}」的身份来看，我真正想提醒你的不是这个热点本身，"
        f"而是它背后的一个变化：{contrarian}\n\n"
        "很多人做内容，会停在追热点、搬工具、改标题这一步。可真正能长期跑出来的账号，"
        "一定是在做一件事：把外部变化翻译成自己受众能执行的路径。\n\n"
        f"所以这条内容我会这样迁移：第一，先讲清楚这个变化服务谁；第二，给出一个最小交付物，"
        f"比如{migration_angles[0]}；第三，用一次真实发布或一个小样本去验证，而不是直接 All in。\n\n"
        "如果你也在做 AI 或自媒体，不要只收藏爆款。你要问的是：这条内容里的结构、痛点和证据，"
        "能不能变成我自己的选题、脚本和交付物。能迁移，才真的值得对标。"
    )

    return {
        "radar_type": "metadata",
        "target_direction": target,
        "source": {
            "id": video.get("id"),
            "account_name": account,
            "title": video.get("title"),
            "video_url": video.get("video_url"),
            "like_count": like_count,
            "like_score": parse_metric_number(like_count),
            "cover_url": video.get("cover_url"),
        },
        "viral_theme": theme,
        "audience_anxieties": audience_anxieties[:4],
        "contrarian_viewpoint": contrarian,
        "evidence_types": evidence_types,
        "migration_angles": migration_angles,
        "recommended_titles": titles,
        "opening_script": opening_script,
        "personalized_script": personalized_script,
        "formula": "爆款 = 人群焦虑 × 反常识观点 × 可验证证据 × 可迁移行动",
    }


def get_transcript_radar_schema():
    return transcript_radar_schema()


def build_transcript_radar_prompt(video, transcript, target_direction):
    return build_idea_radar_prompt(video, transcript, target_direction)


def run_codex_cli_structured(prompt, schema, timeout=None):
    timeout = timeout or int(get_runtime_setting(
        "codexAnalysisTimeout", "codex_timeout", env="CODEX_ANALYSIS_TIMEOUT_SECONDS", default="180"
    ))
    configured_codex_cmd = get_runtime_setting(
        "codexCliPath", "codex_cli_path", env="CODEX_CLI_PATH", default="codex"
    )
    codex_model = get_runtime_setting(
        "codexAnalysisModel", "codex_model", env="CODEX_ANALYSIS_MODEL", default="gpt-5.4-mini"
    )
    return agent_run_codex_cli_structured(
        prompt,
        schema,
        base_dir=BASE_DIR,
        codex_cmd=configured_codex_cmd,
        codex_model=codex_model,
        timeout=timeout,
        log=backend_log,
    )


def get_task_agent_model(task_name="viralAnalysis", settings=None):
    return agent_get_task_agent_model(task_name, settings or load_runtime_settings())


def call_hermes_structured(prompt, schema, model_config=None, timeout=None):
    settings = load_runtime_settings()
    return agent_call_hermes_structured(
        prompt,
        schema,
        settings=settings,
        model_config=model_config,
        timeout=timeout,
        log=backend_log,
    )


def run_codex_structured(prompt, schema, timeout=None):
    return call_hermes_structured(prompt, schema, timeout=timeout)


def generate_identity_script(identity_profile, radar_result, benchmark_analysis=None):
    settings = load_runtime_settings()
    return agent_call_hermes_structured(
        build_identity_script_prompt(identity_profile, radar_result, benchmark_analysis),
        identity_script_schema(),
        settings=settings,
        task_name="scriptGeneration",
        timeout=get_hermes_settings(settings)["timeout"],
        log=backend_log,
    )


def load_idea_radar_video(video_id):
    return benchmark_repository.get_video(get_db_path(), video_id, include_account=True)


def run_idea_radar_pipeline(video_id, target_direction, force_transcription=False):
    return run_idea_radar_pipeline_core(
        video_id,
        target_direction,
        force_transcription=force_transcription,
        load_video=load_idea_radar_video,
        get_transcript=get_idea_radar_transcript,
        update_progress=update_idea_radar_progress,
        download_video=download_douyin_video,
        transcribe_media=transcribe_idea_radar_media,
        clean_transcript=clean_transcript_text,
        build_prompt=build_transcript_radar_prompt,
        schema_factory=get_transcript_radar_schema,
        run_structured=run_codex_structured,
        get_agent_model=get_task_agent_model,
        parse_metric_number=parse_metric_number,
        registry=idea_radar_job_registry,
    )


def start_idea_radar_pipeline(video_id, target_direction, force=False, force_transcription=False):
    current = get_idea_radar_transcript(video_id)
    started = start_pipeline_task(
        video_id,
        target_direction,
        current=current,
        registry=idea_radar_job_registry,
        update_transcript=update_idea_radar_transcript,
        pipeline_fn=run_idea_radar_pipeline,
        force=force,
        force_transcription=force_transcription,
    )
    return started or get_idea_radar_transcript(video_id)


def save_publish_record(platform_type, title, tags, file_list, account_list, status, error_message=None,
                          views=0, likes=0, comments=0, shares=0, video_url=None):
    return publish_repository.save_record(
        get_db_path(),
        platform_type,
        title,
        tags,
        file_list,
        account_list,
        status,
        error_message,
        views,
        likes,
        comments,
        shares,
        video_url,
    )


def validate_account_files_for_platform(platform_type, account_list):
    return account_repository.validate_account_files_for_platform(
        get_db_path(),
        platform_type,
        account_list,
    )


def publish_video_payload(payload):
    return publish_video_service(
        payload,
        validate_accounts=validate_account_files_for_platform,
        publishers={
            1: post_video_xhs,
            2: post_video_tencent,
            3: post_video_DouYin,
            4: post_video_ks,
        },
        save_record=save_publish_record,
    )


ensure_publish_records_table()
ensure_douyin_benchmark_tables()
ensure_douyin_own_tables()

# 获取当前目录（假设 index.html 和 assets 在这里）
current_dir = os.path.dirname(os.path.abspath(__file__))

# 处理所有静态资源请求（未来打包用）
@app.route('/assets/<filename>')
def custom_static(filename):
    return send_from_directory(os.path.join(current_dir, 'assets'), filename)

# 处理 favicon.ico 静态资源（未来打包用）
@app.route('/favicon.ico')
def favicon(filename):
    return send_from_directory(os.path.join(current_dir, 'assets'), 'favicon.ico')

# （未来打包用）
@app.route('/')
def hello_world():  # put application's code here
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({
            "code": 200,
            "data": None,
            "msg": "No file part in the request"
        }), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({
            "code": 200,
            "data": None,
            "msg": "No selected file"
        }), 400
    try:
        # 保存文件到指定位置
        uuid_v1 = uuid.uuid1()
        print(f"UUID v1: {uuid_v1}")
        filepath = Path(BASE_DIR / "videoFile" / f"{uuid_v1}_{file.filename}")
        file.save(filepath)
        return jsonify({"code":200,"msg": "File uploaded successfully", "data": f"{uuid_v1}_{file.filename}"}), 200
    except Exception as e:
        return jsonify({"code":200,"msg": str(e),"data":None}), 500

@app.route('/getFile', methods=['GET'])
def get_file():
    # 获取 filename 参数
    filename = request.args.get('filename')

    if not filename:
        return {"error": "filename is required"}, 400

    # 防止路径穿越攻击
    if '..' in filename or filename.startswith('/'):
        return {"error": "Invalid filename"}, 400

    # 拼接完整路径
    file_path = str(Path(BASE_DIR / "videoFile"))

    # 返回文件
    return send_from_directory(file_path,filename)


@app.route('/uploadSave', methods=['POST'])
def upload_save():
    if 'file' not in request.files:
        return jsonify({
            "code": 400,
            "data": None,
            "msg": "No file part in the request"
        }), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({
            "code": 400,
            "data": None,
            "msg": "No selected file"
        }), 400

    # 获取表单中的自定义文件名（可选）
    custom_filename = request.form.get('filename', None)
    if custom_filename:
        filename = custom_filename + "." + file.filename.split('.')[-1]
    else:
        filename = file.filename

    try:
        # 生成 UUID v1
        uuid_v1 = uuid.uuid1()
        print(f"UUID v1: {uuid_v1}")

        # 构造文件名和路径
        final_filename = f"{uuid_v1}_{filename}"
        filepath = Path(BASE_DIR / "videoFile" / f"{uuid_v1}_{filename}")

        # 保存文件
        file.save(filepath)

        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                                INSERT INTO file_records (filename, filesize, file_path)
            VALUES (?, ?, ?)
                                ''', (filename, round(float(os.path.getsize(filepath)) / (1024 * 1024),2), final_filename))
            conn.commit()
        print("[OK] 上传文件已记录")

        return jsonify({
            "code": 200,
            "msg": "File uploaded and saved successfully",
            "data": {
                "filename": filename,
                "filepath": final_filename
            }
        }), 200

    except Exception as e:
        return jsonify({
            "code": 500,
            "msg": str("upload failed!"),
            "data": None
        }), 500

@app.route('/getFiles', methods=['GET'])
def get_all_files():
    try:
        # 使用 with 自动管理数据库连接
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row  # 允许通过列名访问结果
            cursor = conn.cursor()

            # 查询所有记录
            cursor.execute("SELECT * FROM file_records")
            rows = cursor.fetchall()

            # 将结果转为字典列表
            data = [dict(row) for row in rows]

        return jsonify({
            "code": 200,
            "msg": "success",
            "data": data
        }), 200
    except Exception as e:
        return jsonify({
            "code": 500,
            "msg": str("get file failed!"),
            "data": None
        }), 500


@app.route("/getValidAccounts",methods=['GET'])
async def getValidAccounts():
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        SELECT * FROM user_info''')
        rows = cursor.fetchall()
        rows_list = [list(row) for row in rows]
        safe_print("\n[INFO] 当前数据表内容：")
        for row in rows:
            safe_print(row)
        for row in rows_list:
            flag = await check_cookie(row[1],row[2])
            if not flag:
                row[4] = 0
                cursor.execute('''
                UPDATE user_info 
                SET status = ? 
                WHERE id = ?
                ''', (0,row[0]))
                conn.commit()
                safe_print("[OK] 用户状态已更新")
        for row in rows:
            safe_print(row)
        return jsonify(
                        {
                            "code": 200,
                            "msg": None,
                            "data": rows_list
                        }),200

@app.route('/getPublishRecords', methods=['GET'])
def get_publish_records():
    try:
        records = publish_repository.list_records(get_db_path())
        return jsonify({"code": 200, "msg": "success", "data": records}), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500



@app.route('/publish/updateStats', methods=['POST'])
def update_publish_stats():
    """手动更新某条发布记录的流量数据"""
    try:
        data = request.get_json()
        record_id = data.get('id')
        if not record_id:
            return jsonify({"code": 400, "msg": "缺少记录ID"}), 400

        fields = publish_repository.update_stats(get_db_path(), record_id, data)
        if not fields:
            return jsonify({"code": 400, "msg": "没有需要更新的字段"}), 400
        return jsonify({"code": 200, "msg": "更新成功", "data": fields}), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/publish/batchUpdateStats', methods=['POST'])
def batch_update_publish_stats():
    """批量更新多条记录的流量数据（来自前端批量操作或爬取结果）"""
    try:
        data = request.get_json()
        records = data.get('records', [])
        if not records:
            return jsonify({"code": 400, "msg": "没有记录"}), 400

        updated = publish_repository.batch_update_stats(get_db_path(), records)
        return jsonify({"code": 200, "msg": f"更新成功 {updated} 条记录", "data": {"updated": updated}}), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/account/updateFollower', methods=['POST'])
def update_account_follower():
    """更新账号粉丝数"""
    try:
        data = request.get_json()
        account_id = data.get('id')
        follower_count = data.get('follower_count')
        if not account_id or follower_count is None:
            return jsonify({"code": 400, "msg": "缺少账号ID或粉丝数"}), 400

        account_repository.update_follower_count(get_db_path(), account_id, follower_count)

        return jsonify({"code": 200, "msg": "更新成功"}), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/account/followers', methods=['GET'])
def get_account_followers():
    """获取所有账号的粉丝数"""
    try:
        accounts = account_repository.list_followers(get_db_path())
        return jsonify({"code": 200, "msg": "success", "data": accounts}), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/dashboard/stats', methods=['GET'])
def get_dashboard_stats():
    try:
        ensure_publish_records_table()
        data = dashboard_stats_service(get_db_path())
        return jsonify(
            {
                "code": 200,
                "msg": "success",
                "data": data,
            }
        ), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/benchmark/douyin/accounts', methods=['POST'])
def add_douyin_benchmark_account():
    data = request.get_json() or {}
    homepage_url = data.get("homepageUrl") or data.get("homepage_url")
    try:
        cookie_file = latest_douyin_cookie_file()
        result = sync_one_douyin_benchmark(homepage_url, cookie_file, max_videos=20)
        return jsonify({"code": 200, "msg": "success", "data": {"id": result["id"], "sync": result["sync"]}}), 200
    except Exception as e:
        try:
            if homepage_url:
                save_douyin_benchmark_error(upsert_douyin_benchmark(homepage_url), str(e))
        except Exception:
            pass
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/benchmark/douyin/auto-discover', methods=['POST'])
def auto_discover_douyin_benchmark_accounts():
    payload = request.get_json() or {}
    keywords = parse_keywords_payload(payload.get("keywords") or payload.get("keyword"))
    try:
        if not keywords:
            return jsonify({"code": 400, "msg": "请填写至少一个对标关键词", "data": None}), 400
        cookie_file = latest_douyin_cookie_file()
        limit = max(1, min(int(payload.get("limit") or 5), 20))
        max_videos = max(1, min(int(payload.get("maxVideos") or payload.get("max_videos") or 10), 30))
        candidates = asyncio.run(discover_douyin_benchmark_accounts(
            keywords,
            cookie_file=cookie_file,
            limit=limit
        ))
        synced = []
        failed = []
        processed_urls = set()
        for candidate in candidates:
            homepage_url = normalize_douyin_user_url(candidate.get("homepage_url"))
            if not homepage_url or homepage_url in processed_urls:
                continue
            processed_urls.add(homepage_url)
            candidate["homepage_url"] = homepage_url
            try:
                result = sync_one_douyin_benchmark(homepage_url, cookie_file, max_videos=max_videos)
                synced.append({
                    "candidate": candidate,
                    "id": result["id"],
                    "sync": result["sync"],
                    "nickname": result["account"].get("nickname") or candidate.get("nickname"),
                    "homepage_url": homepage_url,
                })
            except Exception as exc:
                try:
                    if homepage_url:
                        save_douyin_benchmark_error(upsert_douyin_benchmark(homepage_url), str(exc))
                except Exception:
                    pass
                failed.append({
                    "candidate": candidate,
                    "homepage_url": homepage_url,
                    "error": str(exc),
                })
        return jsonify({
            "code": 200,
            "msg": "success",
            "data": {
                "keywords": keywords,
                "candidates": candidates,
                "synced": synced,
                "failed": failed,
                "summary": {
                    "found": len(candidates),
                    "synced": len(synced),
                    "failed": len(failed),
                }
            }
        }), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/own/douyin/import/preview', methods=['POST'])
def preview_own_douyin_import():
    try:
        if 'file' not in request.files:
            return jsonify({"code": 400, "msg": "请上传 CSV 或 XLSX 文件", "data": None}), 400
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
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/own/douyin/import', methods=['POST'])
def import_own_douyin_videos():
    try:
        if 'file' not in request.files:
            return jsonify({"code": 400, "msg": "请上传 CSV 或 XLSX 文件", "data": None}), 400
        account_name = request.form.get("accountName") or request.form.get("account_name") or "太阳鸟"
        parsed = parse_own_douyin_import(request.files['file'])
        result = save_own_douyin_import(parsed["rows"], account_name=account_name)
        result.update({
            "raw_count": parsed["raw_count"],
            "valid_count": parsed["valid_count"],
            "field_map": parsed["field_map"],
        })
        return jsonify({"code": 200, "msg": "success", "data": result}), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/own/douyin/videos', methods=['GET'])
def get_own_douyin_videos():
    try:
        limit = request.args.get("limit", 100)
        videos = list_own_douyin_videos(limit)
        return jsonify({"code": 200, "msg": "success", "data": videos}), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/benchmark/douyin/accounts', methods=['GET'])
def get_douyin_benchmark_accounts():
    try:
        accounts = benchmark_repository.list_accounts(get_db_path())
        return jsonify({"code": 200, "msg": "success", "data": accounts}), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/benchmark/douyin/accounts/<int:account_id>', methods=['DELETE'])
def delete_douyin_benchmark_account(account_id):
    try:
        result = delete_douyin_benchmark(account_id)
        if not result:
            return jsonify({"code": 404, "msg": "对标账号不存在", "data": None}), 404
        return jsonify({
            "code": 200,
            "msg": "删除成功",
            "data": result,
        }), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/benchmark/douyin/accounts/<int:account_id>/sync', methods=['POST'])
def sync_douyin_benchmark_account(account_id):
    try:
        cookie_file = latest_douyin_cookie_file()
        homepage_url = benchmark_repository.get_account_homepage(get_db_path(), account_id)
        if not homepage_url:
            return jsonify({"code": 404, "msg": "对标账号不存在", "data": None}), 404
        existing_urls = get_douyin_benchmark_video_urls(account_id)
        sync_data = asyncio.run(scrape_douyin_benchmark(
            homepage_url,
            cookie_file=cookie_file,
            max_videos=20,
            existing_video_urls=existing_urls
        ))
        stats = save_douyin_benchmark_sync(account_id, sync_data)
        return jsonify({"code": 200, "msg": "success", "data": {"id": account_id, "sync": stats}}), 200
    except Exception as e:
        save_douyin_benchmark_error(account_id, str(e))
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/benchmark/douyin/accounts/<int:account_id>/videos', methods=['GET'])
def get_douyin_benchmark_videos(account_id):
    try:
        videos = benchmark_repository.list_videos(get_db_path(), account_id)
        return jsonify({"code": 200, "msg": "success", "data": videos}), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/benchmark/douyin/videos/<int:video_id>/analysis', methods=['GET'])
def get_douyin_benchmark_video_analysis(video_id):
    try:
        video = benchmark_repository.get_video(get_db_path(), video_id)
        if not video:
            return jsonify({"code": 404, "msg": "作品不存在", "data": None}), 404
        row = benchmark_repository.get_analysis(get_db_path(), video_id)
        if is_douyin_analysis_stale(row, video):
            analysis = generate_douyin_video_analysis(video)
            save_douyin_video_analysis(video_id, analysis)
            row = benchmark_repository.get_analysis(get_db_path(), video_id)
        return jsonify({
            "code": 200,
            "msg": "success",
            "data": {
                "video": video,
                "analysis": parse_douyin_video_analysis(row)
            }
        }), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/benchmark/douyin/videos/<int:video_id>/analysis', methods=['POST'])
def create_douyin_benchmark_video_analysis(video_id):
    try:
        force = bool((request.get_json(silent=True) or {}).get("force"))
        video = benchmark_repository.get_video(get_db_path(), video_id)
        if not video:
            return jsonify({"code": 404, "msg": "作品不存在", "data": None}), 404
        existing = benchmark_repository.get_analysis(get_db_path(), video_id)
        if existing and not force and not is_douyin_analysis_stale(existing, video):
            return jsonify({
                "code": 200,
                "msg": "success",
                "data": parse_douyin_video_analysis(existing)
            }), 200

        analysis = generate_douyin_video_analysis(video)
        save_douyin_video_analysis(video_id, analysis)
        row = benchmark_repository.get_analysis(get_db_path(), video_id)
        return jsonify({"code": 200, "msg": "success", "data": parse_douyin_video_analysis(row)}), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/idea-radar/douyin/videos', methods=['GET'])
def get_idea_radar_videos():
    try:
        limit = request.args.get("limit", 80)
        videos = list_idea_radar_videos(limit)
        return jsonify({"code": 200, "msg": "success", "data": videos}), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/idea-radar/douyin/videos/<int:video_id>/analyze', methods=['POST'])
def analyze_idea_radar_video(video_id):
    try:
        payload = request.get_json(silent=True) or {}
        target_direction = payload.get("targetDirection") or payload.get("target_direction")
        target_direction = target_direction or "AI 生产系统研究员"
        if not load_idea_radar_video(video_id):
            return jsonify({"code": 404, "msg": "作品不存在", "data": None}), 404
        task = start_idea_radar_pipeline(
            video_id,
            target_direction,
            force=bool(payload.get("force")),
            force_transcription=bool(payload.get("forceTranscription") or payload.get("force_transcription")),
        )
        return jsonify({"code": 200, "msg": "success", "data": task}), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/idea-radar/douyin/videos/<int:video_id>/status', methods=['GET'])
def get_idea_radar_video_status(video_id):
    try:
        if not load_idea_radar_video(video_id):
            return jsonify({"code": 404, "msg": "作品不存在", "data": None}), 404
        task = get_idea_radar_status_payload(video_id, get_idea_radar_transcript)
        return jsonify({"code": 200, "msg": "success", "data": task}), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/script-generation/identity', methods=['POST'])
def create_identity_script():
    try:
        payload = request.get_json(silent=True) or {}
        identity_profile = payload.get("identityProfile") or payload.get("identity_profile") or {}
        radar_result = payload.get("radarResult") or payload.get("radar_result") or {}
        benchmark_analysis = payload.get("benchmarkAnalysis") or payload.get("benchmark_analysis") or {}
        if not isinstance(identity_profile, dict) or not identity_profile:
            return jsonify({"code": 400, "msg": "请提供创作者身份资料", "data": None}), 400
        if not isinstance(radar_result, dict) or not radar_result:
            return jsonify({"code": 400, "msg": "请提供观点雷达结果", "data": None}), 400
        script = generate_identity_script(identity_profile, radar_result, benchmark_analysis)
        return jsonify({"code": 200, "msg": "success", "data": script}), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


def mcp_collect_douyin_account(homepage_url, max_videos=20):
    cookie_file = latest_douyin_cookie_file()
    return sync_one_douyin_benchmark(homepage_url, cookie_file, max_videos=max_videos)


def mcp_list_benchmark_videos(account_id, page=1, page_size=20):
    videos = benchmark_repository.list_videos(get_db_path(), account_id)
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 20), 100))
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": videos[start:end],
        "page": page,
        "page_size": page_size,
        "total": len(videos),
    }


def mcp_analyze_benchmark_video(video_id, force=False):
    video = benchmark_repository.get_video(get_db_path(), video_id)
    if not video:
        raise ValueError("作品不存在")
    existing = benchmark_repository.get_analysis(get_db_path(), video_id)
    if existing and not force and not is_douyin_analysis_stale(existing, video):
        return parse_douyin_video_analysis(existing)
    analysis = generate_douyin_video_analysis(video)
    save_douyin_video_analysis(video_id, analysis)
    return parse_douyin_video_analysis(benchmark_repository.get_analysis(get_db_path(), video_id))


def mcp_run_idea_radar(video_id, target_direction="AI 生产系统研究员", force=False, force_transcription=False):
    if not load_idea_radar_video(video_id):
        raise ValueError("作品不存在")
    return start_idea_radar_pipeline(
        video_id,
        target_direction,
        force=force,
        force_transcription=force_transcription,
    )


def mcp_generate_my_script(identity_profile, radar_result, benchmark_analysis=None):
    return generate_identity_script(identity_profile, radar_result, benchmark_analysis or {})


def mcp_review_published_content(work_id=None, limit=50):
    videos = list_own_douyin_videos(limit)
    if work_id is not None:
        videos = [video for video in videos if str(video.get("id")) == str(work_id)]
    return review_published_content(videos)


def mcp_publish_video(**kwargs):
    return publish_video_payload(kwargs)


def mcp_tool_handlers():
    return create_tool_handlers({
        "collect_douyin_account": mcp_collect_douyin_account,
        "list_benchmark_videos": mcp_list_benchmark_videos,
        "analyze_benchmark_video": mcp_analyze_benchmark_video,
        "run_idea_radar": mcp_run_idea_radar,
        "generate_my_script": mcp_generate_my_script,
        "review_published_content": mcp_review_published_content,
        "publish_video": mcp_publish_video,
    })


@app.route('/mcp/tools', methods=['GET'])
def list_mcp_tools():
    return jsonify({"code": 200, "msg": "success", "data": describe_mcp_tools()}), 200


@app.route('/mcp/invoke', methods=['POST'])
def invoke_mcp_tool():
    payload = request.get_json(silent=True) or {}
    tool_name = str(payload.get("name") or "").strip()
    arguments = payload.get("arguments") or {}
    if not tool_name:
        return jsonify({"code": 400, "msg": "请提供 MCP 工具名称", "data": None}), 400
    if not isinstance(arguments, dict):
        return jsonify({"code": 400, "msg": "MCP 工具参数必须是对象", "data": None}), 400
    handlers = mcp_tool_handlers()
    handler = handlers.get(tool_name)
    if not handler:
        return jsonify({"code": 404, "msg": "MCP 工具不存在", "data": None}), 404
    try:
        return jsonify({"code": 200, "msg": "success", "data": handler(arguments)}), 200
    except NotImplementedError as exc:
        return jsonify({"code": 501, "msg": str(exc), "data": None}), 501
    except KeyError as exc:
        return jsonify({"code": 400, "msg": f"缺少参数：{exc}", "data": None}), 400
    except Exception as exc:
        return jsonify({"code": 500, "msg": str(exc), "data": None}), 500


@app.route('/deleteFile', methods=['GET'])
def delete_file():
    file_id = request.args.get('id')

    if not file_id or not file_id.isdigit():
        return jsonify({
            "code": 400,
            "msg": "Invalid or missing file ID",
            "data": None
        }), 400

    try:
        # 获取数据库连接
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 查询要删除的记录
            cursor.execute("SELECT * FROM file_records WHERE id = ?", (file_id,))
            record = cursor.fetchone()

            if not record:
                return jsonify({
                    "code": 404,
                    "msg": "File not found",
                    "data": None
                }), 404

            record = dict(record)

            # 删除数据库记录
            cursor.execute("DELETE FROM file_records WHERE id = ?", (file_id,))
            conn.commit()

        return jsonify({
            "code": 200,
            "msg": "File deleted successfully",
            "data": {
                "id": record['id'],
                "filename": record['filename']
            }
        }), 200

    except Exception as e:
        return jsonify({
            "code": 500,
            "msg": str("delete failed!"),
            "data": None
        }), 500

@app.route('/deleteAccount', methods=['GET'])
def delete_account():
    account_id = int(request.args.get('id'))

    try:
        # 获取数据库连接
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 查询要删除的记录
            cursor.execute("SELECT * FROM user_info WHERE id = ?", (account_id,))
            record = cursor.fetchone()

            if not record:
                return jsonify({
                    "code": 404,
                    "msg": "account not found",
                    "data": None
                }), 404

            record = dict(record)

            # 删除数据库记录
            cursor.execute("DELETE FROM user_info WHERE id = ?", (account_id,))
            conn.commit()

        return jsonify({
            "code": 200,
            "msg": "account deleted successfully",
            "data": None
        }), 200

    except Exception as e:
        return jsonify({
            "code": 500,
            "msg": str("delete failed!"),
            "data": None
        }), 500


# SSE 登录接口
@app.route('/login')
def login():
    # 1 小红书 2 视频号 3 抖音 4 快手
    type = request.args.get('type')
    # 账号名
    id = request.args.get('id')

    # 模拟一个用于异步通信的队列
    status_queue = Queue()
    active_queues[id] = status_queue

    def on_close():
        print(f"清理队列: {id}")
        del active_queues[id]
    # 启动异步任务线程
    thread = threading.Thread(target=run_async_function, args=(type,id,status_queue), daemon=True)
    thread.start()
    response = Response(sse_stream(status_queue,), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'  # 关键：禁用 Nginx 缓冲
    response.headers['Content-Type'] = 'text/event-stream'
    response.headers['Connection'] = 'keep-alive'
    return response

@app.route('/postVideo', methods=['POST'])
def postVideo():
    data = request.get_json() or {}
    print("File List:", data.get('fileList', []))
    print("Account List:", data.get('accountList', []))
    try:
        publish_video_payload(data)
    except Exception as e:
        return jsonify(
            {
                "code": 500,
                "msg": str(e),
                "data": None
            }), 500
    # 返回响应给客户端
    return jsonify(
        {
            "code": 200,
            "msg": None,
            "data": None
        }), 200


@app.route('/updateUserinfo', methods=['POST'])
def updateUserinfo():
    # 获取JSON数据
    data = request.get_json()

    # 从JSON数据中提取 type 和 userName
    user_id = data.get('id')
    type = data.get('type')
    userName = data.get('userName')
    try:
        # 获取数据库连接
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 更新数据库记录
            cursor.execute('''
                           UPDATE user_info
                           SET type     = ?,
                               userName = ?
                           WHERE id = ?;
                           ''', (type, userName, user_id))
            conn.commit()

        return jsonify({
            "code": 200,
            "msg": "account update successfully",
            "data": None
        }), 200

    except Exception as e:
        return jsonify({
            "code": 500,
            "msg": str("update failed!"),
            "data": None
        }), 500

@app.route('/postVideoBatch', methods=['POST'])
def postVideoBatch():
    data_list = request.get_json()

    if not isinstance(data_list, list):
        return jsonify({"error": "Expected a JSON array"}), 400
    for data in data_list:
        print("File List:", data.get('fileList', []))
        print("Account List:", data.get('accountList', []))
        try:
            publish_video_payload(data or {})
        except Exception as e:
            return jsonify({"code": 500, "msg": str(e), "data": None}), 500
    # 返回响应给客户端
    return jsonify(
        {
            "code": 200,
            "msg": None,
            "data": None
        }), 200

# 包装函数：在线程中运行异步函数
def run_async_function(type,id,status_queue):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        backend_log(f"account login started type={type} id={id}")
        match type:
            case '1':
                loop.run_until_complete(xiaohongshu_cookie_gen(id, status_queue))
            case '2':
                loop.run_until_complete(get_tencent_cookie(id, status_queue))
            case '3':
                loop.run_until_complete(douyin_cookie_gen(id, status_queue))
            case '4':
                loop.run_until_complete(get_ks_cookie(id, status_queue))
            case _:
                raise ValueError(f"Unsupported login type: {type}")
        backend_log(f"account login finished type={type} id={id}")
    except Exception as exc:
        backend_log(f"account login failed type={type} id={id}: {repr(exc)}\n{traceback.format_exc()}")
        status_queue.put(f"ERROR:{exc}")
        status_queue.put("500")
    finally:
        loop.close()

# SSE 流生成器函数
def sse_stream(status_queue):
    started_at = time.time()
    while True:
        if not status_queue.empty():
            msg = status_queue.get()
            yield f"data: {msg}\n\n"
            if msg in ("200", "500") or str(msg).startswith("ERROR:"):
                break
        elif time.time() - started_at > 240:
            backend_log("SSE account login timeout")
            yield "data: 500\n\n"
            break
        else:
            # 避免 CPU 占满
            time.sleep(0.1)

if __name__ == '__main__':
    ensure_core_tables()
    app.run(host='127.0.0.1', port=int(os.environ.get("SAU_BACKEND_PORT", "5409")))
