import os
from pathlib import Path

from backend_app.modules.ai_settings import AiSettingsService


def settings_path(base_dir):
    """Compatibility name retained for callers; settings now live in SQLite."""
    return Path(base_dir) / "db" / "database.db"


def load_runtime_settings(base_dir):
    service = AiSettingsService(settings_path(base_dir))
    return service.legacy_settings()


def save_runtime_settings(base_dir, settings):
    return AiSettingsService(settings_path(base_dir)).apply_legacy_settings(settings)


def get_runtime_setting(base_dir, *keys, env=None, default=None):
    if env and os.environ.get(env):
        return os.environ.get(env)
    settings = load_runtime_settings(base_dir)
    for key in keys:
        value = settings.get(key)
        if value:
            return value
    return default
