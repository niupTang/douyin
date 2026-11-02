import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend_app.common import sqlite as sqlite3
import json
import os

# 数据库文件路径（如果不存在会自动创建）
db_file = Path(__file__).resolve().parent / 'database.db'

# 如果数据库已存在，则删除旧的表（可选）
# if os.path.exists(db_file):
#     os.remove(db_file)

# 连接到SQLite数据库（如果文件不存在则会自动创建）
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# 创建账号记录表
cursor.execute('''
CREATE TABLE IF NOT EXISTS user_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type INTEGER NOT NULL,
    filePath TEXT NOT NULL,  -- 存储文件路径
    userName TEXT NOT NULL,
    status INTEGER DEFAULT 0
)
''')

# 创建文件记录表
cursor.execute('''CREATE TABLE IF NOT EXISTS file_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- 唯一标识每条记录
    filename TEXT NOT NULL,               -- 文件名
    filesize REAL,                     -- 文件大小（单位：MB）
    upload_time DATETIME DEFAULT CURRENT_TIMESTAMP, -- 上传时间，默认当前时间
    file_path TEXT                        -- 文件路径
)
''')


# 提交更改
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
    received_likes_count TEXT,
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

cursor.execute('''
CREATE TABLE IF NOT EXISTS douyin_benchmark_video_transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending',
    stage TEXT NOT NULL DEFAULT 'pending',
    analysis_basis TEXT NOT NULL DEFAULT 'title_only',
    raw_transcript TEXT,
    cleaned_transcript TEXT,
    segments TEXT,
    engine TEXT,
    model TEXT,
    language TEXT,
    duration REAL DEFAULT 0,
    target_direction TEXT,
    radar_json TEXT,
    error_message TEXT,
    progress_percent INTEGER DEFAULT 0,
    progress_message TEXT,
    progress_log TEXT,
    started_at DATETIME,
    finished_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS douyin_own_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    user_info_id INTEGER,
    source TEXT NOT NULL DEFAULT 'manual_import',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS douyin_own_videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    source_key TEXT NOT NULL,
    title TEXT NOT NULL,
    video_url TEXT,
    published_at TEXT,
    content_format TEXT,
    visibility_status TEXT,
    transcript TEXT,
    notes TEXT,
    raw_data TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_id, source_key)
)
''')

cursor.execute('''
CREATE UNIQUE INDEX IF NOT EXISTS idx_douyin_own_accounts_user_info
ON douyin_own_accounts(user_info_id)
WHERE user_info_id IS NOT NULL
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS douyin_own_video_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL UNIQUE,
    play_count INTEGER,
    completion_rate REAL,
    five_sec_completion_rate REAL,
    cover_click_rate REAL,
    two_sec_bounce_rate REAL,
    avg_play_duration REAL,
    like_count INTEGER,
    share_count INTEGER,
    comment_count INTEGER,
    collect_count INTEGER,
    profile_visit_count INTEGER,
    follower_delta INTEGER,
    raw_data TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS douyin_own_export_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_info_id INTEGER,
    account_name TEXT,
    status TEXT NOT NULL,
    file_path TEXT,
    imported_count INTEGER DEFAULT 0,
    error_message TEXT,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    finished_at DATETIME
)
''')

cursor.execute('''
CREATE INDEX IF NOT EXISTS idx_douyin_own_export_runs_account
ON douyin_own_export_runs(user_info_id, id DESC)
''')

conn.commit()
print("✅ 表创建成功")
# 关闭连接
conn.close()
