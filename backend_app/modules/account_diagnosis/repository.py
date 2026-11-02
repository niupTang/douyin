import json
from backend_app.common import sqlite as sqlite3
from pathlib import Path


def connect(db_path):
    connection = sqlite3.connect(Path(db_path))
    connection.row_factory = sqlite3.Row
    return connection


def _ensure_column(conn, table, column, definition):
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def ensure_tables(db_path):
    with sqlite3.connect(Path(db_path)) as conn:
        cursor = conn.cursor()
        # 自有账号挂 user_info 外键
        _ensure_column(conn, "douyin_own_accounts", "user_info_id", "INTEGER")
        # 发布记录挂 user_info 外键
        _ensure_column(conn, "publish_records", "user_info_id", "INTEGER")
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS diagnosis_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_type TEXT NOT NULL,
            target_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            facts_json TEXT,
            report_json TEXT,
            error_message TEXT,
            progress_percent INTEGER DEFAULT 0,
            progress_message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        _ensure_column(conn, "diagnosis_reports", "progress_percent", "INTEGER DEFAULT 0")
        _ensure_column(conn, "diagnosis_reports", "progress_message", "TEXT")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_diagnosis_reports_target "
            "ON diagnosis_reports(target_type, target_id)"
        )
        conn.commit()


# ---------------------------------------------------------------- user_info

def list_douyin_user_info_accounts(db_path):
    ensure_tables(db_path)
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, userName, filePath, follower_count, status "
            "FROM user_info WHERE type = 3 ORDER BY id"
        ).fetchall()
    return [dict(row) for row in rows]


