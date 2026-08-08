import tempfile
from datetime import datetime
from pathlib import Path


def run_pipeline(
    video_id,
    target_direction,
    *,
    force_transcription=False,
    load_video,
    get_transcript,
    update_progress,
    download_video,
    transcribe_media,
    clean_transcript,
    build_prompt,
    schema_factory,
    run_structured,
    get_agent_model,
    parse_metric_number,
    registry,
):
    try:
        video = load_video(video_id)
        if not video:
            raise RuntimeError("作品不存在")
        cached = get_transcript(video_id) or {}
        transcript = "" if force_transcription else (cached.get("cleaned_transcript") or "")
        if not transcript:
            update_progress(
                video_id, "downloading", 3, "正在准备下载视频", analysis_basis="title_only",
                target_direction=target_direction, radar_json=None, error_message=None,
            )
            with tempfile.TemporaryDirectory(prefix=f"idea-radar-{video_id}-") as work_dir:
                download_progress = {"value": -1}

                def report_download(percent, message):
                    overall = min(35, 5 + float(percent or 0) * 0.3)
                    rounded = int(round(overall))
                    if rounded <= download_progress["value"] and percent < 100:
                        return
                    download_progress["value"] = rounded
                    update_progress(video_id, "downloading", overall, message)

                media_path = download_video(
                    video.get("video_url"), work_dir, progress_callback=report_download
                )
                media_path_obj = Path(media_path)
                media_size_text = ""
                if media_path_obj.exists():
                    media_size_mb = media_path_obj.stat().st_size / (1024 * 1024)
                    media_size_text = f"（{media_size_mb:.1f} MB）"
                update_progress(
                    video_id, "transcribing", 38,
                    f"视频下载完成{media_size_text}，正在启动语音识别",
                )
                transcription_progress = {"value": -1}

                def report_transcription(percent, message, details=None):
                    details = details or {}
                    overall = min(78, 40 + float(percent or 0) * 0.38)
                    rounded = int(round(overall))
                    if rounded <= transcription_progress["value"] and percent < 100:
                        return
                    transcription_progress["value"] = rounded
                    duration = float(details.get("duration") or 0)
                    position = float(details.get("position") or 0)
                    detail_message = message
                    if duration and position:
                        detail_message = f"{message} / 共 {int(duration)} 秒"
                    update_progress(video_id, "transcribing", overall, detail_message)

                transcript_data, model = transcribe_media(
                    media_path, progress_callback=report_transcription
                )
            raw_transcript = (transcript_data.get("text") or "").strip()
            transcript = clean_transcript(raw_transcript)
            if not transcript:
                raise RuntimeError("Whisper 没有识别出有效视频文案")
            update_progress(
                video_id, "analyzing", 80, "转写完成，正在整理完整文案",
                analysis_basis="transcript",
                raw_transcript=raw_transcript, cleaned_transcript=transcript,
                segments=transcript_data.get("segments") or [], engine=transcript_data.get("engine"),
                model=model, language=transcript_data.get("language") or "zh",
                duration=transcript_data.get("duration") or 0, error_message=None,
            )
        else:
            update_progress(
                video_id, "analyzing", 80, "已读取历史转写，正在准备观点分析",
                analysis_basis="transcript",
                target_direction=target_direction, radar_json=None, error_message=None,
            )
        update_progress(video_id, "analyzing", 84, "正在调用 Hermes Gateway 拆解正文与内容机会")
        radar = run_structured(build_prompt(video, transcript, target_direction), schema_factory())
        try:
            selected_agent_model = get_agent_model()
            radar["agent_model"] = {
                "id": selected_agent_model.get("id"),
                "name": selected_agent_model.get("name"),
                "provider": selected_agent_model.get("provider"),
                "model": selected_agent_model.get("model"),
                "reasoning_effort": selected_agent_model.get("reasoningEffort") or None,
            }
        except Exception:
            radar["agent_model"] = None
        radar["radar_type"] = "transcript"
        radar["target_direction"] = target_direction
        radar["source"] = {
            "id": video.get("id"), "account_name": video.get("account_name") or "对标账号",
            "title": video.get("title"), "video_url": video.get("video_url"),
            "like_count": video.get("like_count") or "0",
            "like_score": parse_metric_number(video.get("like_count")),
            "cover_url": video.get("cover_url"),
        }
        update_progress(video_id, "analyzing", 96, "分析结果已生成，正在校验并保存")
        update_progress(
            video_id, "complete", 100, "解析完成", status="success",
            analysis_basis="transcript",
            target_direction=target_direction, radar_json=radar, error_message=None,
            finished_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        )
    except Exception as exc:
        if registry.is_cancelled(video_id):
            return
        current = get_transcript(video_id) or {}
        basis = "transcript" if current.get("cleaned_transcript") else "title_only"
        update_progress(
            video_id, current.get("stage") or "failed",
            current.get("progress_percent") or 0,
            f"处理失败：{str(exc)[:300]}", status="failed",
            analysis_basis=basis, error_message=str(exc),
            finished_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        )
    finally:
        registry.finish(video_id)
