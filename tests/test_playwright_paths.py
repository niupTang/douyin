import pytest

from backend_app.common.playwright_paths import required_browser_files, resolve_browser_directory


def install_stub(directory):
    for relative in required_browser_files():
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()
    return str(directory.resolve())


def test_empty_and_wrong_revision_directories_fall_back_to_bundle(tmp_path):
    cache = tmp_path / "ms-playwright"
    (cache / "chromium-999" / "chrome-win").mkdir(parents=True)
    (cache / "chromium-999" / "chrome-win" / "chrome.exe").touch()
    bundled = tmp_path / "build-resources" / "ms-playwright"
    expected = install_stub(bundled)
    assert resolve_browser_directory(tmp_path, {"PLAYWRIGHT_BROWSERS_PATH": str(cache)}) == expected


def test_complete_explicit_directory_has_priority(tmp_path):
    custom = tmp_path / "custom"
    expected = install_stub(custom)
    assert resolve_browser_directory(tmp_path, {"PLAYWRIGHT_BROWSERS_PATH": str(custom)}) == expected


def test_missing_installation_stays_in_project_directory(tmp_path):
    assert resolve_browser_directory(tmp_path, {}) == str(tmp_path / "ms-playwright")


def test_packaged_installation_must_be_complete(tmp_path):
    with pytest.raises(RuntimeError, match="missing or incomplete"):
        resolve_browser_directory(tmp_path, {"SAU_PACKAGED": "1"})


@pytest.mark.parametrize("complete", [True, False])
def test_packaged_browser_on_c_drive_is_checked_for_completeness(monkeypatch, complete):
    from pathlib import PureWindowsPath
    from backend_app.common import playwright_paths

    class InstalledPath(PureWindowsPath):
        def resolve(self):
            return self

        def is_file(self):
            return complete

    monkeypatch.setattr(playwright_paths, "Path", InstalledPath)
    monkeypatch.setattr(playwright_paths, "required_browser_files", lambda: (
        PureWindowsPath("chromium-1169/chrome-win/chrome.exe"),
        PureWindowsPath("chromium_headless_shell-1169/chrome-win/headless_shell.exe"),
    ))
    directory = r"C:\Program Files\Sunbird OS\resources\ms-playwright"
    env = {"SAU_PACKAGED": "1", "SAU_BUNDLED_PLAYWRIGHT_PATH": directory}
    if complete:
        assert resolve_browser_directory(r"C:\Program Files\Sunbird OS", env) == directory
    else:
        with pytest.raises(RuntimeError, match="missing or incomplete"):
            resolve_browser_directory(r"C:\Program Files\Sunbird OS", env)


def test_development_still_rejects_c_drive_browser_cache(monkeypatch):
    from pathlib import PureWindowsPath
    from backend_app.common import playwright_paths

    class CachePath(PureWindowsPath):
        def resolve(self):
            return self

        def is_file(self):
            raise AssertionError("C drive download cache must not be used")

    monkeypatch.setattr(playwright_paths, "Path", CachePath)
    monkeypatch.setattr(playwright_paths, "required_browser_files", lambda: (PureWindowsPath("chrome.exe"),))
    assert resolve_browser_directory(r"C:\project", {
        "PLAYWRIGHT_BROWSERS_PATH": r"C:\cache",
    }) == str(PureWindowsPath(r"C:\project\ms-playwright"))
