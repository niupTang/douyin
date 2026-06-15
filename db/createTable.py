import sqlite3
import json
import os

# 数据库文件路径（如果不存在会自动创建）
db_file = './database.db'

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
print("✅ 表创建成功")
# 关闭连接
conn.close()
