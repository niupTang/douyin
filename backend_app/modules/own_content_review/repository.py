import json
from backend_app.common import sqlite as sqlite3


def ensure_tables(db_path):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS douyin_own_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            user_info_id INTEGER,
            source TEXT NOT NULL DEFAULT 'manual_import',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
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
            analysis_status TEXT NOT NULL DEFAULT 'pending',
            analysis_json TEXT,
            analysis_error TEXT,
            analysis_updated_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(account_id, source_key)
        )
        """)
        cursor.execute("""
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
        """)
        account_columns = {row[1] for row in cursor.execute("PRAGMA table_info(douyin_own_accounts)").fetchall()}
        if "user_info_id" not in account_columns:
            cursor.execute("ALTER TABLE douyin_own_accounts ADD COLUMN user_info_id INTEGER")
        duplicate_bindings = cursor.execute("""
            SELECT user_info_id
            FROM douyin_own_accounts
            WHERE user_info_id IS NOT NULL
            GROUP BY user_info_id
            HAVING COUNT(*) > 1
        """).fetchall()
        if duplicate_bindings:
            raise RuntimeError("自有作品账号存在重复绑定，请先修复 user_info_id 归属")
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_douyin_own_accounts_user_info
            ON douyin_own_accounts(user_info_id)
            WHERE user_info_id IS NOT NULL
        """)
        columns = {row[1] for row in cursor.execute("PRAGMA table_info(douyin_own_videos)").fetchall()}
        for name, definition in {
            "analysis_status": "TEXT NOT NULL DEFAULT 'pending'",
            "analysis_json": "TEXT",
            "analysis_error": "TEXT",
            "analysis_updated_at": "DATETIME",
        }.items():
            if name not in columns:
                cursor.execute(f"ALTER TABLE douyin_own_videos ADD COLUMN {name} {definition}")
        cursor.execute("""
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
        """)
        export_columns = {row[1] for row in cursor.execute("PRAGMA table_info(douyin_own_export_runs)").fetchall()}
        for name, definition in {
            "user_info_id": "INTEGER",
            "account_name": "TEXT",
        }.items():
            if name not in export_columns:
                cursor.execute(f"ALTER TABLE douyin_own_export_runs ADD COLUMN {name} {definition}")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_douyin_own_export_runs_account "
            "ON douyin_own_export_runs(user_info_id, id DESC)"
        )
        conn.commit()


def create_export_run(db_path, user_info_id, account_name):
    ensure_tables(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        running = conn.execute(
            "SELECT id FROM douyin_own_export_runs WHERE user_info_id = ? AND status = 'running' LIMIT 1",
            (user_info_id,),
        ).fetchone()
        if running:
            raise ValueError("该账号正在同步，请勿重复启动")
        cursor = conn.execute(
            "INSERT INTO douyin_own_export_runs (user_info_id, account_name, status) VALUES (?, ?, 'running')",
            (user_info_id, account_name),
        )
        conn.commit()
        return cursor.lastrowid


def finish_export_run(db_path, run_id, status, file_path=None, imported_count=0, error_message=None):
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            UPDATE douyin_own_export_runs
            SET status = ?, file_path = ?, imported_count = ?, error_message = ?, finished_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (status, file_path, imported_count, error_message, run_id))
        conn.commit()


def get_latest_export_run(db_path, user_info_id):
    ensure_tables(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM douyin_own_export_runs WHERE user_info_id = ? ORDER BY id DESC LIMIT 1",
            (user_info_id,),
        ).fetchone()
    return dict(row) if row else None


def get_video(db_path, video_id):
    ensure_tables(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("""
            SELECT v.*, a.name AS account_name,
                m.play_count, m.completion_rate, m.five_sec_completion_rate,
                m.cover_click_rate, m.two_sec_bounce_rate, m.avg_play_duration,
                m.like_count, m.share_count, m.comment_count, m.collect_count,
                m.profile_visit_count, m.follower_delta
            FROM douyin_own_videos v
            LEFT JOIN douyin_own_accounts a ON a.id = v.account_id
            LEFT JOIN douyin_own_video_metrics m ON m.video_id = v.id
            WHERE v.id = ?
        """, (video_id,)).fetchone()
    return dict(row) if row else None


def set_analysis_status(db_path, video_id, status, analysis=None, error=None):
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            UPDATE douyin_own_videos
            SET analysis_status = ?, analysis_json = ?, analysis_error = ?,
                analysis_updated_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (status, json.dumps(analysis, ensure_ascii=False) if analysis is not None else None, error, video_id))
        conn.commit()


