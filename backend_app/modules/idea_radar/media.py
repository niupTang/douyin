import asyncio
import json
import os
import re
import sys
from dataclasses import replace
from pathlib import Path

from backend_app.common.browser_engine import BrowserEngine, BrowserSpec, BrowserStrategyRegistry
from backend_app.common.browser_engine.downloads import validate_download_directory
from backend_app.common.browser_engine.shared import on_browser_worker


def write_netscape_cookie_file(storage_state_path, output_path):
    data = json.loads(Path(storage_state_path).read_text(encoding="utf-8"))
    lines = ["# Netscape HTTP Cookie File"]
    for cookie in data.get("cookies") or []:
        domain = cookie.get("domain") or ".douyin.com"
        include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
        path = cookie.get("path") or "/"
        secure = "TRUE" if cookie.get("secure") else "FALSE"
        expires = int(cookie.get("expires") or 0)
        lines.append("\t".join([
            domain, include_subdomains, path, secure, str(max(expires, 0)),
            cookie.get("name") or "", cookie.get("value") or "",
        ]))
    Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def download_with_ytdlp(video_url, output_dir, cookie_file, progress_callback=None, log=None):
    from yt_dlp import YoutubeDL

    output_dir = validate_download_directory(output_dir)
    output_template = str(Path(output_dir) / "source.%(ext)s")
    ffmpeg_dir = os.environ.get("SAU_FFMPEG_DIR")

    def progress_hook(status):
        if not progress_callback:
            return
        if status.get("status") == "finished":
            progress_callback(100, "视频下载完成")
            return
        if status.get("status") != "downloading":
            return
        total = status.get("total_bytes") or status.get("total_bytes_estimate") or 0
        downloaded = status.get("downloaded_bytes") or 0
        percent = min(99.0, downloaded * 100 / total) if total else 5.0
        details = [f"下载 {percent:.1f}%"]
        speed = str(status.get("_speed_str") or "").strip()
        eta = str(status.get("_eta_str") or "").strip()
        if speed and speed != "N/A":
            details.append(speed)
        if eta and eta != "N/A":
            details.append(f"剩余 {eta}")
        progress_callback(percent, " · ".join(details))

    options = {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 20,
        "retries": 2,
        "fragment_retries": 2,
        "merge_output_format": "mp4",
        "outtmpl": output_template,
        "paths": {"home": str(output_dir), "temp": str(output_dir)},
        "cachedir": str(output_dir / ".yt-dlp-cache"),
        "progress_hooks": [progress_hook],
    }
    if ffmpeg_dir and Path(ffmpeg_dir).exists():
        options["ffmpeg_location"] = ffmpeg_dir
    if cookie_file:
        options["cookiefile"] = str(cookie_file)
    if log:
        log(f"yt-dlp in-process ffmpeg dir: {ffmpeg_dir or '<none>'}")
    with YoutubeDL(options) as downloader:
        downloader.extract_info(video_url, download=True)
    candidates = sorted(
        (path for path in Path(output_dir).glob("source.*") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise RuntimeError("yt-dlp 下载完成但没有找到视频文件")
    return candidates[0]


class DouyinMediaDownloadStrategy:
    platform = "douyin"
    operation = "download_media"

    def browser_spec(self, request):
        from myUtils.douyin_benchmark import collection_browser_spec
        from myUtils.douyin_session import resolve_storage_state
        state = request["storage_state_path"]
        if not state or not Path(state).is_file():
            state = resolve_storage_state()
        spec = collection_browser_spec(state)
        options = dict(spec.context_options)
        if request.get("session_storage_state") is not None:
            options["storage_state"] = request["session_storage_state"]
        # A headed context cannot become headless. Copy its login state into
        # an isolated download context instead of opening a visible tab.
        return replace(spec, headless=True, presentation=None, shared_key=None,
                       context_options=options)

    async def execute(self, context, page, request):
        video_url = request["video_url"]
        output_path = request["output_path"]
        progress_callback = request["progress_callback"]
        media_urls = []

        def capture_response(response):
            content_type = (response.headers.get("content-type") or "").lower()
            if "video/" in content_type or ".mp4" in response.url:
                media_urls.append(response.url)

        from .media_transfer import download_media_candidates, media_candidates, MediaTransferError

        page.on("response", capture_response)
        try:
            if progress_callback:
                progress_callback(15, "备用下载：正在打开作品页")
            await page.goto(video_url, wait_until="domcontentloaded", timeout=60000)
            for refresh in range(2):
                await page.wait_for_timeout(7000 if not refresh else 3000)
                current_src = await page.evaluate(
                    "() => document.querySelector('video')?.currentSrc || document.querySelector('video')?.src || ''"
                )
                urls = media_candidates(current_src, media_urls)
                try:
                    result = await download_media_candidates(
                        context.request, urls, video_url, output_path, progress_callback,
                    )
                    if progress_callback:
                        progress_callback(100, "备用方式下载完成")
                    return result
                except MediaTransferError:
                    if refresh:
                        raise
                    if progress_callback:
                        progress_callback(45, "视频地址传输失败，正在刷新作品页重新获取")
                    media_urls.clear()
                    await page.reload(wait_until="domcontentloaded", timeout=60000)
        finally:
            page.remove_listener("response", capture_response)



@on_browser_worker
async def download_with_playwright(video_url, output_path, storage_state_path=None, progress_callback=None):
    from playwright.async_api import async_playwright

    output_path = Path(output_path)
    validate_download_directory(output_path.parent)
    from myUtils.douyin_session import resolve_storage_state, session_key
    from backend_app.common.browser_engine.shared import shared_contexts
    state = storage_state_path if storage_state_path else resolve_storage_state()
    entry = shared_contexts.entries.get(session_key(state))
    session_storage_state = None
    if entry and not entry[2]["closed"]:
        session_storage_state = await entry[1].storage_state()
    registry = BrowserStrategyRegistry()
    registry.register(DouyinMediaDownloadStrategy())
    from utils.base_social_media import set_init_script
    engine = BrowserEngine(registry, playwright_factory=async_playwright, init_context=set_init_script)
    return await engine.run("douyin", "download_media", {
        "video_url": video_url,
        "output_path": output_path,
        "storage_state_path": storage_state_path,
        "session_storage_state": session_storage_state,
        "progress_callback": progress_callback,
    })


def download_douyin_video(video_url, work_dir, *, base_dir, latest_cookie_file, progress_callback=None, log=None):
    work_dir = validate_download_directory(work_dir)
    cookie_name = latest_cookie_file()
    storage_state = Path(base_dir) / "cookiesFile" / cookie_name if cookie_name else None
    netscape_cookie = Path(work_dir) / "cookies.txt"
    if storage_state and storage_state.exists():
        write_netscape_cookie_file(storage_state, netscape_cookie)
    try:
        if progress_callback:
            progress_callback(2, "正在使用 yt-dlp 获取视频")
        return download_with_ytdlp(
            video_url, work_dir, netscape_cookie if netscape_cookie.exists() else None,
            progress_callback=progress_callback, log=log,
        )
    except Exception as primary_error:
        fallback_path = Path(work_dir) / "source-playwright.mp4"
        try:
            if progress_callback:
                progress_callback(5, "主下载方式失败，正在切换备用方式")
            return asyncio.run(download_with_playwright(
                video_url, fallback_path, storage_state, progress_callback=progress_callback,
            ))
        except Exception as fallback_error:
            raise RuntimeError(
                f"yt-dlp: {primary_error}; Playwright: {fallback_error}"
            ) from fallback_error


def transcribe_media(media_path, progress_callback=None, log=None, download_root=None):
    model = os.environ.get("IDEA_RADAR_WHISPER_MODEL", "base")
    language = "zh"
    device = os.environ.get("IDEA_RADAR_WHISPER_DEVICE", "cpu")
    compute_type = os.environ.get("IDEA_RADAR_WHISPER_COMPUTE_TYPE", "int8")
    media_path = Path(media_path)
    if not media_path.exists():
        raise FileNotFoundError(media_path)

    try:
        from faster_whisper import WhisperModel
    except ModuleNotFoundError as exc:
        raise RuntimeError("Missing faster-whisper dependency for local transcription") from exc

    if progress_callback:
        progress_callback(0, "正在启动本地语音识别")
        progress_callback(2, f"正在加载 Whisper {model} 模型")
    from .whisper_models import resolve_whisper_model
    model_source, local_only = resolve_whisper_model(model, download_root)
    if log:
        log(f"loading faster-whisper model={model} source={model_source} local_only={local_only} device={device} compute_type={compute_type}")
    whisper_model = WhisperModel(
        model_source, device=device, compute_type=compute_type,
        download_root=str(download_root) if download_root else None,
        local_files_only=local_only,
    )
    if progress_callback:
        progress_callback(5, "模型加载完成，正在读取音视频")

    segments, info = whisper_model.transcribe(
        str(media_path),
        language=language,
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
        if progress_callback and int(percent) > last_reported:
            last_reported = int(percent)
            progress_callback(percent, f"已识别到 {int(position)} 秒", {
                "position": round(position, 3),
                "duration": round(duration, 3),
            })

    if progress_callback:
        progress_callback(100, "视频文案识别完成")
    return {
        "engine": "faster-whisper",
        "language": getattr(info, "language", language),
        "duration": round(duration, 3),
        "text": "".join(text_parts).strip(),
        "segments": items,
    }, model


def clean_transcript_text(text):
    value = re.sub(r"[ \t]+", " ", str(text or ""))
    value = re.sub(r"\s*\n\s*", "\n", value)
    value = re.sub(r"([。！？!?，,])\1+", r"\1", value)
    return value.strip()
