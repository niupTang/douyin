"""Find complete browser installations matching the installed Playwright version."""
import json
import os
from pathlib import Path

import playwright


def required_browser_files():
    manifest = Path(playwright.__file__).parent / "driver" / "package" / "browsers.json"
    revisions = {
        item["name"]: item["revision"]
        for item in json.loads(manifest.read_text(encoding="utf-8"))["browsers"]
    }
    return (
        Path(f"chromium-{revisions['chromium']}") / "chrome-win" / "chrome.exe",
        Path(f"chromium_headless_shell-{revisions['chromium-headless-shell']}")
        / "chrome-win" / "headless_shell.exe",
    )


def resolve_browser_directory(app_dir, environ=None):
    env = os.environ if environ is None else environ
    root = Path(app_dir)
    packaged = env.get("SAU_PACKAGED") == "1"
    candidates = [env.get("SAU_BUNDLED_PLAYWRIGHT_PATH")] if packaged else [
        env.get("PLAYWRIGHT_BROWSERS_PATH"),
        root / "ms-playwright",
        root / "build-resources" / "ms-playwright",
    ]
    required = required_browser_files()
    for candidate in candidates:
        if not candidate:
            continue
        directory = Path(candidate).resolve()
        # Installed resources are read-only inputs, not browser download caches.
        if not packaged and directory.drive.upper() == "C:":
            continue
        if all((directory / relative).is_file() for relative in required):
            return str(directory)
    if packaged:
        raise RuntimeError("Packaged Playwright browser installation is missing or incomplete")
    return str(root / "ms-playwright")