def get_user_info_account(db_path, user_info_id):
    with sqlite3.connect(Path(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM user_info WHERE id = ?", (user_info_id,)
        ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------- 自有账号绑定

def list_own_accounts(db_path):
    ensure_tables(db_path)
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM douyin_own_accounts ORDER BY id"
        ).fetchall()
    return [dict(row) for row in rows]


def get_own_account(db_path, own_account_id):
    with sqlite3.connect(Path(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM douyin_own_accounts WHERE id = ?", (own_account_id,)
        ).fetchone()
    return dict(row) if row else None


def bind_own_account(db_path, own_account_id, user_info_id):
    ensure_tables(db_path)
    with sqlite3.connect(Path(db_path)) as conn:
        conn.execute(
            "UPDATE douyin_own_accounts SET user_info_id = ? WHERE id = ?",
            (user_info_id, own_account_id),
        )
        conn.commit()


def get_bound_own_account(db_path, user_info_id):
    with sqlite3.connect(Path(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM douyin_own_accounts WHERE user_info_id = ? ORDER BY id LIMIT 1",
            (user_info_id,),
        ).fetchone()
    return dict(row) if row else None


def list_own_videos_for_user(db_path, user_info_id):
    ensure_tables(db_path)
    with connect(db_path) as conn:
        rows = conn.execute("""
            SELECT v.*, m.play_count, m.completion_rate, m.five_sec_completion_rate,
                m.cover_click_rate, m.two_sec_bounce_rate, m.avg_play_duration,
                m.like_count, m.share_count, m.comment_count, m.collect_count,
                m.profile_visit_count, m.follower_delta
            FROM douyin_own_videos v
            JOIN douyin_own_accounts a ON a.id = v.account_id
            LEFT JOIN douyin_own_video_metrics m ON m.video_id = v.id
            WHERE a.user_info_id = ?
            ORDER BY COALESCE(v.published_at, v.created_at) DESC, v.id DESC
        """, (user_info_id,)).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------- 发布记录

def backfill_publish_user_info(db_path):
    """按 account_list 里的 filePath 反查 user_info.id 回填 user_info_id。"""
    with sqlite3.connect(Path(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        _ensure_column(conn, "publish_records", "user_info_id", "INTEGER")
        rows = conn.execute(
            "SELECT id, account_list FROM publish_records WHERE user_info_id IS NULL"
        ).fetchall()
        updated = 0
        for row in rows:
            filepaths = []
            try:
                parsed = json.loads(row["account_list"] or "[]")
                filepaths = [str(p) for p in parsed] if isinstance(parsed, list) else []
            except (TypeError, ValueError):
                filepaths = []
            user_info_id = None
            if filepaths:
                placeholders = ",".join("?" for _ in filepaths)
                found = conn.execute(
                    f"SELECT id FROM user_info WHERE filePath IN ({placeholders}) ORDER BY id LIMIT 1",
                    filepaths,
                ).fetchone()
                if found:
                    user_info_id = found["id"]
            if user_info_id is not None:
                conn.execute(
                    "UPDATE publish_records SET user_info_id = ? WHERE id = ?",
                    (user_info_id, row["id"]),
                )
                updated += 1
        conn.commit()
        return updated


def list_publish_records_for_user(db_path, user_info_id):
    ensure_tables(db_path)
    backfill_publish_user_info(db_path)
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM publish_records WHERE user_info_id = ? ORDER BY id DESC",
            (user_info_id,),
        ).fetchall()
    records = []
    for row in rows:
        item = dict(row)
        for key in ("tags", "file_list", "account_list"):
            try:
                item[key] = json.loads(item.get(key) or "[]")
            except (TypeError, ValueError):
                item[key] = []
        records.append(item)
    return records


# ---------------------------------------------------------------- 对标账号

def get_benchmark_account(db_path, account_id):
    with sqlite3.connect(Path(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM douyin_benchmark_accounts WHERE id = ?", (account_id,)
        ).fetchone()
    return dict(row) if row else None


def list_benchmark_videos(db_path, account_id):
    from backend_app.modules.benchmark import repository as benchmark_repository
    return benchmark_repository.list_videos(db_path, account_id)


# ---------------------------------------------------------------- 报告

def create_report(db_path, target_type, target_id, status, facts=None, report=None, error=None,
                  progress=0, message=None):
    ensure_tables(db_path)
    with sqlite3.connect(Path(db_path)) as conn:
        cursor = conn.execute(
            "INSERT INTO diagnosis_reports "
            "(target_type, target_id, status, facts_json, report_json, error_message, progress_percent, progress_message) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                target_type,
                target_id,
                status,
                json.dumps(facts, ensure_ascii=False) if facts is not None else None,
                json.dumps(report, ensure_ascii=False) if report is not None else None,
                error,
                progress,
                message,
            ),
        )
        conn.commit()
        return cursor.lastrowid


def update_report_progress(db_path, report_id, status=None, progress=None, message=None,
                           facts=None, report=None, error=None):
    fields = {}
    if status is not None:
        fields["status"] = status
    if progress is not None:
        fields["progress_percent"] = progress
    if message is not None:
        fields["progress_message"] = message
    if facts is not None:
        fields["facts_json"] = json.dumps(facts, ensure_ascii=False)
    if report is not None:
        fields["report_json"] = json.dumps(report, ensure_ascii=False)
    if error is not None:
        fields["error_message"] = error
    if not fields:
        return
    assignments = ", ".join(f"{key} = ?" for key in fields)
    params = list(fields.values()) + [report_id]
    with sqlite3.connect(Path(db_path)) as conn:
        conn.execute(f"UPDATE diagnosis_reports SET {assignments} WHERE id = ?", params)
        conn.commit()


def list_reports(db_path, target_type=None, limit=50):
    ensure_tables(db_path)
    clauses, params = [], []
    if target_type:
        clauses.append("target_type = ?")
        params.append(target_type)
    params.append(max(1, min(int(limit or 50), 200)))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM diagnosis_reports {where} ORDER BY id DESC LIMIT ?",
            params,
        ).fetchall()
    return [_decode_report(row) for row in rows]


def get_report(db_path, report_id):
    ensure_tables(db_path)
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM diagnosis_reports WHERE id = ?", (report_id,)
        ).fetchone()
    return _decode_report(row) if row else None


def _decode_report(row):
    item = dict(row)
    item["report"] = _load_json(item.pop("report_json", None))
    item["facts"] = _load_json(item.pop("facts_json", None))
    return item


def _load_json(value):
    if value in (None, ""):
        return None
    try:
        return json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError):
        return None
