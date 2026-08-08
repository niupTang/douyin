import argparse
import json
import sys
from pathlib import Path


def emit_progress(percent, message, position=0, duration=0):
    print(json.dumps({
        "type": "progress",
        "percent": round(float(percent or 0), 1),
        "message": message,
        "position": round(float(position or 0), 3),
        "duration": round(float(duration or 0), 3),
    }, ensure_ascii=False), flush=True)


def transcribe_with_faster_whisper(media_path, model_name, language, device, compute_type):
    from faster_whisper import WhisperModel

    emit_progress(2, f"正在加载 Whisper {model_name} 模型")
    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    emit_progress(5, "模型加载完成，正在读取音频")
    segments, info = model.transcribe(
        str(media_path),
        language=language or None,
        vad_filter=True,
        beam_size=5,
    )
    items = []
    text_parts = []
    duration = float(getattr(info, "duration", 0) or 0)
    last_reported = -1
    for segment in segments:
        text = (segment.text or "").strip()
        if not text:
            continue
        text_parts.append(text)
        items.append({
            "start": round(float(segment.start or 0), 3),
            "end": round(float(segment.end or 0), 3),
            "text": text,
        })
        position = float(segment.end or 0)
        percent = min(99, (position / duration * 100)) if duration else 0
        if int(percent) > last_reported:
            last_reported = int(percent)
            emit_progress(percent, f"已识别到 {int(position)} 秒", position, duration)
    return {
        "engine": "faster-whisper",
        "language": getattr(info, "language", language),
        "duration": round(float(getattr(info, "duration", 0) or 0), 3),
        "text": "".join(text_parts).strip(),
        "segments": items,
    }


def transcribe_with_openai_whisper(media_path, model_name, language):
    import whisper

    emit_progress(2, f"正在加载 Whisper {model_name} 模型")
    model = whisper.load_model(model_name)
    emit_progress(8, "模型加载完成，正在识别音频")
    result = model.transcribe(str(media_path), language=language or None, fp16=False)
    segments = []
    for segment in result.get("segments", []) or []:
        text = (segment.get("text") or "").strip()
        if not text:
            continue
        segments.append({
            "start": round(float(segment.get("start") or 0), 3),
            "end": round(float(segment.get("end") or 0), 3),
            "text": text,
        })
    return {
        "engine": "openai-whisper",
        "language": result.get("language") or language,
        "duration": round(float(segments[-1]["end"]), 3) if segments else 0,
        "text": (result.get("text") or "").strip(),
        "segments": segments,
    }


def main():
    parser = argparse.ArgumentParser(description="Transcribe media with local Whisper.")
    parser.add_argument("--input", required=True, help="Input audio/video path.")
    parser.add_argument("--model", default="base", help="Whisper model name, e.g. tiny/base/small.")
    parser.add_argument("--language", default="zh", help="Language code, default zh.")
    parser.add_argument("--device", default="cpu", help="faster-whisper device, default cpu.")
    parser.add_argument("--compute-type", default="int8", help="faster-whisper compute type, default int8.")
    args = parser.parse_args()

    media_path = Path(args.input)
    if not media_path.exists():
        raise SystemExit(json.dumps({
            "ok": False,
            "error": f"Input file not found: {media_path}",
        }, ensure_ascii=False))

    try:
      emit_progress(0, "正在启动本地语音识别")
      try:
          result = transcribe_with_faster_whisper(
              media_path,
              model_name=args.model,
              language=args.language,
              device=args.device,
              compute_type=args.compute_type,
          )
      except ModuleNotFoundError:
          result = transcribe_with_openai_whisper(
              media_path,
              model_name=args.model,
              language=args.language,
          )
      emit_progress(100, "视频文案识别完成", result.get("duration") or 0, result.get("duration") or 0)
      print(json.dumps({"ok": True, "data": result}, ensure_ascii=False))
    except Exception as exc:
      print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
      raise SystemExit(1)


if __name__ == "__main__":
    main()