def list_analysis_peers(db_path, account_id):
    ensure_tables(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT v.*, m.play_count, m.completion_rate, m.five_sec_completion_rate,
                m.cover_click_rate, m.two_sec_bounce_rate, m.avg_play_duration,
                m.like_count, m.share_count, m.comment_count, m.collect_count,
                m.profile_visit_count, m.follower_delta
            FROM douyin_own_videos v
            LEFT JOIN douyin_own_video_metrics m ON m.video_id = v.id
            WHERE v.account_id = ?
        """, (account_id,)).fetchall()
    return [dict(row) for row in rows]


def upsert_account(db_path, user_info_id, account_name):
    ensure_tables(db_path)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT id FROM douyin_own_accounts WHERE user_info_id = ?",
            (user_info_id,),
        ).fetchone()
        if row:
            cursor.execute(
                "UPDATE douyin_own_accounts SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (row[0],),
            )
            conn.commit()
            return row[0]

        unbound = cursor.execute(
            "SELECT id FROM douyin_own_accounts WHERE name = ? AND user_info_id IS NULL",
            (account_name,),
        ).fetchone()
        if unbound:
            cursor.execute(
                "UPDATE douyin_own_accounts SET user_info_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (user_info_id, unbound[0]),
            )
            conn.commit()
            return unbound[0]

        stored_name = account_name
        if cursor.execute("SELECT 1 FROM douyin_own_accounts WHERE name = ?", (stored_name,)).fetchone():
            stored_name = f"{account_name} ({user_info_id})"
        cursor.execute("""
        INSERT INTO douyin_own_accounts (name, user_info_id)
        VALUES (?, ?)
        """, (stored_name, user_info_id))
        conn.commit()
        return cursor.lastrowid


def save_import(db_path, rows, user_info_id, account_name, source_key_fn):
    ensure_tables(db_path)
    account_id = upsert_account(db_path, user_info_id, account_name)
    inserted = 0
    updated = 0
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        for item in rows:
            source_key = source_key_fn(item)
            existing = cursor.execute(
                "SELECT id FROM douyin_own_videos WHERE account_id = ? AND source_key = ?",
                (account_id, source_key),
            ).fetchone()
            raw_data = json.dumps(item, ensure_ascii=False)
            cursor.execute("""
            INSERT INTO douyin_own_videos
                (account_id, source_key, title, video_url, published_at, content_format,
                 visibility_status, transcript, notes, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(account_id, source_key) DO UPDATE SET
                title = excluded.title,
                video_url = excluded.video_url,
                published_at = excluded.published_at,
                content_format = excluded.content_format,
                visibility_status = excluded.visibility_status,
                transcript = excluded.transcript,
                notes = excluded.notes,
                raw_data = excluded.raw_data,
                updated_at = CURRENT_TIMESTAMP
            """, (
                account_id, source_key, item.get("title"), item.get("video_url"),
                item.get("published_at"), item.get("content_format"),
                item.get("visibility_status"), item.get("transcript"),
                item.get("notes"), raw_data,
            ))
            video_id = cursor.execute(
                "SELECT id FROM douyin_own_videos WHERE account_id = ? AND source_key = ?",
                (account_id, source_key),
            ).fetchone()[0]
            cursor.execute("""
            INSERT INTO douyin_own_video_metrics
                (video_id, play_count, completion_rate, five_sec_completion_rate, cover_click_rate,
                 two_sec_bounce_rate, avg_play_duration, like_count, share_count, comment_count,
                 collect_count, profile_visit_count, follower_delta, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                play_count = excluded.play_count,
                completion_rate = excluded.completion_rate,
                five_sec_completion_rate = excluded.five_sec_completion_rate,
                cover_click_rate = excluded.cover_click_rate,
                two_sec_bounce_rate = excluded.two_sec_bounce_rate,
                avg_play_duration = excluded.avg_play_duration,
                like_count = excluded.like_count,
                share_count = excluded.share_count,
                comment_count = excluded.comment_count,
                collect_count = excluded.collect_count,
                profile_visit_count = excluded.profile_visit_count,
                follower_delta = excluded.follower_delta,
                raw_data = excluded.raw_data,
                updated_at = CURRENT_TIMESTAMP
            """, (
                video_id, item.get("play_count"), item.get("completion_rate"),
                item.get("five_sec_completion_rate"), item.get("cover_click_rate"),
                item.get("two_sec_bounce_rate"), item.get("avg_play_duration"),
                item.get("like_count"), item.get("share_count"), item.get("comment_count"),
                item.get("collect_count"), item.get("profile_visit_count"),
                item.get("follower_delta"), raw_data,
            ))
            if existing:
                updated += 1
            else:
                inserted += 1
        conn.commit()
    return {"account_id": account_id, "inserted": inserted, "updated": updated, "total": len(rows)}


def list_videos(db_path, user_info_id, limit=100):
    ensure_tables(db_path)
    try:
        limit = max(1, min(int(limit), 500))
    except Exception:
        limit = 100
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
        SELECT
            v.*, a.name AS account_name,
            m.play_count, m.completion_rate, m.five_sec_completion_rate,
            m.cover_click_rate, m.two_sec_bounce_rate, m.avg_play_duration,
            m.like_count, m.share_count, m.comment_count, m.collect_count,
            m.profile_visit_count, m.follower_delta
        FROM douyin_own_videos v
        JOIN douyin_own_accounts a ON a.id = v.account_id
        LEFT JOIN douyin_own_video_metrics m ON m.video_id = v.id
        WHERE a.user_info_id = ?
        ORDER BY COALESCE(v.published_at, v.created_at) DESC, v.id DESC
        LIMIT ?
        """, (user_info_id, limit)).fetchall()
    return [dict(row) for row in rows]


def list_all_videos(db_path, limit=100):
    ensure_tables(db_path)
    try:
        limit = max(1, min(int(limit), 500))
    except Exception:
        limit = 100
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
        SELECT
            v.*, a.name AS account_name, a.user_info_id,
            m.play_count, m.completion_rate, m.five_sec_completion_rate,
            m.cover_click_rate, m.two_sec_bounce_rate, m.avg_play_duration,
            m.like_count, m.share_count, m.comment_count, m.collect_count,
            m.profile_visit_count, m.follower_delta
        FROM douyin_own_videos v
        JOIN douyin_own_accounts a ON a.id = v.account_id
        LEFT JOIN douyin_own_video_metrics m ON m.video_id = v.id
        WHERE a.user_info_id IS NOT NULL
        ORDER BY COALESCE(v.published_at, v.created_at) DESC, v.id DESC
        LIMIT ?
        """, (limit,)).fetchall()
    return [dict(row) for row in rows]
