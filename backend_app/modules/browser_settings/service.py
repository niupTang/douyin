import re
from uuid import uuid4

from backend_app.common.browser_engine.downloads import validate_download_directory
from backend_app.common import app_settings as settings_repository


DOWNLOAD_DIRECTORY_KEY = "browser_download_directory"


def get_download_directory(db_path):
    value = settings_repository.get_app_setting(db_path, DOWNLOAD_DIRECTORY_KEY)
    if not value:
        return {"path": None, "valid": False}
    try:
        return {"path": str(validate_download_directory(value)), "valid": True}
    except ValueError:
        return {"path": str(value), "valid": False}


def require_download_directory(db_path):
    setting = get_download_directory(db_path)
    if not setting["valid"]:
        raise ValueError("下载目录未设置或已失效，请重新选择非 C 盘目录")
    return validate_download_directory(setting["path"])


def save_download_directory(db_path, value):
    path = validate_download_directory(value)
    settings_repository.set_app_setting(db_path, DOWNLOAD_DIRECTORY_KEY, str(path), "path")
    return {"path": str(path), "valid": True}


def save_markdown_download(db_path, filename, content):
    if not isinstance(content, str) or not content.strip() or len(content.encode("utf-8")) > 2_000_000:
        raise ValueError("Markdown 内容为空或超过 2 MB")
    stem = re.sub(r"[^\w\u4e00-\u9fff-]", "_", str(filename or "分析方案").removesuffix(".md"))[:80]
    target = require_download_directory(db_path) / f"{stem}-{uuid4().hex[:8]}.md"
    target.write_text(content, encoding="utf-8")
    return {"path": str(target)}
