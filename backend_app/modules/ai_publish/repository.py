import json
import sqlite3
from datetime import datetime


def ensure_tables(db_path):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
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
        """)
        conn.commit()


def save_record(db_path, platform_type, title, tags, file_list, account_list, status,
                error_message=None, views=0, likes=0, comments=0, shares=0, video_url=None):
    ensure_tables(db_path)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO publish_records
            (platform_type, title, tags, file_list, account_list, status, error_message,
             views, likes, comments, shares, video_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
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
            video_url,
        ))
        conn.commit()
        return cursor.lastrowid


def list_records(db_path):
    ensure_tables(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM publish_records ORDER BY id DESC").fetchall()
    records = []
    for row in rows:
        item = dict(row)
        for key in ("tags", "file_list", "account_list"):
            try:
                item[key] = json.loads(item.get(key) or "[]")
            except Exception:
                item[key] = []
        for key in ("views", "likes", "comments", "shares"):
            try:
                item[key] = int(item.get(key) or 0)
            except (ValueError, TypeError):
                item[key] = 0
        records.append(item)
    return records


def update_stats(db_path, record_id, values):
    fields = {}
    for key in ("views", "likes", "comments", "shares"):
        value = values.get(key)
        if value is not None:
            fields[key] = int(value)
    if not fields:
        return {}
    fields["last_refresh_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_clause = ", ".join(f"{key} = ?" for key in fields)
    params = list(fields.values()) + [record_id]
    with sqlite3.connect(db_path) as conn:
        conn.execute(f"UPDATE publish_records SET {set_clause} WHERE id = ?", params)
        conn.commit()
    return fields


def batch_update_stats(db_path, records):
    ensure_tables(db_path)
    updated = 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(db_path) as conn:
        for record in records:
            record_id = record.get("id")
            if not record_id:
                continue
            fields = {}
            for key in ("views", "likes", "comments", "shares"):
                value = record.get(key)
                if value is not None:
                    fields[key] = int(value)
            if not fields:
                continue
            fields["last_refresh_at"] = now
            set_clause = ", ".join(f"{key} = ?" for key in fields)
            params = list(fields.values()) + [record_id]
            conn.execute(f"UPDATE publish_records SET {set_clause} WHERE id = ?", params)
            updated += 1
        conn.commit()
    return updated
