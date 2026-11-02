"""Write bounded, structured backend diagnostics to a local JSON snapshot."""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REDACTED_VALUE = "[REDACTED]"
SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "cookies",
    "setcookie",
    "token",
    "refreshtoken",
    "accesstoken",
    "apikey",
    "api_key",
    "password",
    "secret",
    "license",
    "code",
}
TEXT_SECRET_PATTERNS = (
    re.compile(r"(?i)(bearer\s+)[^\s,;]+"),
    re.compile(
        r"(?i)(\b(?:authorization|cookie|token|refresh[_-]?token|access[_-]?token|api[_-]?key|password|secret|license|code)\s*[=:]\s*)[^\s,;&]+"
    ),
)


def _normalise_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _is_sensitive_key(key: Any) -> bool:
    normalised = _normalise_key(key)
    return normalised in SENSITIVE_KEYS or normalised.endswith("token") or normalised.endswith("cookie")


def redact_text(value: Any) -> str:
    """Return a display-safe string without common credential formats."""
    text = str(value)
    for pattern in TEXT_SECRET_PATTERNS:
        text = pattern.sub(lambda match: f"{match.group(1)}{REDACTED_VALUE}", text)
    return text


def sanitise_context(value: Any, *, key: Any | None = None) -> Any:
    """Recursively remove sensitive values while retaining useful diagnostics."""
    if key is not None and _is_sensitive_key(key):
        return REDACTED_VALUE
    if isinstance(value, dict):
        return {str(item_key): sanitise_context(item_value, key=item_key) for item_key, item_value in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [sanitise_context(item) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redact_text(value)


class RuntimeLogService:
    """Best-effort local diagnostics writer that never blocks business work."""

    def __init__(self, base_dir: str | Path, *, max_entries: int = 10_000):
        self._base_dir = Path(base_dir)
        self._max_entries = max(1, int(max_entries))
        self._lock = threading.RLock()

    @property
    def log_path(self) -> Path:
        return self._base_dir / "logs" / "backend.json"

    def log(
        self,
        *,
        level: str = "INFO",
        module: str = "backend",
        event: str = "message",
        message: Any = "",
        context: Any | None = None,
        duration_ms: int | float | None = None,
    ) -> bool:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": str(level or "INFO").upper(),
            "module": str(module or "backend"),
            "event": str(event or "message"),
            "message": redact_text(message),
            "durationMs": int(duration_ms) if duration_ms is not None else None,
            "context": sanitise_context(context or {}),
        }
        try:
            with self._lock:
                entries = self._read_entries()
                entries.append(entry)
                self._write_entries(entries[-self._max_entries :])
            return True
        except Exception:
            return False

    def _read_entries(self) -> list[dict[str, Any]]:
        try:
            payload = json.loads(self.log_path.read_text(encoding="utf-8"))
            entries = payload.get("entries", []) if isinstance(payload, dict) else []
            return [item for item in entries if isinstance(item, dict)]
        except (FileNotFoundError, OSError, ValueError, TypeError):
            return []

    def _write_entries(self, entries: list[dict[str, Any]]) -> None:
        log_path = self.log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "entries": entries,
        }
        temporary_path = log_path.with_suffix(".json.tmp")
        temporary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary_path.replace(log_path)
