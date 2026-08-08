from datetime import datetime
import threading


def idle_task(video_id):
    return {
        "video_id": video_id,
        "status": "idle",
        "stage": "idle",
        "analysis_basis": "title_only",
        "can_retry": False,
    }


def get_status(video_id, get_transcript):
    return get_transcript(video_id) or idle_task(video_id)


def start_pipeline_task(
    video_id,
    target_direction,
    *,
    current,
    registry,
    update_transcript,
    pipeline_fn,
    force=False,
    force_transcription=False,
):
    if (
        current and current.get("status") == "success" and not force
        and current.get("target_direction") == target_direction
    ):
        return current
    if not registry.start(video_id):
        return current or {"video_id": video_id, "status": "processing", "stage": "pending"}

    now_text = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    update_transcript(
        video_id, status="pending", stage="pending", target_direction=target_direction,
        progress_percent=0, progress_message="任务已创建，等待后台处理",
        progress_log=[{
            "time": datetime.now().strftime("%H:%M:%S"),
            "stage": "pending", "percent": 0, "message": "任务已创建，等待后台处理",
        }],
        started_at=now_text, finished_at=None, error_message=None,
        **({"radar_json": None} if force else {}),
    )
    thread = threading.Thread(
        target=pipeline_fn,
        args=(video_id, target_direction, force_transcription),
        daemon=True,
        name=f"idea-radar-{video_id}",
    )
    thread.start()
    return None
