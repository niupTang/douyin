import json
import sqlite3
from datetime import datetime
from pathlib import Path

from backend_app.modules.benchmark.repository import ensure_tables


ALLOWED_TRANSCRIPT_FIELDS = {
    "status", "stage", "analysis_basis", "raw_transcript", "cleaned_transcript",
    "segments", "engine", "model", "language", "duration", "target_direction",
    "radar_json", "error_message", "progress_percent", "progress_message",
    "progress_log", "started_at", "finished_at",
}


def parse_transcript(row):
    if not row:
        return None
    item = dict(row)
    for key, fallback in (("segments", []), ("radar_json", None), ("progress_log", [])):
        try:
            default_json = "[]" if key in {"segments", "progress_log"} else "null"
            item[key] = json.loads(item.get(key) or default_json)
        except Exception:
            item[key] = fallback
    if item.get("status") == "success" and not item.get("progress_percent"):
        item["progress_percent"] = 100
    started_at = item.get("started_at")
    finished_at = item.get("finished_at")
    try:
        started = datetime.fromisoformat(started_at) if started_at else None
        ended = datetime.fromisoformat(finished_at) if finished_at else datetime.utcnow()
        item["elapsed_seconds"] = max(0, int((ended - started).total_seconds())) if started else 0
    except Exception:
        item["elapsed_seconds"] = 0
    item["can_retry"] = item.get("status") == "failed"
    return item


def get_transcript(db_path, video_id):
    ensure_tables(db_path)
    with sqlite3.connect(Path(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM douyin_benchmark_video_transcripts WHERE video_id = ?",
            (video_id,),
        ).fetchone()
    return parse_transcript(row)


def update_transcript(db_path, video_id, **values):
    ensure_tables(db_path)
    payload = {key: value for key, value in values.items() if key in ALLOWED_TRANSCRIPT_FIELDS}
    for key in ("segments", "radar_json", "progress_log"):
        if key in payload and not isinstance(payload[key], str):
            payload[key] = json.dumps(payload[key], ensure_ascii=False)
    with sqlite3.connect(Path(db_path)) as conn:
        conn.execute(
            "INSERT INTO douyin_benchmark_video_transcripts (video_id) VALUES (?) "
            "ON CONFLICT(video_id) DO NOTHING",
            (video_id,),
        )
        if payload:
            assignments = ", ".join(f"{key} = ?" for key in payload)
            conn.execute(
                f"UPDATE douyin_benchmark_video_transcripts SET {assignments}, "
                "updated_at = CURRENT_TIMESTAMP WHERE video_id = ?",
                (*payload.values(), video_id),
            )
        conn.commit()


def append_progress(db_path, video_id, stage, percent, message, status="processing", **values):
    current = get_transcript(db_path, video_id) or {}
    logs = list(current.get("progress_log") or [])
    percent = max(0, min(int(round(percent or 0)), 100))
    last_entry = logs[-1] if logs else {}
    if last_entry.get("message") != message or last_entry.get("percent") != percent:
        logs.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "stage": stage,
            "percent": percent,
            "message": message,
        })
        logs = logs[-60:]
    payload = {
        "status": status,
        "stage": stage,
        "progress_percent": percent,
        "progress_message": message,
        "progress_log": logs,
        **values,
    }
    update_transcript(db_path, video_id, **payload)
    return percent
