import sqlite3

from backend_app.common.database import ensure_core_tables


def test_legacy_user_info_timestamp_columns_are_added_and_backfilled(tmp_path):
    db_path = tmp_path / "legacy.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE user_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type INTEGER NOT NULL,
                filePath TEXT NOT NULL,
                userName TEXT NOT NULL,
                status INTEGER DEFAULT 0,
                follower_count INTEGER DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            INSERT INTO user_info (type, filePath, userName, status)
            VALUES (3, 'legacy.json', '旧账号', 1)
            """
        )

    ensure_core_tables(db_path)

    with sqlite3.connect(db_path) as conn:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(user_info)").fetchall()
        }
        timestamps = conn.execute(
            "SELECT created_at, updated_at FROM user_info WHERE id = 1"
        ).fetchone()
        assert {"created_at", "updated_at"}.issubset(columns)
        assert timestamps[0] is not None
        assert timestamps[1] is not None
        conn.execute(
            """
            UPDATE user_info
            SET created_at = '2020-01-01 00:00:00',
                updated_at = '2020-01-02 00:00:00'
            WHERE id = 1
            """
        )

    ensure_core_tables(db_path)

    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT created_at, updated_at FROM user_info WHERE id = 1"
        ).fetchone() == ("2020-01-01 00:00:00", "2020-01-02 00:00:00")
