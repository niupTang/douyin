import os
import tempfile
from pathlib import Path


def validate_download_directory(value):
    """Resolve a user-selected download directory before any file is written."""
    if not value or not str(value).strip():
        raise ValueError("请先选择下载目录")
    path = Path(str(value).strip()).expanduser()
    if not path.is_absolute():
        raise ValueError("下载目录必须是绝对路径")
    try:
        path = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError("下载目录不存在或无法访问") from exc
    if not path.is_dir():
        raise ValueError("下载目录必须是文件夹")
    if os.name == "nt" and path.drive.upper() == "C:":
        raise ValueError("下载目录不能位于 C 盘，请选择 E 盘或其他非 C 盘目录")
    try:
        with tempfile.TemporaryFile(dir=path):
            pass
    except OSError as exc:
        raise ValueError("下载目录不可写") from exc
    return path
