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
