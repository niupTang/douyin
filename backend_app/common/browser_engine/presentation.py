"""Present the actual collection browser without changing its desktop viewport."""

import logging
import os
import sys
from pathlib import Path

from playwright.async_api import Error as PlaywrightError

from .downloads import validate_download_directory


log = logging.getLogger(__name__)
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 700


def floating_enabled():
    mode = os.environ.get("SAU_BROWSER_PRESENTATION", "headless").strip().lower()
    if mode not in {"floating", "headless"}:
        raise ValueError("SAU_BROWSER_PRESENTATION 仅支持 floating 或 headless")
    if mode == "headless":
        return False
    return sys.platform in {"win32", "darwin"} or bool(
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    )


def prepare_floating_launch(options):
    options = dict(options)
    visible = floating_enabled()
    # Playwright also creates temporary profiles and download artifacts. Keep
    # those on the app's data drive, including when started outside Electron.
    root = Path(os.environ.get("SAU_BASE_DIR") or Path(__file__).resolve().parents[3])
    root = validate_download_directory(root)
    cache = root / ".sau-cache" / "browser"
    cache.mkdir(parents=True, exist_ok=True)
    cache = validate_download_directory(cache)
    # The Node driver creates profiles before spawning Chromium, so its own
    # environment (not just launch(env=...)) must use the same temp directory.
    for key in ("TEMP", "TMP", "TMPDIR"):
        os.environ[key] = str(cache)
    options["env"] = {
        **os.environ,
        **options.get("env", {}),
        "TEMP": str(cache), "TMP": str(cache), "TMPDIR": str(cache),
    }
    options.setdefault("downloads_path", str(cache))
    if visible:
        args = [arg for arg in options.get("args", []) if not arg.startswith(
            ("--window-size=", "--window-position=", "--start-maximized")
        )]
        options["args"] = [*args, f"--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}",
                           "--window-position=24,80", "--mute-audio"]
    return not visible, options


async def configure_floating_page(context, page, viewport):
    """Scale the desktop page into a small window; selectors keep their layout."""
    session = await context.new_cdp_session(page)
    target = await session.send("Browser.getWindowForTarget")
    await session.send("Browser.setWindowBounds", {
        "windowId": target["windowId"],
        "bounds": {"windowState": "normal"},
    })
    await session.send("Browser.setWindowBounds", {
        "windowId": target["windowId"],
        "bounds": {"width": WINDOW_WIDTH, "height": WINDOW_HEIGHT},
    })
    if viewport:
        scale = min((WINDOW_WIDTH - 20) / viewport["width"],
                    (WINDOW_HEIGHT - 120) / viewport["height"], 1)
        await session.send("Emulation.setDeviceMetricsOverride", {
            "width": viewport["width"], "height": viewport["height"],
            "deviceScaleFactor": 1, "mobile": False, "scale": scale,
        })
    # Keep the CDP session attached until context.close(), otherwise Chromium
    # restores device metrics and the original large viewport no longer fits.
    if sys.platform == "win32" and context.browser:
        browser_session = await context.browser.new_browser_cdp_session()
        try:
            processes = await browser_session.send("SystemInfo.getProcessInfo")
            browser_pid = next((item["id"] for item in processes["processInfo"]
                                if item["type"] == "browser"), None)
            if browser_pid:
                pin_browser_window(browser_pid)
        except (PlaywrightError, OSError):
            # Window decoration is optional; the real headed browser remains usable.
            log.warning("采集窗口置顶失败，继续使用普通可见窗口")
        finally:
            await browser_session.detach()


def pin_browser_window(browser_pid):
    """Pin only windows owned by this task's Chromium, never another browser."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT,
                                           ctypes.c_void_p, wintypes.UINT]
    work_area = wintypes.RECT()
    if not user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(work_area), 0):
        raise ctypes.WinError(ctypes.get_last_error())

    @callback_type
    def visit(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value != int(browser_pid) or not user32.IsWindowVisible(hwnd):
            return True
        class_name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_name, len(class_name))
        if class_name.value != "Chrome_WidgetWin_1":
            return True
        bounds = wintypes.RECT()
        if user32.GetWindowRect(hwnd, ctypes.byref(bounds)):
            left = max(work_area.left, work_area.right - (bounds.right - bounds.left) - 20)
            top = max(work_area.top, work_area.bottom - (bounds.bottom - bounds.top) - 20)
            # HWND_TOPMOST, SWP_NOSIZE | SWP_NOACTIVATE: draggable, minimizable,
            # and above the app without stealing keyboard focus on every action.
            user32.SetWindowPos(hwnd, wintypes.HWND(-1), left, top, 0, 0, 0x0001 | 0x0010)
        return True

    user32.EnumWindows(visit, 0)
