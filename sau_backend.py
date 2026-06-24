import asyncio
import base64
import hashlib
import hmac
import json
import os
import re
import sqlite3
import ssl
import subprocess
import threading
import time
import tempfile
import uuid
from pathlib import Path
from queue import Queue
from urllib.parse import urlencode, urlparse
from flask_cors import CORS
from myUtils.auth import check_cookie
from myUtils.douyin_benchmark import scrape_douyin_benchmark
from flask import Flask, request, jsonify, Response, render_template, send_from_directory
from conf import BASE_DIR
from myUtils.login import get_tencent_cookie, douyin_cookie_gen, get_ks_cookie, xiaohongshu_cookie_gen
from myUtils.postVideo import post_video_tencent, post_video_DouYin, post_video_ks, post_video_xhs

try:
    import websocket
except Exception:
    websocket = None

active_queues = {}
app = Flask(__name__)

#允许所有来源跨域访问
CORS(app)

# 限制上传文件大小为160MB
app.config['MAX_CONTENT_LENGTH'] = 160 * 1024 * 1024

def ensure_publish_records_table():
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS publish_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform_type INTEGER NOT NULL,
            title TEXT,
            tags TEXT,
            file_list TEXT,
            account_list TEXT,
            status TEXT NOT NULL,
            error_message TEXT,
            views INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            video_url TEXT DEFAULT NULL,
            last_refresh_at DATETIME DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        conn.commit()


def ensure_video_tasks_table():
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS video_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type TEXT NOT NULL,
            status TEXT NOT NULL,
            input_files TEXT,
            output_files TEXT,
            params TEXT,
            error_message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        conn.commit()


def ensure_douyin_benchmark_tables():
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS douyin_benchmark_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            homepage_url TEXT NOT NULL UNIQUE,
            nickname TEXT,
            avatar TEXT,
            bio TEXT,
            followers_count TEXT,
            following_count TEXT,
            likes_count TEXT,
            video_count TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            last_sync_at DATETIME,
            error_message TEXT,
            raw_data TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS douyin_benchmark_videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            video_url TEXT NOT NULL,
            title TEXT,
            cover_url TEXT,
            like_count TEXT,
            comment_count TEXT,
            share_count TEXT,
            collect_count TEXT,
            raw_data TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(account_id, video_url)
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS douyin_benchmark_video_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL UNIQUE,
            analysis_type TEXT NOT NULL DEFAULT 'metadata',
            summary TEXT,
            hook TEXT,
            core_viewpoint TEXT,
            pain_points TEXT,
            viral_points TEXT,
            reusable_points TEXT,
            script_suggestions TEXT,
            raw_analysis TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        conn.commit()


def latest_douyin_cookie_file():
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        cursor = conn.cursor()
        row = cursor.execute('''
        SELECT filePath FROM user_info
        WHERE type = 3 AND status = 1
        ORDER BY id DESC
        LIMIT 1
        ''').fetchone()
        return row[0] if row else None


def get_douyin_benchmark_video_urls(account_id):
    ensure_douyin_benchmark_tables()
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        rows = conn.execute(
            "SELECT video_url FROM douyin_benchmark_videos WHERE account_id = ?",
            (account_id,)
        ).fetchall()
    return [row[0] for row in rows if row and row[0]]


def upsert_douyin_benchmark(homepage_url):
    ensure_douyin_benchmark_tables()
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO douyin_benchmark_accounts (homepage_url, status)
        VALUES (?, 'pending')
        ON CONFLICT(homepage_url) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
        ''', (homepage_url,))
        conn.commit()
        row = cursor.execute(
            "SELECT id FROM douyin_benchmark_accounts WHERE homepage_url = ?",
            (homepage_url,)
        ).fetchone()
        return row[0]


def save_douyin_benchmark_sync(account_id, data):
    ensure_douyin_benchmark_tables()
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        cursor = conn.cursor()
        stats = {
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "deleted_dirty": 0,
            "scanned": len(data.get("videos") or []),
        }
        cursor.execute('''
        UPDATE douyin_benchmark_accounts
        SET nickname = ?,
            avatar = ?,
            bio = ?,
            followers_count = ?,
            following_count = ?,
            likes_count = ?,
            video_count = ?,
            status = 'success',
            last_sync_at = CURRENT_TIMESTAMP,
            error_message = NULL,
            raw_data = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        ''', (
            data.get("nickname"),
            data.get("avatar"),
            data.get("bio"),
            data.get("followers_count"),
            data.get("following_count"),
            data.get("likes_count"),
            data.get("video_count"),
            json.dumps(data.get("raw_data") or {}, ensure_ascii=False),
            account_id
        ))
        for video in data.get("videos") or []:
            video_url = video.get("video_url") or ""
            video_title = (video.get("title") or "").strip()
            if not video_url or not video_title or "source=Baiduspider" in video_url or video_title.startswith("热门"):
                stats["skipped"] += 1
                continue
            existed = cursor.execute(
                "SELECT 1 FROM douyin_benchmark_videos WHERE account_id = ? AND video_url = ?",
                (account_id, video_url)
            ).fetchone()
            cursor.execute('''
            INSERT INTO douyin_benchmark_videos
                (account_id, video_url, title, cover_url, like_count, comment_count,
                 share_count, collect_count, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(account_id, video_url) DO UPDATE SET
                title = excluded.title,
                cover_url = excluded.cover_url,
                like_count = excluded.like_count,
                comment_count = excluded.comment_count,
                share_count = excluded.share_count,
                collect_count = excluded.collect_count,
                raw_data = excluded.raw_data
            ''', (
                account_id,
                video_url,
                video_title,
                video.get("cover_url"),
                video.get("like_count"),
                video.get("comment_count"),
                video.get("share_count"),
                video.get("collect_count"),
                json.dumps(video, ensure_ascii=False)
            ))
            if existed:
                stats["updated"] += 1
            else:
                stats["inserted"] += 1
        cursor.execute('''
        DELETE FROM douyin_benchmark_videos
        WHERE account_id = ?
          AND (video_url LIKE '%source=Baiduspider%' OR title LIKE '热门%')
        ''', (account_id,))
        stats["deleted_dirty"] = cursor.rowcount if cursor.rowcount > 0 else 0
        conn.commit()
        return stats


def save_douyin_benchmark_error(account_id, error_message):
    ensure_douyin_benchmark_tables()
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE douyin_benchmark_accounts
        SET status = 'failed',
            error_message = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        ''', (error_message, account_id))
        conn.commit()


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

    payload = {
        "video_id": video.get("id"),
        "video_url": video.get("video_url"),
        "title": video.get("title"),
        "cover_url": video.get("cover_url"),
        "like_count": video.get("like_count"),
        "comment_count": video.get("comment_count"),
        "share_count": video.get("share_count"),
        "collect_count": video.get("collect_count"),
        "source_text": pick_analysis_source_text(video),
        "raw_data": raw_data,
    }
    return f"""
你是一个中文自媒体对标账号分析师。请基于下面这条抖音作品的同步数据，分析它为什么值得对标，以及普通内容创作者如何复刻。

要求：
1. 只根据输入数据分析，不要编造不存在的评论、完播率、转化率或视频画面细节。
2. 如果信息不足，请明确写成“基于标题/文案判断”。
3. 输出必须是一个 JSON 对象，不要输出 Markdown，不要解释，不要包裹代码块。
4. 所有数组字段都输出 3 到 5 条，语言要适合直接展示在后台页面。
5. hook 不要返回纯数字、点赞数或播放量；必须是作品的开头钩子/标题钩子。

JSON 字段：
- summary: 一句话总结这个作品的内容类型和对标价值
- hook: 开头钩子
- core_viewpoint: 核心观点
- pain_points: 人群痛点数组
- viral_points: 爆点分析数组
- reusable_points: 可复刻点数组
- script_suggestions: 脚本复刻建议数组
- keywords: 关键词数组
- structure: 内容结构数组，每项包含 label 和 content

作品数据：
{json.dumps(payload, ensure_ascii=False, indent=2)}
""".strip()


