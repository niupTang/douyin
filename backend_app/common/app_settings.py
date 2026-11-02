import json
from backend_app.common.database import connect


def _json_dump(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _json_load(value, default=None):
    try:
        return json.loads(value) if value not in (None, "") else default
    except (TypeError, json.JSONDecodeError):
        return default


def set_app_setting(db_path, key, value, value_type="json"):
    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO app_settings(key, value_json, value_type, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value_json=excluded.value_json,
                value_type=excluded.value_type,
                updated_at=CURRENT_TIMESTAMP
            """,
            (key, _json_dump(value), value_type),
        )


def get_app_setting(db_path, key, default=None):
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT value_json FROM app_settings WHERE key=?", (key,)
        ).fetchone()
    return _json_load(row["value_json"], default) if row else default
