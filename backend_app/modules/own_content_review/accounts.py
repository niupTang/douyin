import json
from backend_app.common import sqlite as sqlite3
from pathlib import Path


class DataAccountError(ValueError):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


def list_douyin_data_accounts(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, userName, status FROM user_info WHERE type = 3 ORDER BY id"
        ).fetchall()
    return [dict(row) for row in rows]


def get_douyin_data_account(db_path, user_info_id, require_active=False):
    try:
        account_id = int(user_info_id)
    except (TypeError, ValueError) as exc:
        raise DataAccountError("请选择账号中心中的抖音账号") from exc

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM user_info WHERE id = ?", (account_id,)).fetchone()
    if not row:
        raise DataAccountError("所选账号不存在")

    account = dict(row)
    if int(account.get("type") or 0) != 3:
        raise DataAccountError("所选账号不是抖音账号")
    if require_active and int(account.get("status") or 0) != 1:
        raise DataAccountError("账号登录态已失效，请到账号管理重新登录", status_code=409)
    return account


def resolve_douyin_data_account(db_path, user_info_id, base_dir):
    account = get_douyin_data_account(db_path, user_info_id, require_active=True)

    file_name = str(account.get("filePath") or "").strip()
    if not file_name or Path(file_name).is_absolute() or Path(file_name).name != file_name:
        raise DataAccountError("账号 Cookie 路径无效，请到账号管理重新登录", status_code=409)

    cookies_dir = (Path(base_dir) / "cookiesFile").resolve()
    cookie_path = (cookies_dir / file_name).resolve()
    if cookie_path.parent != cookies_dir or not cookie_path.is_file():
        raise DataAccountError("账号 Cookie 不存在，请到账号管理重新登录", status_code=409)

    try:
        state = json.loads(cookie_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DataAccountError("账号 Cookie 已损坏，请到账号管理重新登录", status_code=409) from exc
    if not isinstance(state, dict) or not isinstance(state.get("cookies"), list):
        raise DataAccountError("账号 Cookie 格式无效，请到账号管理重新登录", status_code=409)

    account["cookie_path"] = cookie_path
    return account
