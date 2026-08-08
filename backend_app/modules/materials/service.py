import os
import uuid
from pathlib import Path

from . import repository


def material_dir(base_dir):
    path = Path(base_dir) / "videoFile"
    path.mkdir(parents=True, exist_ok=True)
    return path


def sanitize_download_filename(filename):
    if not filename:
        raise ValueError("filename is required")
    if ".." in filename or filename.startswith("/") or filename.startswith("\\"):
        raise ValueError("Invalid filename")
    return filename


def save_temp_upload(file_storage, base_dir):
    generated = f"{uuid.uuid1()}_{file_storage.filename}"
    target = material_dir(base_dir) / generated
    file_storage.save(target)
    return generated


def save_material_upload(db_path, file_storage, base_dir, custom_filename=None):
    original_suffix = file_storage.filename.split(".")[-1] if "." in file_storage.filename else ""
    filename = f"{custom_filename}.{original_suffix}" if custom_filename else file_storage.filename
    final_filename = f"{uuid.uuid1()}_{filename}"
    target = material_dir(base_dir) / final_filename
    file_storage.save(target)
    filesize = round(float(os.path.getsize(target)) / (1024 * 1024), 2)
    repository.add_file_record(db_path, filename, filesize, final_filename)
    return {
        "filename": filename,
        "filepath": final_filename,
    }
