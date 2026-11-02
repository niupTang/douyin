from backend_app.common import sqlite as sqlite3


class AccountIdentityMismatch(ValueError):
    pass


def _account_from_row(row):
    if not row:
        return None
    item = dict(row)
    item["follower_count"] = item.get("follower_count") or 0
    item["name"] = (
        item.get("remark_name")
        or item.get("display_name")
        or item.get("userName")
    )
    return item


def list_accounts(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, type, filePath, userName, status, follower_count,
                   platform_user_id, display_name, remark_name,
                   last_validated_at, last_error_code, created_at, updated_at
            FROM user_info
            ORDER BY id
            """
        ).fetchall()
    accounts = []
    for row in rows:
        accounts.append(_account_from_row(row))
    return accounts


def bind_douyin_account(
    db_path,
    *,
    cookie_filename,
    platform_user_id,
    display_name,
    remark_name=None,
    existing_account_id=None,
):
    if not platform_user_id:
        raise ValueError("抖音账号身份不能为空")
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if existing_account_id is not None:
            target = conn.execute(
                "SELECT * FROM user_info WHERE id = ?", (int(existing_account_id),)
            ).fetchone()
            if not target or int(target["type"]) != 3:
                raise ValueError("要重新登录的抖音账号不存在")
            stored_identity = target["platform_user_id"]
            if stored_identity and stored_identity != platform_user_id:
                raise AccountIdentityMismatch("扫码账号与要重新登录的账号不一致")
            duplicate = conn.execute(
                """
                SELECT id FROM user_info
                WHERE type = 3 AND platform_user_id = ? AND id != ?
                """,
                (platform_user_id, int(existing_account_id)),
            ).fetchone()
            if duplicate:
                raise AccountIdentityMismatch("该抖音账号已绑定到另一条记录")
            account_id = int(existing_account_id)
            replaced_cookie = target["filePath"]
        else:
            target = conn.execute(
                "SELECT * FROM user_info WHERE type = 3 AND platform_user_id = ?",
                (platform_user_id,),
            ).fetchone()
            account_id = int(target["id"]) if target else None
            replaced_cookie = target["filePath"] if target else None

        legacy_name = remark_name or display_name
        if account_id is None:
            cursor = conn.execute(
                """
                INSERT INTO user_info
                    (type, filePath, userName, status, platform_user_id,
                     display_name, remark_name, last_validated_at,
                     last_error_code, updated_at)
                VALUES (3, ?, ?, 1, ?, ?, ?, CURRENT_TIMESTAMP, NULL, CURRENT_TIMESTAMP)
                """,
                (
                    cookie_filename,
                    legacy_name,
                    platform_user_id,
                    display_name,
                    remark_name,
                ),
            )
            account_id = cursor.lastrowid
        else:
            conn.execute(
                """
                UPDATE user_info
                SET filePath = ?, userName = ?, status = 1,
                    platform_user_id = ?, display_name = ?, remark_name = ?,
                    last_validated_at = CURRENT_TIMESTAMP,
                    last_error_code = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    cookie_filename,
                    legacy_name,
                    platform_user_id,
                    display_name,
                    remark_name,
                    account_id,
                ),
            )
        conn.commit()
        account = conn.execute(
            "SELECT * FROM user_info WHERE id = ?", (account_id,)
        ).fetchone()
    return {"account": _account_from_row(account), "replaced_cookie": replaced_cookie}


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
