import json
import uuid

from backend_app.common.database import connect


def _dump(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _load(value, default=None):
    try:
        return json.loads(value) if value not in (None, "") else default
    except (TypeError, json.JSONDecodeError):
        return default


def create_run(db_path, agent_key, input_payload):
    run_id = uuid.uuid4().hex
    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO agent_runs(id, agent_key, status, input_json)
            VALUES (?, ?, 'queued', ?)
            """,
            (run_id, agent_key, _dump(input_payload or {})),
        )
    return get_run(db_path, run_id)


def get_run(db_path, run_id):
    with connect(db_path) as connection:
        row = connection.execute("SELECT * FROM agent_runs WHERE id=?", (run_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    data["input"] = _load(data.pop("input_json"), {})
    data["output"] = _load(data.pop("output_json"), None)
    return data


def update_run(db_path, run_id, status, *, output=None, error_code=None, error_message=None, model_profile_id=None):
    allowed = {"queued", "running", "succeeded", "failed", "cancelled", "interrupted"}
    if status not in allowed:
        raise ValueError("无效的 Agent Run 状态")
    started_sql = "CURRENT_TIMESTAMP" if status == "running" else "started_at"
    finished_sql = "CURRENT_TIMESTAMP" if status in {"succeeded", "failed", "cancelled", "interrupted"} else "finished_at"
    with connect(db_path) as connection:
        connection.execute(
            f"""
            UPDATE agent_runs SET
                status=?, output_json=?, error_code=?, error_message=?,
                model_profile_id=COALESCE(?, model_profile_id),
                started_at={started_sql}, finished_at={finished_sql}
            WHERE id=?
            """,
            (
                status,
                _dump(output) if output is not None else None,
                error_code,
                error_message,
                model_profile_id,
                run_id,
            ),
        )
    return get_run(db_path, run_id)


def append_event(db_path, run_id, event_type, payload=None):
    with connect(db_path) as connection:
        sequence = connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 FROM agent_run_events WHERE run_id=?",
            (run_id,),
        ).fetchone()[0]
        connection.execute(
            """
            INSERT INTO agent_run_events(run_id, event_type, sequence, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            (run_id, event_type, sequence, _dump(payload or {})),
        )
    return sequence


def list_events(db_path, run_id):
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, run_id, event_type, sequence, payload_json, created_at
            FROM agent_run_events WHERE run_id=? ORDER BY sequence
            """,
            (run_id,),
        ).fetchall()
    return [
        {
            **{key: row[key] for key in ("id", "run_id", "event_type", "sequence", "created_at")},
            "payload": _load(row["payload_json"], {}),
        }
        for row in rows
    ]


def mark_unfinished_interrupted(db_path):
    with connect(db_path) as connection:
        cursor = connection.execute(
            """
            UPDATE agent_runs
            SET status='interrupted', error_code='backend_restarted',
                error_message='后端重启，任务已中断', finished_at=CURRENT_TIMESTAMP
            WHERE status IN ('queued', 'running')
            """
        )
    return cursor.rowcount


def request_cancel(db_path, run_id):
    run = get_run(db_path, run_id)
    if not run:
        return None
    if run["status"] in {"queued", "running"}:
        return update_run(
            db_path,
            run_id,
            "cancelled",
            error_code="cancelled_by_user",
            error_message="任务已由用户取消",
        )
    return run
