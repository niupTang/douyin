import json
import math
import os
import shutil
import subprocess
from pathlib import Path


def run_media(tool, arguments):
    directory = os.environ.get("SAU_FFMPEG_DIR")
    executable = str(Path(directory) / f"{tool}.exe") if directory else shutil.which(tool)
    if not executable or not Path(executable).is_file():
        raise ValueError(f"未找到 {tool}，请配置 SAU_FFMPEG_DIR")
    try:
        result = subprocess.run(
            [executable, *arguments], capture_output=True, timeout=90,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError("视频处理超时，请重试") from exc
    if result.returncode:
        raise ValueError("视频无法处理，请检查格式和文件是否完整")
    return result.stdout


def probe(path):
    data = json.loads(run_media("ffprobe", [
        "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path),
    ]))
    stream = next((s for s in data.get("streams", []) if s["codec_type"] == "video"), None)
    if not stream:
        raise ValueError("文件不包含视频画面")
    numerator, denominator = stream.get("avg_frame_rate", "0/1").split("/")
    fps = float(numerator) / float(denominator) if float(denominator) else 0
    return {
        "width": stream["width"], "height": stream["height"], "fps": fps,
        "duration": float(data.get("format", {}).get("duration") or stream.get("duration") or 0),
    }


def extract_frame(source, target, seconds):
    try:
        seconds = float(seconds)
    except (ValueError, TypeError) as exc:
        raise ValueError("时间点必须为有效秒数") from exc
    info = probe(source)
    if not math.isfinite(seconds) or seconds < 0 or seconds >= info["duration"]:
        raise ValueError("时间点必须在视频时长范围内")
    run_media("ffmpeg", [
        "-v", "error", "-nostdin", "-i", str(source), "-ss", str(seconds),
        "-map", "0:v:0", "-frames:v", "1", "-y", str(target),
    ])
    if not target.is_file() or not target.stat().st_size:
        raise ValueError("该时间点没有可提取的画面")
    return seconds
