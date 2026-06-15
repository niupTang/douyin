import asyncio
import json
import os
import re
import sqlite3
import subprocess
import threading
import time
import uuid
from pathlib import Path
from queue import Queue
from flask_cors import CORS
from myUtils.auth import check_cookie
from myUtils.douyin_benchmark import scrape_douyin_benchmark
from flask import Flask, request, jsonify, Response, render_template, send_from_directory
from conf import BASE_DIR
from myUtils.login import get_tencent_cookie, douyin_cookie_gen, get_ks_cookie, xiaohongshu_cookie_gen
from myUtils.postVideo import post_video_tencent, post_video_DouYin, post_video_ks, post_video_xhs

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


def generate_douyin_video_analysis(video):
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


def save_publish_record(platform_type, title, tags, file_list, account_list, status, error_message=None):
    ensure_publish_records_table()
    with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO publish_records
            (platform_type, title, tags, file_list, account_list, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            platform_type,
            title,
            json.dumps(tags or [], ensure_ascii=False),
            json.dumps(file_list or [], ensure_ascii=False),
            json.dumps(account_list or [], ensure_ascii=False),
            status,
            error_message
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
    return str(value or "").replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def build_talking_edit_filter(aspect_ratio, title):
    if aspect_ratio == "9:16":
        filters = [
            "scale=1080:-2",
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black"
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
                records.append(item)
        return jsonify({"code": 200, "msg": "success", "data": records}), 200
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
