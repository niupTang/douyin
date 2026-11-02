from backend_app.common import sqlite as sqlite3
from pathlib import Path


def connect(db_path):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


def ensure_core_tables(db_path):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type INTEGER NOT NULL,
            filePath TEXT NOT NULL,
            userName TEXT NOT NULL,
            status INTEGER DEFAULT 0,
            follower_count INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        user_info_columns = {
            row[1] for row in cursor.execute("PRAGMA table_info(user_info)").fetchall()
        }
        if "follower_count" not in user_info_columns:
            cursor.execute(
                "ALTER TABLE user_info ADD COLUMN follower_count INTEGER DEFAULT 0"
            )
        account_columns = {
            "platform_user_id": "TEXT",
            "display_name": "TEXT",
            "remark_name": "TEXT",
            "last_validated_at": "DATETIME",
            "last_error_code": "TEXT",
            "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
        }
        for column_name, definition in account_columns.items():
            if column_name not in user_info_columns:
                migration_definition = (
                    "DATETIME"
                    if column_name in {"created_at", "updated_at"}
                    else definition
                )
                cursor.execute(
                    f"ALTER TABLE user_info ADD COLUMN {column_name} {migration_definition}"
                )
        cursor.execute(
            """
            UPDATE user_info
            SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP),
                updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)
            WHERE created_at IS NULL OR updated_at IS NULL
            """
        )
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uk_user_info_platform_identity
            ON user_info(type, platform_user_id)
            WHERE platform_user_id IS NOT NULL
            """
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
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL,
            value_type TEXT NOT NULL DEFAULT 'json',
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        conn.commit()
