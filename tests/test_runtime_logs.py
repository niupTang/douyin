import json

from backend_app.modules.runtime_logs.service import REDACTED_VALUE, RuntimeLogService, sanitise_context


def test_sanitises_nested_sensitive_values():
    context = sanitise_context({
        "Authorization": "Bearer secret-value",
        "nested": {"apiKey": "key-value"},
        "items": [{"token": "token-value"}],
        "safe": "value",
    })

    assert context == {
        "Authorization": REDACTED_VALUE,
        "nested": {"apiKey": REDACTED_VALUE},
        "items": [{"token": REDACTED_VALUE}],
        "safe": "value",
    }


def test_writes_bounded_valid_json_snapshot(tmp_path):
    logger = RuntimeLogService(tmp_path, max_entries=2)

    for index in range(3):
        assert logger.log(
            module="test",
            event="written",
            message=f"event {index}",
            context={"token": "never-write-this", "index": index},
        )

    payload = json.loads((tmp_path / "logs" / "backend.json").read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert len(payload["entries"]) == 2
    assert [entry["message"] for entry in payload["entries"]] == ["event 1", "event 2"]
    assert payload["entries"][0]["context"]["token"] == REDACTED_VALUE
    assert not (tmp_path / "logs" / "backend.json.tmp").exists()


def test_redacts_sensitive_text_in_message(tmp_path):
    logger = RuntimeLogService(tmp_path)

    assert logger.log(message="request Authorization: Bearer secret-token", event="request_failed")

    payload = json.loads((tmp_path / "logs" / "backend.json").read_text(encoding="utf-8"))
    assert "secret-token" not in payload["entries"][0]["message"]
    assert REDACTED_VALUE in payload["entries"][0]["message"]


def test_write_failure_does_not_raise(tmp_path):
    blocked_base_dir = tmp_path / "blocked"
    blocked_base_dir.write_text("not a directory", encoding="utf-8")
    logger = RuntimeLogService(blocked_base_dir)

    assert logger.log(message="business operation continues") is False