def get_codex_analysis_schema():
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "summary",
            "hook",
            "core_viewpoint",
            "pain_points",
            "viral_points",
            "reusable_points",
            "script_suggestions",
            "keywords",
            "structure",
        ],
        "properties": {
            "summary": {"type": "string"},
            "hook": {"type": "string"},
            "core_viewpoint": {"type": "string"},
            "pain_points": {"type": "array", "items": {"type": "string"}},
            "viral_points": {"type": "array", "items": {"type": "string"}},
            "reusable_points": {"type": "array", "items": {"type": "string"}},
            "script_suggestions": {"type": "array", "items": {"type": "string"}},
            "keywords": {"type": "array", "items": {"type": "string"}},
            "structure": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["label", "content"],
                    "properties": {
                        "label": {"type": "string"},
                        "content": {"type": "string"},
                    },
                },
            },
        },
    }


def load_json_object(text):
    if not text:
        raise ValueError("empty response")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise
        return json.loads(match.group(0))


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
    timeout = int(os.environ.get("CODEX_ANALYSIS_TIMEOUT_SECONDS", "180"))
    codex_cmd = os.environ.get("CODEX_CLI_PATH", "codex")
    codex_model = os.environ.get("CODEX_ANALYSIS_MODEL", "gpt-5.4-mini")

    with tempfile.TemporaryDirectory(prefix="douyin-codex-analysis-") as tmp_dir:
        schema_path = Path(tmp_dir) / "schema.json"
        output_path = Path(tmp_dir) / "result.json"
        schema_path.write_text(json.dumps(get_codex_analysis_schema(), ensure_ascii=False), encoding="utf-8")

        command = [
            codex_cmd,
            "--ask-for-approval",
            "never",
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


def save_publish_record(platform_type, title, tags, file_list, account_list, status, error_message=None,
                          views=0, likes=0, comments=0, shares=0, video_url=None):
    ensure_publish_records_table()
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO publish_records
            (platform_type, title, tags, file_list, account_list, status, error_message,
             views, likes, comments, shares, video_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            platform_type,
            title,
            json.dumps(tags or [], ensure_ascii=False),
            json.dumps(file_list or [], ensure_ascii=False),
            json.dumps(account_list or [], ensure_ascii=False),
            status,
            error_message,
            views,
            likes,
            comments,
            shares,
            video_url
        ))
        conn.commit()


def validate_account_files_for_platform(platform_type, account_list):
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        cursor = conn.cursor()
        for account_file in account_list or []:
            row = cursor.execute(
                "SELECT type, userName FROM user_info WHERE filePath = ?",
                (account_file,)
            ).fetchone()
            if not row:
                raise ValueError(f"账号不存在或未登录: {account_file}")
            if int(row[0]) != int(platform_type):
                raise ValueError(f"账号 {row[1]} 不属于当前发布平台，请重新选择账号")


def create_video_task(task_type, input_files, params):
    ensure_video_tasks_table()
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO video_tasks (task_type, status, input_files, params)
        VALUES (?, ?, ?, ?)
        ''', (
            task_type,
            "running",
            json.dumps(input_files or [], ensure_ascii=False),
            json.dumps(params or {}, ensure_ascii=False)
        ))
        conn.commit()
        return cursor.lastrowid


def update_video_task(task_id, status, output_files=None, error_message=None):
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE video_tasks
        SET status = ?,
            output_files = ?,
            error_message = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        ''', (
            status,
            json.dumps(output_files or [], ensure_ascii=False),
            error_message,
            task_id
        ))
        conn.commit()


