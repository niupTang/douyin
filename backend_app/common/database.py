import sqlite3
from pathlib import Path


def ensure_core_tables(db_path):
    db_path = Path(db_path)
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
