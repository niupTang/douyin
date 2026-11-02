import json
from backend_app.common import sqlite as sqlite3
from contextlib import nullcontext
from pathlib import Path


def connect(db_path):
    connection = sqlite3.connect(Path(db_path))
    connection.row_factory = sqlite3.Row
    return connection


def ensure_tables(db_path):
    with sqlite3.connect(Path(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS douyin_benchmark_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            homepage_url TEXT NOT NULL UNIQUE,
            sec_uid TEXT,
            nickname TEXT,
            avatar TEXT,
            bio TEXT,
            followers_count TEXT,
            following_count TEXT,
            likes_count TEXT,
            received_likes_count TEXT,
            video_count TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            error_message TEXT,
            raw_data TEXT,
            last_sync_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        account_columns = {
            row[1] for row in cursor.execute(
                "PRAGMA table_info(douyin_benchmark_accounts)"
            ).fetchall()
        }
        if "received_likes_count" not in account_columns:
            cursor.execute(
                "ALTER TABLE douyin_benchmark_accounts "
                "ADD COLUMN received_likes_count TEXT"
            )
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS douyin_benchmark_videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
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
        video_info = cursor.execute("PRAGMA table_info(douyin_benchmark_videos)").fetchall()
        account_info = next((row for row in video_info if row[1] == "account_id"), None)
        if account_info and account_info[3]:
            cursor.execute("ALTER TABLE douyin_benchmark_videos RENAME TO douyin_benchmark_videos_legacy")
            cursor.execute('''
            CREATE TABLE douyin_benchmark_videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER,
                video_url TEXT NOT NULL,
                title TEXT,
                cover_url TEXT,
                like_count TEXT,
                comment_count TEXT,
                share_count TEXT,
                collect_count TEXT,
                raw_data TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                source_type TEXT NOT NULL DEFAULT 'account_sync',
                source_keyword TEXT,
                search_task_id INTEGER,
                source_rank INTEGER,
                author_name TEXT,
                author_url TEXT,
                author_sec_uid TEXT,
                video_type TEXT DEFAULT 'video',
                like_count_value INTEGER,
                UNIQUE(account_id, video_url)
            )
            ''')
            cursor.execute('''
            INSERT INTO douyin_benchmark_videos
                (id, account_id, video_url, title, cover_url, like_count, comment_count,
                 share_count, collect_count, raw_data, created_at)
            SELECT id, account_id, video_url, title, cover_url, like_count, comment_count,
                   share_count, collect_count, raw_data, created_at
            FROM douyin_benchmark_videos_legacy
            ''')
            cursor.execute("DROP TABLE douyin_benchmark_videos_legacy")
        video_columns = {row[1] for row in cursor.execute("PRAGMA table_info(douyin_benchmark_videos)").fetchall()}
        for column_name, definition in {
            "source_type": "TEXT NOT NULL DEFAULT 'account_sync'",
            "source_keyword": "TEXT",
            "search_task_id": "INTEGER",
            "source_rank": "INTEGER",
            "author_name": "TEXT",
            "author_url": "TEXT",
            "author_sec_uid": "TEXT",
            "video_type": "TEXT DEFAULT 'video'",
            "like_count_value": "INTEGER",
        }.items():
            if column_name not in video_columns:
                cursor.execute(f"ALTER TABLE douyin_benchmark_videos ADD COLUMN {column_name} {definition}")
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS douyin_content_search_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            target_count INTEGER NOT NULL DEFAULT 50,
            status TEXT NOT NULL DEFAULT 'pending',
            collected_count INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            started_at DATETIME,
            finished_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_benchmark_videos_source ON douyin_benchmark_videos(source_type, search_task_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_benchmark_videos_title ON douyin_benchmark_videos(title)")
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
        transcript_columns = {
            row[1] for row in cursor.execute(
                "PRAGMA table_info(douyin_benchmark_video_transcripts)"
            ).fetchall()
        }
        for column_name, definition in {
            "progress_percent": "INTEGER DEFAULT 0",
            "progress_message": "TEXT",
            "progress_log": "TEXT",
            "started_at": "DATETIME",
            "finished_at": "DATETIME",
        }.items():
            if column_name not in transcript_columns:
                cursor.execute(
                    f"ALTER TABLE douyin_benchmark_video_transcripts "
                    f"ADD COLUMN {column_name} {definition}"
                )
        conn.commit()


def list_accounts(db_path):
    ensure_tables(db_path)
    with connect(db_path) as conn:
        rows = conn.execute('''
        SELECT *,
            (SELECT COUNT(*) FROM douyin_benchmark_videos v WHERE v.account_id = a.id) AS synced_video_count
        FROM douyin_benchmark_accounts a
        ORDER BY id DESC
        ''').fetchall()
    return [dict(row) for row in rows]


def list_video_urls(db_path, account_id):
    ensure_tables(db_path)
    with sqlite3.connect(Path(db_path)) as conn:
        rows = conn.execute(
            "SELECT video_url FROM douyin_benchmark_videos WHERE account_id = ?",
            (account_id,)
        ).fetchall()
    return [row[0] for row in rows if row and row[0]]


def upsert_account(db_path, homepage_url, normalize_url, *, connection=None):
    homepage_url = normalize_url(homepage_url)
    if not homepage_url:
        raise ValueError("无效的抖音用户主页链接")
    if connection is None:
        ensure_tables(db_path)
    with (sqlite3.connect(Path(db_path)) if connection is None else nullcontext(connection)) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO douyin_benchmark_accounts (homepage_url, status)
        VALUES (?, 'pending')
        ON CONFLICT(homepage_url) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
        ''', (homepage_url,))
        if connection is None:
            conn.commit()
        row = cursor.execute(
            "SELECT id FROM douyin_benchmark_accounts WHERE homepage_url = ?",
            (homepage_url,)
        ).fetchone()
    return row[0]


def get_account_homepage(db_path, account_id):
    ensure_tables(db_path)
    with sqlite3.connect(Path(db_path)) as conn:
        row = conn.execute(
            "SELECT homepage_url FROM douyin_benchmark_accounts WHERE id = ?",
            (account_id,)
        ).fetchone()
    return row[0] if row else None


def list_videos(db_path, account_id):
    ensure_tables(db_path)
    with connect(db_path) as conn:
        rows = conn.execute('''
        SELECT * FROM douyin_benchmark_videos
        WHERE account_id = ?
        ORDER BY id DESC
        ''', (account_id,)).fetchall()
    return [dict(row) for row in rows]


def create_search_task(db_path, keyword, target_count):
    ensure_tables(db_path)
    with sqlite3.connect(Path(db_path)) as conn:
        cursor = conn.execute(
            "INSERT INTO douyin_content_search_tasks (keyword, target_count, status) VALUES (?, ?, 'pending')",
            (keyword, target_count),
        )
        conn.commit()
        return cursor.lastrowid


def update_search_task(db_path, task_id, **fields):
    ensure_tables(db_path)
    allowed = {"status", "collected_count", "error_message", "started_at", "finished_at"}
    values = {key: value for key, value in fields.items() if key in allowed}
    if not values:
        return
    values["updated_at"] = "CURRENT_TIMESTAMP"
    assignments = ", ".join(
        f"{key} = CURRENT_TIMESTAMP" if value == "CURRENT_TIMESTAMP" else f"{key} = ?"
        for key, value in values.items()
    )
    params = [value for value in values.values() if value != "CURRENT_TIMESTAMP"]
    params.append(task_id)
    with sqlite3.connect(Path(db_path)) as conn:
        conn.execute(f"UPDATE douyin_content_search_tasks SET {assignments} WHERE id = ?", params)
        conn.commit()


def get_search_task(db_path, task_id):
    ensure_tables(db_path)
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM douyin_content_search_tasks WHERE id = ?", (task_id,)).fetchone()
    return dict(row) if row else None


def list_search_results(db_path, task_id):
    ensure_tables(db_path)
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT v.*, a.nickname AS account_name FROM douyin_benchmark_videos v "
            "LEFT JOIN douyin_benchmark_accounts a ON a.id = v.account_id "
            "WHERE v.search_task_id = ? ORDER BY v.source_rank ASC, v.id ASC",
            (task_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_all_videos(db_path, keyword=None, source_type=None, limit=200):
    ensure_tables(db_path)
    clauses, params = [], []
    if keyword:
        clauses.append("(COALESCE(v.title, '') LIKE ? OR COALESCE(v.source_keyword, '') LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    if source_type:
        clauses.append("v.source_type = ?")
        params.append(source_type)
    params.append(max(1, min(int(limit or 200), 500)))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT v.*, a.nickname AS account_name FROM douyin_benchmark_videos v "
            f"LEFT JOIN douyin_benchmark_accounts a ON a.id = v.account_id {where} ORDER BY v.id DESC LIMIT ?",
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def save_search_results(db_path, task_id, keyword, videos):
    ensure_tables(db_path)
    inserted = 0
    with sqlite3.connect(Path(db_path)) as conn:
        for video in videos:
            url = video.get("video_url")
            if not url:
                continue
            existing = conn.execute("SELECT id FROM douyin_benchmark_videos WHERE video_url = ? LIMIT 1", (url,)).fetchone()
            if existing:
                conn.execute(
                    "UPDATE douyin_benchmark_videos SET search_task_id = COALESCE(search_task_id, ?), source_keyword = COALESCE(source_keyword, ?), "
                    "source_rank = COALESCE(source_rank, ?), author_name = COALESCE(author_name, ?), author_url = COALESCE(author_url, ?), "
                    "like_count = COALESCE(like_count, ?), like_count_value = COALESCE(like_count_value, ?) WHERE id = ?",
                    (task_id, keyword, video.get("source_rank"), video.get("author_name"), video.get("author_url"), video.get("like_count"), video.get("like_count_value"), existing[0]),
                )
                continue
            conn.execute(
                "INSERT INTO douyin_benchmark_videos (account_id, video_url, title, cover_url, like_count, raw_data, source_type, source_keyword, search_task_id, source_rank, author_name, author_url, author_sec_uid, video_type, like_count_value) VALUES (NULL, ?, ?, ?, ?, ?, 'content_search', ?, ?, ?, ?, ?, ?, ?, ?)",
                (url, video.get("title"), video.get("cover_url"), video.get("like_count"), json.dumps(video, ensure_ascii=False), keyword, task_id, video.get("source_rank"), video.get("author_name"), video.get("author_url"), video.get("author_sec_uid"), video.get("video_type") or "video", video.get("like_count_value")),
            )
            inserted += 1
        conn.commit()
    return inserted


def get_video(db_path, video_id, include_account=False):
    ensure_tables(db_path)
    with connect(db_path) as conn:
        if include_account:
            row = conn.execute(
                """
                SELECT v.*, a.nickname AS account_name
                FROM douyin_benchmark_videos v
                LEFT JOIN douyin_benchmark_accounts a ON a.id = v.account_id
                WHERE v.id = ?
                """,
                (video_id,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM douyin_benchmark_videos WHERE id = ?",
                (video_id,)
            ).fetchone()
    return dict(row) if row else None


def get_analysis(db_path, video_id):
    ensure_tables(db_path)
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM douyin_benchmark_video_analysis WHERE video_id = ?",
            (video_id,)
        ).fetchone()
    return dict(row) if row else None


def save_analysis(db_path, video_id, analysis):
    ensure_tables(db_path)
    with sqlite3.connect(Path(db_path)) as conn:
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
            json.dumps(analysis, ensure_ascii=False),
        ))
        conn.commit()


def delete_account_cascade(db_path, account_id):
    ensure_tables(db_path)
    with connect(db_path) as conn:
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

    with sqlite3.connect(Path(db_path)) as conn:
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
        account_count = max(cursor.rowcount, 0)
        conn.commit()

    return {
        "account": dict(account),
        "video_ids": video_ids,
        "deleted": {
            "accounts": account_count,
            "videos": video_count,
            "analysis": analysis_count,
            "transcripts": transcript_count,
        },
    }


def save_sync(db_path, account_id, data, *, connection=None):
    if connection is None:
        ensure_tables(db_path)
    with (sqlite3.connect(Path(db_path)) if connection is None else nullcontext(connection)) as conn:
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
            received_likes_count = ?,
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
            data.get("received_likes_count"),
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
        if connection is None:
            conn.commit()
    return stats


def save_error(db_path, account_id, error_message):
    ensure_tables(db_path)
    with sqlite3.connect(Path(db_path)) as conn:
        conn.execute('''
        UPDATE douyin_benchmark_accounts
        SET status = 'failed',
            error_message = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        ''', (error_message, account_id))
        conn.commit()


def list_idea_radar_videos(db_path, parse_metric_number, limit=80):
    ensure_tables(db_path)
    try:
        limit = max(1, min(int(limit), 200))
    except Exception:
        limit = 80
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT v.*, a.nickname AS account_name
            FROM douyin_benchmark_videos v
            LEFT JOIN douyin_benchmark_accounts a ON a.id = v.account_id
            WHERE COALESCE(v.title, '') != ''
            ORDER BY v.id DESC
            """
        ).fetchall()

    videos = []
    for row in rows:
        item = dict(row)
        item["like_score"] = parse_metric_number(item.get("like_count"))
        videos.append(item)
    videos.sort(key=lambda item: (item["like_score"], item.get("id") or 0), reverse=True)
    return videos[:limit]
