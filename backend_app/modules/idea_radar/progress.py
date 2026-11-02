from datetime import datetime


def update_progress(
    video_id, stage, percent, message, status="processing", *,
    registry, get_transcript, update_transcript, **values,
):
    registry.ensure_not_cancelled(video_id)
    current = get_transcript(video_id) or {}
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
    update_transcript(video_id, **payload)
    print(f"[观点雷达 {video_id}] {percent}% {message}", flush=True)
