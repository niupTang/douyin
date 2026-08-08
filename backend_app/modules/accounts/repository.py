import sqlite3


def update_follower_count(db_path, account_id, follower_count):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE user_info SET follower_count = ? WHERE id = ?",
            (int(follower_count), account_id),
        )
        conn.commit()


def list_followers(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, userName, type, follower_count, status FROM user_info ORDER BY id"
        ).fetchall()
    accounts = []
    for row in rows:
        item = dict(row)
        item["follower_count"] = item.get("follower_count") or 0
        accounts.append(item)
    return accounts


def list_accounts_raw(db_path):
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM user_info").fetchall()
    return [list(row) for row in rows]


def mark_account_invalid(db_path, account_id):
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE user_info SET status = ? WHERE id = ?", (0, account_id))
        conn.commit()


def update_account_info(db_path, account_id, platform_type, username):
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
        UPDATE user_info
        SET type = ?,
            userName = ?
        WHERE id = ?
        """, (platform_type, username, account_id))
        conn.commit()


def delete_account(db_path, account_id):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM user_info WHERE id = ?",
            (account_id,),
        ).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM user_info WHERE id = ?", (account_id,))
        conn.commit()
    return dict(row)


def validate_account_files_for_platform(db_path, platform_type, account_list):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        for account_file in account_list or []:
            row = cursor.execute(
                "SELECT type, userName FROM user_info WHERE filePath = ?",
                (account_file,),
            ).fetchone()
            if not row:
                raise ValueError(f"账号不存在或未登录: {account_file}")
            if int(row[0]) != int(platform_type):
                raise ValueError(f"账号 {row[1]} 不属于当前发布平台，请重新选择账号")


def latest_douyin_cookie_file(db_path):
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("""
        SELECT filePath FROM user_info
        WHERE type = 3 AND status = 1
        ORDER BY id DESC
        LIMIT 1
        """).fetchone()
        return row[0] if row else None
