import os
from pathlib import Path
from backend_app.common.playwright_paths import resolve_browser_directory

APP_DIR = Path(os.environ.get("SAU_APP_DIR") or Path(__file__).parent).resolve()
BASE_DIR = Path(os.environ.get("SAU_BASE_DIR") or APP_DIR).resolve()
FFMPEG_DIR = os.environ.get("SAU_FFMPEG_DIR")
PLAYWRIGHT_BROWSERS_PATH = resolve_browser_directory(APP_DIR)
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = PLAYWRIGHT_BROWSERS_PATH
if FFMPEG_DIR:
    os.environ["PATH"] = f"{FFMPEG_DIR}{os.pathsep}{os.environ.get('PATH', '')}"
XHS_SERVER = "http://127.0.0.1:11901"
LOCAL_CHROME_PATH = ""