def insert_file_record(filename, stored_filename):
    file_path = Path(BASE_DIR / "videoFile" / stored_filename)
    filesize = round(float(os.path.getsize(file_path)) / (1024 * 1024), 2)
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO file_records (filename, filesize, file_path)
        VALUES (?, ?, ?)
        ''', (filename, filesize, stored_filename))
        conn.commit()
        return cursor.lastrowid


def ffmpeg_escape_text(value):
    return (
        str(value or "")
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace(",", "\\,")
        .replace("%", "\\%")
        .replace("'", "\\'")
    )


def build_talking_edit_filter(aspect_ratio, title):
    if aspect_ratio == "9:16":
        filters = [
            "scale=1080:1920:force_original_aspect_ratio=decrease",
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black"
        ]
    elif aspect_ratio == "16:9":
        filters = [
            "scale=1920:1080:force_original_aspect_ratio=decrease",
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black"
        ]
    elif aspect_ratio == "1:1":
        filters = [
            "scale=1080:1080:force_original_aspect_ratio=decrease",
            "pad=1080:1080:(ow-iw)/2:(oh-ih)/2:black"
        ]
    else:
        filters = ["scale=trunc(iw/2)*2:trunc(ih/2)*2"]
    if title:
        font_path = "C\\:/Windows/Fonts/msyh.ttc"
        safe_title = ffmpeg_escape_text(title)
        filters.append(
            "drawtext="
            f"fontfile='{font_path}':"
            f"text='{safe_title}':"
            "fontcolor=white:fontsize=54:borderw=4:bordercolor=black:"
            "x=(w-text_w)/2:y=80"
        )
    return ",".join(filters)


def run_talking_edit(input_filename, options):
    input_path = Path(BASE_DIR / "videoFile" / input_filename)
    if not input_path.exists():
        raise FileNotFoundError(f"Input video not found: {input_filename}")

    aspect_ratio = options.get("aspectRatio") or "9:16"
    title = options.get("title") or ""
    start_time = options.get("startTime") or ""
    end_time = options.get("endTime") or ""
    output_name = options.get("outputName") or f"{input_path.stem}_talking_edit.mp4"
    output_name = "".join(ch for ch in output_name if ch not in '<>:"/\\|?*').strip() or "talking_edit.mp4"
    if not output_name.lower().endswith(".mp4"):
        output_name += ".mp4"
    if not Path(output_name).stem:
        output_name = f"{input_path.stem}_talking_edit.mp4"

    stored_filename = f"{uuid.uuid1()}_{output_name}"
    output_path = Path(BASE_DIR / "videoFile" / stored_filename)
    vf_filter = build_talking_edit_filter(aspect_ratio, title)

    cmd = ["ffmpeg", "-y"]
    if start_time:
        cmd.extend(["-ss", start_time])
    cmd.extend(["-i", str(input_path)])
    if end_time:
        cmd.extend(["-to", end_time])
    cmd.extend([
        "-vf", vf_filter,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        str(output_path)
    ])

    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-3000:] or "ffmpeg edit failed")

    record_id = insert_file_record(output_name, stored_filename)
    return {
        "id": record_id,
        "filename": output_name,
        "filepath": stored_filename
    }


def sanitize_output_name(output_name, fallback):
    output_name = "".join(ch for ch in str(output_name or "") if ch not in '<>:"/\\|?*').strip()
    output_name = output_name or fallback
    return output_name if output_name.lower().endswith(".mp4") else f"{output_name}.mp4"


def split_sentences(text):
    parts = re.split(r"[。！？!?；;\n]+", str(text or ""))
    return [part.strip() for part in parts if part.strip()]


def one_click_extract_content(topic, reference_text=""):
    source = "\n".join([str(topic or ""), str(reference_text or "")]).strip()
    sentences = split_sentences(source)
    hook = sentences[0] if sentences else "如果你每天都在看对标账号，却不知道怎么变成自己的内容，这条视频给你一套完整流程。"
    core = sentences[1] if len(sentences) > 1 else "对标不是照搬，而是拆结构、拆节奏、拆表达，再变成自己的内容资产。"
    case = sentences[2] if len(sentences) > 2 else "用 Codex 输入目标、素材和风格，就能完成文案、配音、分镜和剪辑。"
    return {
        "hook": hook,
        "core_viewpoint": core,
        "case": case,
        "pain_points": [
            "有对标内容，但不会拆解",
            "会写文案，但剪辑和配音耗时",
            "内容流程没有沉淀，不能稳定复用"
        ],
        "viral_points": [
            "开头三秒给痛点",
            "中段给方法和案例",
            "结尾给明确行动建议"
        ],
        "structure": ["开场钩子", "核心观点", "案例拆解", "方法总结", "结尾转化"]
    }


def one_click_generate_script(topic, extraction):
    hook = extraction.get("hook") or "你是不是也刷了很多对标账号，却不知道怎么变成自己的内容？"
    core = extraction.get("core_viewpoint") or "真正重要的不是抄文案，而是把结构拆出来。"
    case = extraction.get("case") or "现在只要给 Codex 三句话，它就能生成文案、配音和剪辑方案。"
    return {
        "title": "三句话，让 Codex 帮你把对标内容做成视频",
        "blocks": [
            {
                "title": "开场钩子",
                "text": f"{hook} 这不是简单省时间，而是把内容生产变成一条可以复用的流程。"
            },
            {
                "title": "核心观点",
                "text": f"{core} 我们要拆的是开头怎么抓人、观点怎么展开、案例怎么支撑、结尾怎么转化。"
            },
            {
                "title": "案例说明",
                "text": f"{case} 它先提取文案结构，再生成你的口播原文，接着合成 TTS 旁白。"
            },
            {
                "title": "结尾转化",
                "text": "最后智能剪辑会把分镜、字幕和动画组合成一条可以发布的视频。你只需要检查和微调。"
            }
        ],
        "full_text": "\n".join([
            f"{hook} 这不是简单省时间，而是把内容生产变成一条可以复用的流程。",
            f"{core} 我们要拆的是开头怎么抓人、观点怎么展开、案例怎么支撑、结尾怎么转化。",
            f"{case} 它先提取文案结构，再生成你的口播原文，接着合成 TTS 旁白。",
            "最后智能剪辑会把分镜、字幕和动画组合成一条可以发布的视频。你只需要检查和微调。"
        ])
    }


def one_click_build_storyboard(script):
    blocks = script.get("blocks") or []
    defaults = [
        ("镜头 1", "真人口播开场，字幕突出痛点", 5),
        ("镜头 2", "展示对标拆解结构和关键词", 7),
        ("镜头 3", "动画弹窗呈现方法步骤", 8),
        ("镜头 4", "结尾行动建议和转化提示", 6)
    ]
    storyboard = []
    for index, block in enumerate(blocks[:4]):
        title, visual, duration = defaults[index] if index < len(defaults) else (f"镜头 {index + 1}", "知识卡片动画", 6)
        storyboard.append({
            "title": title,
            "copy": block.get("text", ""),
            "visual": visual,
            "duration": duration
        })
    return storyboard or [
        {"title": "镜头 1", "copy": script.get("full_text", ""), "visual": "知识口播卡片", "duration": 12}
    ]


def run_xfyun_tts(text, options):
    missing = [name for name in ("XFYUN_APPID", "XFYUN_API_KEY", "XFYUN_API_SECRET") if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

    script_path = Path(os.path.expanduser("~")) / ".codex" / "skills" / "xfyun-tts" / "scripts" / "xfyun_tts.py"
    if not script_path.exists():
        script_path = Path(BASE_DIR / "project-video" / "scripts" / "xfyun_tts.py")
    if not script_path.exists():
        raise FileNotFoundError("xfyun_tts.py not found")

    voice = options.get("voice") or "x4_lingbosong"
    speed_ratio = float(options.get("speed") or 1.0)
    speed = max(0, min(100, int(speed_ratio * 50)))
    stored_filename = f"{uuid.uuid1()}_one_click_tts.mp3"
    text_path = Path(BASE_DIR / "videoFile" / f"{uuid.uuid1()}_one_click_tts.txt")
    output_path = Path(BASE_DIR / "videoFile" / stored_filename)
    text_path.write_text(text, encoding="utf-8")

    cmd = [
        os.environ.get("PYTHON") or str(Path(BASE_DIR / ".venv" / "Scripts" / "python.exe")),
        str(script_path),
        "--text", str(text_path),
        "--out", str(output_path),
        "--voice", voice,
        "--speed", str(speed),
        "--volume", "80",
        "--pitch", "50"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        text_path.unlink(missing_ok=True)
    except Exception:
        pass
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "TTS failed")[-3000:])

    record_id = insert_file_record("一键剪辑_TTS配音.mp3", stored_filename)
    return {
        "id": record_id,
        "filename": "一键剪辑_TTS配音.mp3",
        "filepath": stored_filename
    }


def assemble_xfyun_auth_url(host_url, api_key, api_secret):
    parsed = urlparse(host_url)
    date = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
    signature_origin = "\n".join([
        f"host: {parsed.netloc}",
        f"date: {date}",
        f"GET {parsed.path} HTTP/1.1"
    ])
    signature = base64.b64encode(
        hmac.new(
            api_secret.encode("utf-8"),
            signature_origin.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()
    ).decode("utf-8")
    authorization_origin = (
        f'api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")
    return f"{host_url}?{urlencode({'host': parsed.netloc, 'date': date, 'authorization': authorization})}"


def extract_audio_pcm(input_filename):
    input_path = Path(BASE_DIR / "videoFile" / input_filename)
    if not input_path.exists():
        raise FileNotFoundError(f"Input media not found: {input_filename}")

    pcm_path = Path(BASE_DIR / "videoFile" / f"{uuid.uuid1()}_asr_16k.pcm")
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-f", "s16le",
        str(pcm_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-3000:] or "extract audio failed")
    return pcm_path


def parse_xfyun_iat_result(result):
    words = []
    for ws_item in result.get("ws", []) or []:
        candidates = ws_item.get("cw", []) or []
        if candidates:
            words.append(candidates[0].get("w", ""))
    return "".join(words)


def run_xfyun_asr(input_filename, options=None):
    options = options or {}
    if websocket is None:
        raise RuntimeError("Missing dependency: websocket-client")

    missing = [name for name in ("XFYUN_APPID", "XFYUN_API_KEY", "XFYUN_API_SECRET") if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

    app_id = os.environ.get("XFYUN_APPID")
    api_key = os.environ.get("XFYUN_API_KEY")
    api_secret = os.environ.get("XFYUN_API_SECRET")
    host_url = options.get("hostUrl") or "wss://iat-api.xfyun.cn/v2/iat"
    pcm_path = extract_audio_pcm(input_filename)
    transcript_parts = []
    error = None

    def on_open(ws):
        frame_size = 1280
        interval = 0.04
        with open(pcm_path, "rb") as audio_file:
            status = 0
            while True:
                buf = audio_file.read(frame_size)
                if not buf:
                    status = 2
                payload = {
                    "common": {"app_id": app_id},
                    "business": {
                        "language": options.get("language") or "zh_cn",
                        "domain": "iat",
                        "accent": options.get("accent") or "mandarin",
                        "vad_eos": int(options.get("vadEos") or 5000)
                    },
                    "data": {
                        "status": status,
                        "format": "audio/L16;rate=16000",
                        "encoding": "raw",
                        "audio": base64.b64encode(buf).decode("utf-8")
                    }
                }
                ws.send(json.dumps(payload, ensure_ascii=False))
                if status == 2:
                    break
                status = 1
                time.sleep(interval)

    def on_message(ws, message):
        nonlocal error
        data = json.loads(message)
        code = data.get("code", 0)
        if code != 0:
            error = RuntimeError(f"XFYun ASR failed: code={code}, message={data.get('message')}")
            ws.close()
            return
        result = data.get("data", {}).get("result")
        if result:
            text = parse_xfyun_iat_result(result)
            if text:
                transcript_parts.append(text)
        if data.get("data", {}).get("status") == 2:
            ws.close()

    def on_error(ws, ws_error):
        nonlocal error
        error = RuntimeError(f"XFYun ASR websocket error: {ws_error}")

    try:
        ws_url = assemble_xfyun_auth_url(host_url, api_key, api_secret)
        ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message, on_error=on_error)
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
    finally:
        try:
            pcm_path.unlink(missing_ok=True)
        except Exception:
            pass

    if error:
        raise error
    transcript = "".join(transcript_parts).strip()
    if not transcript:
        raise RuntimeError("ASR returned empty transcript")
    return {
        "text": transcript,
        "segments": split_sentences(transcript)
    }


def run_whisper_asr(input_filename, options=None):
    options = options or {}
    input_path = Path(BASE_DIR / "videoFile" / input_filename)
    if not input_path.exists():
        raise FileNotFoundError(f"Input media not found: {input_filename}")

    python_exe = (
        options.get("python")
        or os.environ.get("WHISPER_PYTHON")
        or "D:\\python\\python.exe"
    )
    script_path = Path(BASE_DIR / "scripts" / "whisper_asr.py")
    if not script_path.exists():
        raise FileNotFoundError(f"Whisper ASR script not found: {script_path}")

    language = options.get("language") or "zh"
    language_map = {
        "zh_cn": "zh",
        "zh-CN": "zh",
        "cn": "zh",
        "mandarin": "zh",
        "chinese": "zh",
    }
    language = language_map.get(str(language), language)

    cmd = [
        python_exe,
        str(script_path),
        "--input", str(input_path),
        "--model", options.get("model") or os.environ.get("WHISPER_MODEL") or "base",
        "--language", language,
        "--device", options.get("device") or os.environ.get("WHISPER_DEVICE") or "cpu",
        "--compute-type", options.get("computeType") or os.environ.get("WHISPER_COMPUTE_TYPE") or "int8",
    ]
    timeout = int(options.get("timeout") or os.environ.get("WHISPER_TIMEOUT") or 900)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    output = (result.stdout or "").strip().splitlines()[-1] if result.stdout else ""
    try:
        payload = json.loads(output)
    except Exception:
        payload = None

    if result.returncode != 0 or not payload or not payload.get("ok"):
        error = (payload or {}).get("error") if payload else None
        raise RuntimeError(error or result.stderr[-3000:] or result.stdout[-3000:] or "Whisper ASR failed")

    data = payload.get("data") or {}
    text = (data.get("text") or "").strip()
    if not text:
        raise RuntimeError("Whisper ASR returned empty transcript")
    return data


def run_media_asr(input_filename, options=None):
    options = options or {}
    engine = (options.get("engine") or "whisper").lower()
    if engine == "xfyun":
        return run_xfyun_asr(input_filename, options)
    return run_whisper_asr(input_filename, options)


def one_click_video_filter(script, storyboard):
    font_path = "C\\:/Windows/Fonts/msyh.ttc"
    title = ffmpeg_escape_text((script.get("title") or "AI 一键剪辑").replace("\n", " ")[:26])
    lines = []
    blocks = script.get("blocks") or []
    for block in blocks[:4]:
        text = str(block.get("text") or "").replace("\n", " ")
        lines.append(ffmpeg_escape_text(text[:30]))

    filters = [
        "format=yuv420p",
        "drawbox=x=0:y=0:w=iw:h=ih:color=0x090f1f@1:t=fill",
        "drawbox=x=70:y=90:w=940:h=180:color=0x1f3b8a@0.55:t=fill",
        (
            "drawtext="
            f"fontfile='{font_path}':text='{title}':"
            "fontcolor=white:fontsize=58:borderw=3:bordercolor=0x111827:"
            "x=(w-text_w)/2:y=140"
        )
    ]
    y_positions = [430, 650, 870, 1090]
    colors = ["0x60a5fa", "0xfbbf24", "0x34d399", "0xf472b6"]
    for index, line in enumerate(lines):
        filters.append(f"drawbox=x=85:y={y_positions[index]-34}:w=910:h=125:color=0x111827@0.72:t=fill")
        filters.append(
            "drawtext="
            f"fontfile='{font_path}':text='{line}':"
            f"fontcolor={colors[index]}:fontsize=36:borderw=2:bordercolor=0x000000:"
            f"x=120:y={y_positions[index]}"
        )
    filters.append(
        "drawtext="
        f"fontfile='{font_path}':text='文案提取  原文生成  TTS合成  智能剪辑':"
        "fontcolor=0xc7d2fe:fontsize=34:x=(w-text_w)/2:y=1710"
    )
    return ",".join(filters)


def run_one_click_clip(script, storyboard, audio_file=None, options=None):
    options = options or {}
    output_name = sanitize_output_name(options.get("outputName"), "一键剪辑成片.mp4")
    stored_filename = f"{uuid.uuid1()}_{output_name}"
    output_path = Path(BASE_DIR / "videoFile" / stored_filename)
    duration = sum(int(item.get("duration") or 6) for item in storyboard or []) or 24
    duration = max(8, min(duration, 120))

    vf_filter = one_click_video_filter(script, storyboard)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=0x090f1f:s=1080x1920:d={duration}:r=30"
    ]
    audio_path = Path(BASE_DIR / "videoFile" / audio_file) if audio_file else None
    if audio_path and audio_path.exists():
        cmd.extend(["-i", str(audio_path)])
        audio_args = ["-c:a", "aac", "-b:a", "128k", "-shortest"]
    else:
        cmd.extend(["-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100:d={duration}"])
        audio_args = ["-c:a", "aac", "-b:a", "128k", "-shortest"]

    cmd.extend([
        "-vf", vf_filter,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        *audio_args,
        "-movflags", "+faststart",
        str(output_path)
    ])
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-3000:] or "one-click clip failed")

    record_id = insert_file_record(output_name, stored_filename)
    return {
        "id": record_id,
        "filename": output_name,
        "filepath": stored_filename
    }


ensure_publish_records_table()
ensure_video_tasks_table()
ensure_douyin_benchmark_tables()

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
            print("✅ 上传文件已记录")

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
        print("\n📋 当前数据表内容：")
        for row in rows:
            print(row)
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
                print("✅ 用户状态已更新")
        for row in rows:
            print(row)
        return jsonify(
                        {
                            "code": 200,
                            "msg": None,
                            "data": rows_list
                        }),200

@app.route('/getPublishRecords', methods=['GET'])
def get_publish_records():
    try:
        ensure_publish_records_table()
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM publish_records ORDER BY id DESC")
            records = []
            for row in cursor.fetchall():
                item = dict(row)
                for key in ("tags", "file_list", "account_list"):
                    try:
                        item[key] = json.loads(item.get(key) or "[]")
                    except Exception:
                        item[key] = []
                # 确保流量字段为数字
                for key in ("views", "likes", "comments", "shares"):
                    try:
                        item[key] = int(item.get(key) or 0)
                    except (ValueError, TypeError):
                        item[key] = 0
                records.append(item)
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

        ensure_publish_records_table()
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            cursor = conn.cursor()
            fields = {}
            for key in ('views', 'likes', 'comments', 'shares'):
                val = data.get(key)
                if val is not None:
                    fields[key] = int(val)
            if not fields:
                return jsonify({"code": 400, "msg": "没有需要更新的字段"}), 400

            fields['last_refresh_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            set_clause = ", ".join(f"{k} = ?" for k in fields)
            values = list(fields.values()) + [record_id]
            cursor.execute(f"UPDATE publish_records SET {set_clause} WHERE id = ?", values)
            conn.commit()

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

        ensure_publish_records_table()
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            cursor = conn.cursor()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            updated = 0
            for rec in records:
                record_id = rec.get('id')
                if not record_id:
                    continue
                fields = {}
                for key in ('views', 'likes', 'comments', 'shares'):
                    val = rec.get(key)
                    if val is not None:
                        fields[key] = int(val)
                if fields:
                    fields['last_refresh_at'] = now
                    set_clause = ", ".join(f"{k} = ?" for k in fields)
                    values = list(fields.values()) + [record_id]
                    cursor.execute(f"UPDATE publish_records SET {set_clause} WHERE id = ?", values)
                    updated += 1
            conn.commit()

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

        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE user_info SET follower_count = ? WHERE id = ?",
                          (int(follower_count), account_id))
            conn.commit()

        return jsonify({"code": 200, "msg": "更新成功"}), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/account/followers', methods=['GET'])
def get_account_followers():
    """获取所有账号的粉丝数"""
    try:
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, userName, type, follower_count, status FROM user_info ORDER BY id")
            accounts = []
            for row in cursor.fetchall():
                d = dict(row)
                d['follower_count'] = d.get('follower_count') or 0
                accounts.append(d)

        return jsonify({"code": 200, "msg": "success", "data": accounts}), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/dashboard/stats', methods=['GET'])
def get_dashboard_stats():
    try:
        ensure_publish_records_table()
        ensure_video_tasks_table()
        db_path = Path(BASE_DIR / "db" / "database.db")

        def scalar(cursor, sql, params=()):
            cursor.execute(sql, params)
            row = cursor.fetchone()
            return row[0] if row else 0

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            account_total = scalar(cursor, "SELECT COUNT(*) FROM user_info")
            account_normal = scalar(cursor, "SELECT COUNT(*) FROM user_info WHERE status = 1")
            account_abnormal = account_total - account_normal

            # 流量统计
            total_views = scalar(cursor, "SELECT COALESCE(SUM(views), 0) FROM publish_records WHERE status = 'success'")
            total_likes = scalar(cursor, "SELECT COALESCE(SUM(likes), 0) FROM publish_records WHERE status = 'success'")
            publish_success_count = scalar(cursor, "SELECT COUNT(*) FROM publish_records WHERE status = 'success'")

            cursor.execute("SELECT type, COUNT(*) AS count FROM user_info GROUP BY type")
            platform_counts = {str(row["type"]): row["count"] for row in cursor.fetchall()}
            active_platform_total = sum(1 for count in platform_counts.values() if count > 0)

            task_total = (
                scalar(cursor, "SELECT COUNT(*) FROM publish_records")
                + scalar(cursor, "SELECT COUNT(*) FROM video_tasks")
            )
            publish_success = scalar(cursor, "SELECT COUNT(*) FROM publish_records WHERE status = 'success'")
            publish_failed = scalar(cursor, "SELECT COUNT(*) FROM publish_records WHERE status = 'failed'")
            video_success = scalar(cursor, "SELECT COUNT(*) FROM video_tasks WHERE status = 'success'")
            video_failed = scalar(cursor, "SELECT COUNT(*) FROM video_tasks WHERE status = 'failed'")
            task_completed = publish_success + video_success
            task_failed = publish_failed + video_failed
            task_in_progress = scalar(
                cursor,
                "SELECT COUNT(*) FROM video_tasks WHERE status NOT IN ('success', 'failed')",
            )

            cursor.execute("SELECT file_path FROM file_records")
            material_files = {row["file_path"] for row in cursor.fetchall() if row["file_path"]}
            cursor.execute("SELECT file_list FROM publish_records WHERE status = 'success'")
            published_files = set()
            for row in cursor.fetchall():
                try:
                    published_files.update(json.loads(row["file_list"] or "[]"))
                except Exception:
                    continue
            content_total = len(material_files | published_files)
            published_content = len(published_files)
            draft_content = len(material_files - published_files)

            # 总流量合计（用于首页统计卡片）
            publish_success_count = scalar(cursor, "SELECT COUNT(*) FROM publish_records WHERE status = 'success'")

            platform_names = {
                1: "小红书",
                2: "视频号",
                3: "抖音",
                4: "快手",
            }
            status_names = {
                "success": "已完成",
                "failed": "已失败",
                "pending": "待执行",
                "running": "进行中",
            }
            recent_tasks = []
            cursor.execute("SELECT filePath, userName FROM user_info")
            account_names = {row["filePath"]: row["userName"] for row in cursor.fetchall()}

            cursor.execute(
                """
                SELECT id, platform_type, title, status, created_at, account_list
                FROM publish_records
                ORDER BY id DESC
                LIMIT 5
                """
            )
            for row in cursor.fetchall():
                try:
                    accounts = json.loads(row["account_list"] or "[]")
                except Exception:
                    accounts = []
                account_label = "、".join(account_names.get(account, account) for account in accounts)
                recent_tasks.append(
                    {
                        "id": row["id"],
                        "title": row["title"] or "未命名发布任务",
                        "platform": platform_names.get(row["platform_type"], "未知"),
                        "account": account_label if account_label else "-",
                        "createTime": row["created_at"],
                        "status": status_names.get(row["status"], row["status"]),
                    }
                )

        return jsonify(
            {
                "code": 200,
                "msg": "success",
                "data": {
                    "accountStats": {
                        "total": account_total,
                        "normal": account_normal,
                        "abnormal": account_abnormal,
                    },
                    "platformStats": {
                        "total": active_platform_total,
                        "kuaishou": platform_counts.get("4", 0),
                        "douyin": platform_counts.get("3", 0),
                        "channels": platform_counts.get("2", 0),
                        "xiaohongshu": platform_counts.get("1", 0),
                    },
                    "taskStats": {
                        "total": task_total,
                        "completed": task_completed,
                        "inProgress": task_in_progress,
                        "failed": task_failed,
                    },
                    "contentStats": {
                        "total": content_total,
                        "published": published_content,
                        "draft": draft_content,
                    },
                    "trafficStats": {
                        "total_views": total_views,
                        "total_likes": total_likes,
                        "publish_count": publish_success_count,
                    },
                    "recentTasks": recent_tasks,
                },
            }
        ), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/video/talkingEdit', methods=['POST'])
def talking_edit():
    data = request.get_json() or {}
    input_file = data.get("file")
    options = data.get("options") or {}
    if not input_file:
        return jsonify({"code": 400, "msg": "file is required", "data": None}), 400

    task_id = create_video_task("talking_edit", [input_file], options)
    try:
        output = run_talking_edit(input_file, options)
        update_video_task(task_id, "success", [output.get("filepath")])
        return jsonify({
            "code": 200,
            "msg": "success",
            "data": {
                "taskId": task_id,
                "output": output
            }
        }), 200
    except Exception as e:
        update_video_task(task_id, "failed", [], str(e))
        return jsonify({"code": 500, "msg": str(e), "data": {"taskId": task_id}}), 500


@app.route('/video/oneClick/extract', methods=['POST'])
def one_click_extract():
    data = request.get_json() or {}
    try:
        extraction = one_click_extract_content(data.get("topic"), data.get("referenceText"))
        return jsonify({"code": 200, "msg": "success", "data": extraction}), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/video/oneClick/rewrite', methods=['POST'])
def one_click_rewrite():
    data = request.get_json() or {}
    try:
        extraction = data.get("extraction") or one_click_extract_content(data.get("topic"), data.get("referenceText"))
        script = one_click_generate_script(data.get("topic"), extraction)
        storyboard = one_click_build_storyboard(script)
        return jsonify({
            "code": 200,
            "msg": "success",
            "data": {
                "script": script,
                "storyboard": storyboard
            }
        }), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/video/oneClick/tts', methods=['POST'])
def one_click_tts():
    data = request.get_json() or {}
    text = data.get("text") or data.get("scriptText") or ""
    options = data.get("options") or {}
    if not text.strip():
        return jsonify({"code": 400, "msg": "text is required", "data": None}), 400

    task_id = create_video_task("one_click_tts", [], {"voice": options.get("voice"), "speed": options.get("speed")})
    try:
        audio = run_xfyun_tts(text, options)
        update_video_task(task_id, "success", [audio.get("filepath")])
        return jsonify({"code": 200, "msg": "success", "data": {"taskId": task_id, "audio": audio}}), 200
    except Exception as e:
        update_video_task(task_id, "failed", [], str(e))
        return jsonify({"code": 500, "msg": str(e), "data": {"taskId": task_id}}), 500


@app.route('/video/oneClick/asr', methods=['POST'])
def one_click_asr():
    data = request.get_json() or {}
    input_file = data.get("file") or data.get("sourceFile") or data.get("source_file")
    options = data.get("options") or {}
    if not input_file:
        return jsonify({"code": 400, "msg": "file is required", "data": None}), 400

    task_id = create_video_task("one_click_asr", [input_file], options)
    try:
        transcript = run_media_asr(input_file, options)
        update_video_task(task_id, "success", [])
        return jsonify({
            "code": 200,
            "msg": "success",
            "data": {
                "taskId": task_id,
                "transcript": transcript
            }
        }), 200
    except Exception as e:
        update_video_task(task_id, "failed", [], str(e))
        return jsonify({"code": 500, "msg": str(e), "data": {"taskId": task_id}}), 500


@app.route('/video/oneClick/clip', methods=['POST'])
def one_click_clip():
    data = request.get_json() or {}
    script = data.get("script") or {}
    storyboard = data.get("storyboard") or []
    audio_file = data.get("audioFile") or data.get("audio_file")
    options = data.get("options") or {}
    if not script:
        return jsonify({"code": 400, "msg": "script is required", "data": None}), 400

    task_id = create_video_task("one_click_clip", [audio_file] if audio_file else [], options)
    try:
        output = run_one_click_clip(script, storyboard, audio_file=audio_file, options=options)
        update_video_task(task_id, "success", [output.get("filepath")])
        return jsonify({"code": 200, "msg": "success", "data": {"taskId": task_id, "output": output}}), 200
    except Exception as e:
        update_video_task(task_id, "failed", [], str(e))
        return jsonify({"code": 500, "msg": str(e), "data": {"taskId": task_id}}), 500


@app.route('/video/oneClick/run', methods=['POST'])
def one_click_run():
    data = request.get_json() or {}
    topic = data.get("topic") or ""
    reference_text = data.get("referenceText") or ""
    source_file = data.get("sourceFile") or data.get("source_file")
    voice_options = data.get("voice") or data.get("voiceOptions") or {}
    clip_options = data.get("clip") or data.get("clipOptions") or {}
    input_files = [source_file] if source_file else []
    task_id = create_video_task("one_click_video", input_files, {
        "topic": topic,
        "sourceFile": source_file,
        "voice": voice_options,
        "clip": clip_options
    })
    try:
        transcript = None
        if source_file and not str(reference_text or "").strip():
            transcript = run_media_asr(source_file, data.get("asr") or {})
            reference_text = transcript.get("text") or reference_text

        extraction = one_click_extract_content(topic, reference_text)
        script = one_click_generate_script(topic, extraction)
        storyboard = one_click_build_storyboard(script)
        warnings = []
        audio = None
        try:
            audio = run_xfyun_tts(script.get("full_text") or "", voice_options)
        except Exception as tts_error:
            warnings.append(f"TTS skipped: {tts_error}")

        output = run_one_click_clip(
            script,
            storyboard,
            audio_file=audio.get("filepath") if audio else None,
            options=clip_options
        )
        outputs = [output.get("filepath")]
        if audio:
            outputs.insert(0, audio.get("filepath"))
        update_video_task(task_id, "success", outputs, "\n".join(warnings) if warnings else None)
        return jsonify({
            "code": 200,
            "msg": "success",
            "data": {
                "taskId": task_id,
                "extraction": extraction,
                "transcript": transcript,
                "script": script,
                "storyboard": storyboard,
                "audio": audio,
                "output": output,
                "warnings": warnings
            }
        }), 200
    except Exception as e:
        update_video_task(task_id, "failed", [], str(e))
        return jsonify({"code": 500, "msg": str(e), "data": {"taskId": task_id}}), 500


@app.route('/video/tasks', methods=['GET'])
def get_video_tasks():
    try:
        ensure_video_tasks_table()
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM video_tasks ORDER BY id DESC")
            tasks = []
            for row in cursor.fetchall():
                item = dict(row)
                for key in ("input_files", "output_files"):
                    try:
                        item[key] = json.loads(item.get(key) or "[]")
                    except Exception:
                        item[key] = []
                try:
                    item["params"] = json.loads(item.get("params") or "{}")
                except Exception:
                    item["params"] = {}
                tasks.append(item)
        return jsonify({"code": 200, "msg": "success", "data": tasks}), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/benchmark/douyin/accounts', methods=['POST'])
def add_douyin_benchmark_account():
    data = request.get_json() or {}
    homepage_url = data.get("homepageUrl") or data.get("homepage_url")
    try:
        cookie_file = latest_douyin_cookie_file()
        if not cookie_file:
            return jsonify({"code": 400, "msg": "请先在账号管理中登录一个抖音账号", "data": None}), 400
        account_id = upsert_douyin_benchmark(homepage_url)
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
        try:
            if homepage_url:
                save_douyin_benchmark_error(upsert_douyin_benchmark(homepage_url), str(e))
        except Exception:
            pass
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/benchmark/douyin/accounts', methods=['GET'])
def get_douyin_benchmark_accounts():
    try:
        ensure_douyin_benchmark_tables()
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            rows = cursor.execute('''
            SELECT *,
                (SELECT COUNT(*) FROM douyin_benchmark_videos v WHERE v.account_id = a.id) AS synced_video_count
            FROM douyin_benchmark_accounts a
            ORDER BY id DESC
            ''').fetchall()
            accounts = [dict(row) for row in rows]
        return jsonify({"code": 200, "msg": "success", "data": accounts}), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/benchmark/douyin/accounts/<int:account_id>/sync', methods=['POST'])
def sync_douyin_benchmark_account(account_id):
    try:
        cookie_file = latest_douyin_cookie_file()
        if not cookie_file:
            return jsonify({"code": 400, "msg": "请先在账号管理中登录一个抖音账号", "data": None}), 400
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            row = conn.execute(
                "SELECT homepage_url FROM douyin_benchmark_accounts WHERE id = ?",
                (account_id,)
            ).fetchone()
        if not row:
            return jsonify({"code": 404, "msg": "对标账号不存在", "data": None}), 404
        existing_urls = get_douyin_benchmark_video_urls(account_id)
        sync_data = asyncio.run(scrape_douyin_benchmark(
            row[0],
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
        ensure_douyin_benchmark_tables()
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            rows = cursor.execute('''
            SELECT * FROM douyin_benchmark_videos
            WHERE account_id = ?
            ORDER BY id DESC
            ''', (account_id,)).fetchall()
            videos = [dict(row) for row in rows]
        return jsonify({"code": 200, "msg": "success", "data": videos}), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/benchmark/douyin/videos/<int:video_id>/analysis', methods=['GET'])
def get_douyin_benchmark_video_analysis(video_id):
    try:
        ensure_douyin_benchmark_tables()
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row
            video = conn.execute(
                "SELECT * FROM douyin_benchmark_videos WHERE id = ?",
                (video_id,)
            ).fetchone()
            if not video:
                return jsonify({"code": 404, "msg": "作品不存在", "data": None}), 404
            row = conn.execute(
                "SELECT * FROM douyin_benchmark_video_analysis WHERE video_id = ?",
                (video_id,)
            ).fetchone()
        if is_douyin_analysis_stale(row, dict(video)):
            analysis = generate_douyin_video_analysis(dict(video))
            save_douyin_video_analysis(video_id, analysis)
            with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT * FROM douyin_benchmark_video_analysis WHERE video_id = ?",
                    (video_id,)
                ).fetchone()
        return jsonify({
            "code": 200,
            "msg": "success",
            "data": {
                "video": dict(video),
                "analysis": parse_douyin_video_analysis(row)
            }
        }), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


@app.route('/benchmark/douyin/videos/<int:video_id>/analysis', methods=['POST'])
def create_douyin_benchmark_video_analysis(video_id):
    try:
        ensure_douyin_benchmark_tables()
        force = bool((request.get_json(silent=True) or {}).get("force"))
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row
            video = conn.execute(
                "SELECT * FROM douyin_benchmark_videos WHERE id = ?",
                (video_id,)
            ).fetchone()
            if not video:
                return jsonify({"code": 404, "msg": "作品不存在", "data": None}), 404
            existing = conn.execute(
                "SELECT * FROM douyin_benchmark_video_analysis WHERE video_id = ?",
                (video_id,)
            ).fetchone()
            if existing and not force and not is_douyin_analysis_stale(existing, dict(video)):
                return jsonify({
                    "code": 200,
                    "msg": "success",
                    "data": parse_douyin_video_analysis(existing)
                }), 200

        analysis = generate_douyin_video_analysis(dict(video))
        save_douyin_video_analysis(video_id, analysis)
        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM douyin_benchmark_video_analysis WHERE video_id = ?",
                (video_id,)
            ).fetchone()
        return jsonify({"code": 200, "msg": "success", "data": parse_douyin_video_analysis(row)}), 200
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e), "data": None}), 500


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
    # 获取JSON数据
    data = request.get_json()

    # 从JSON数据中提取fileList和accountList
    file_list = data.get('fileList', [])
    account_list = data.get('accountList', [])
    type = data.get('type')
    title = data.get('title')
    tags = data.get('tags')
    category = data.get('category')
    enableTimer = data.get('enableTimer')
    if category == 0:
        category = None

    videos_per_day = data.get('videosPerDay')
    daily_times = data.get('dailyTimes')
    start_days = data.get('startDays')
    # 打印获取到的数据（仅作为示例）
    print("File List:", file_list)
    print("Account List:", account_list)
    try:
        validate_account_files_for_platform(type, account_list)
        match type:
            case 1:
                post_video_xhs(title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times,
                                   start_days)
            case 2:
                post_video_tencent(title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times,
                                   start_days)
            case 3:
                post_video_DouYin(title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times,
                          start_days)
            case 4:
                post_video_ks(title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times,
                          start_days)
            case _:
                raise ValueError(f"Unsupported platform type: {type}")
        save_publish_record(type, title, tags, file_list, account_list, "success")
    except Exception as e:
        save_publish_record(type, title, tags, file_list, account_list, "failed", str(e))
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
        # 从JSON数据中提取fileList和accountList
        file_list = data.get('fileList', [])
        account_list = data.get('accountList', [])
        type = data.get('type')
        title = data.get('title')
        tags = data.get('tags')
        category = data.get('category')
        enableTimer = data.get('enableTimer')
        if category == 0:
            category = None

        videos_per_day = data.get('videosPerDay')
        daily_times = data.get('dailyTimes')
        start_days = data.get('startDays')
        # 打印获取到的数据（仅作为示例）
        print("File List:", file_list)
        print("Account List:", account_list)
        try:
            validate_account_files_for_platform(type, account_list)
            match type:
                case 1:
                    post_video_xhs(title, file_list, tags, account_list, category, enableTimer, videos_per_day,
                                   daily_times, start_days)
                case 2:
                    post_video_tencent(title, file_list, tags, account_list, category, enableTimer, videos_per_day,
                                       daily_times, start_days)
                case 3:
                    post_video_DouYin(title, file_list, tags, account_list, category, enableTimer, videos_per_day,
                                      daily_times, start_days)
                case 4:
                    post_video_ks(title, file_list, tags, account_list, category, enableTimer, videos_per_day,
                                  daily_times, start_days)
                case _:
                    raise ValueError(f"Unsupported platform type: {type}")
            save_publish_record(type, title, tags, file_list, account_list, "success")
        except Exception as e:
            save_publish_record(type, title, tags, file_list, account_list, "failed", str(e))
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
    match type:
        case '1':
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(xiaohongshu_cookie_gen(id, status_queue))
            loop.close()
        case '2':
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(get_tencent_cookie(id,status_queue))
            loop.close()
        case '3':
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(douyin_cookie_gen(id,status_queue))
            loop.close()
        case '4':
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(get_ks_cookie(id,status_queue))
            loop.close()

# SSE 流生成器函数
def sse_stream(status_queue):
    while True:
        if not status_queue.empty():
            msg = status_queue.get()
            yield f"data: {msg}\n\n"
        else:
            # 避免 CPU 占满
            time.sleep(0.1)

if __name__ == '__main__':
    app.run(host='0.0.0.0' ,port=5409)
