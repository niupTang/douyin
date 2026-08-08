import json
import os
from pathlib import Path


def settings_path(base_dir):
    return Path(base_dir) / "settings.json"


def load_runtime_settings(base_dir):
    path = settings_path(base_dir)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_runtime_settings(base_dir, settings):
    path = settings_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary_path.replace(path)


def get_runtime_setting(base_dir, *keys, env=None, default=None):
    if env and os.environ.get(env):
        return os.environ.get(env)
    settings = load_runtime_settings(base_dir)
    for key in keys:
        value = settings.get(key)
        if value:
            return value
    return default
