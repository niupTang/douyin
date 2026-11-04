import json
import sqlite3

from backend_app.agent.secret_store import MemoryMasterKeyProvider, SecretStore
from backend_app.modules.ai_settings import AiSettingsService


def create_service(tmp_path):
    return AiSettingsService(
        tmp_path / "database.db",
        secret_store=SecretStore(MemoryMasterKeyProvider()),
    )


def test_provider_secret_is_encrypted_and_public_shape_is_safe(tmp_path):
    service = create_service(tmp_path)
    service.save_provider(
        {
            "id": "hermes-default",
            "name": "Hermes Gateway",
            "provider_type": "hermes",
            "base_url": "http://127.0.0.1:8642",
            "timeout_seconds": 300,
        },
        "hermes-default",
    )
    service.set_credential("hermes-default", "sk-sensitive")

    providers = service.list_providers()
    raw_database = (tmp_path / "database.db").read_bytes()

    assert providers[0]["credentialConfigured"] is True
    assert "sk-sensitive" not in json.dumps(providers, ensure_ascii=False)
    assert b"sk-sensitive" not in raw_database
    assert service.legacy_settings()["hermes"]["apiKey"] == "sk-sensitive"


def test_legacy_settings_migration_is_idempotent(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "hermes": {
                    "gatewayUrl": "http://127.0.0.1:8642",
                    "apiKey": "legacy-key",
                    "timeout": 120,
                },
                "agentModels": [
                    {
                        "id": "model-one",
                        "name": "Model One",
                        "provider": "deepseek",
                        "model": "deepseek-chat",
                        "enabled": True,
                    }
                ],
                "taskModels": {"viralAnalysis": "model-one"},
                "codexCliPath": "codex",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    service = create_service(tmp_path)

    assert service.migrate_legacy_settings(settings_path) is True
    assert service.migrate_legacy_settings(settings_path) is False

    settings = service.legacy_settings()
    assert settings["hermes"]["apiKey"] == "legacy-key"
    assert settings["agentModels"][0]["id"] == "model-one"
    assert settings["taskModels"]["viralAnalysis"] == "model-one"
    assert settings["codexCliPath"] == "codex"
    with sqlite3.connect(tmp_path / "database.db") as connection:
        assert connection.execute("SELECT COUNT(*) FROM ai_model_profiles").fetchone()[0] == 2


def test_apply_legacy_settings_reconciles_models_and_clears_secret(tmp_path):
    service = create_service(tmp_path)
    service.apply_legacy_settings(
        {
            "hermes": {
                "gatewayUrl": "http://localhost:8642",
                "apiKey": "first-secret",
                "timeout": 90,
            },
            "agentModels": [
                {
                    "id": "old-model",
                    "name": "Old",
                    "provider": "gateway-default",
                    "model": "old",
                    "enabled": True,
                }
            ],
            "taskModels": {"viralAnalysis": "old-model"},
        }
    )

    settings = service.apply_legacy_settings(
        {
            "hermes": {
                "gatewayUrl": "http://localhost:8642",
                "apiKey": "",
                "timeout": 120,
            },
            "agentModels": [
                {
                    "id": "new-model",
                    "name": "New",
                    "provider": "deepseek",
                    "model": "new",
                    "enabled": True,
                }
            ],
            "taskModels": {"viralAnalysis": "new-model"},
        }
    )

    assert settings["hermes"]["apiKey"] == ""
    assert [model["id"] for model in settings["agentModels"]] == ["new-model"]
    assert settings["taskModels"]["viralAnalysis"] == "new-model"


def test_legacy_settings_migration_can_remove_plaintext_source(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "hermes": {
                    "gatewayUrl": "http://127.0.0.1:8642",
                    "apiKey": "legacy-secret",
                }
            }
        ),
        encoding="utf-8",
    )
    service = create_service(tmp_path)

    assert service.migrate_legacy_settings(settings_path, remove_source=True) is True
    assert not settings_path.exists()
    assert service.legacy_settings()["hermes"]["apiKey"] == "legacy-secret"


def test_invalid_legacy_provider_is_reported_without_blocking_and_can_retry(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps({"hermes": {"gatewayUrl": "http://remote.example:8642"}}),
        encoding="utf-8",
    )
    service = create_service(tmp_path)

    assert service.migrate_legacy_settings(settings_path, remove_source=True) is False
    assert settings_path.exists()
    assert service.legacy_migration_status()["status"] == "failed"
    assert "HTTPS" in service.legacy_migration_status()["message"]

    settings_path.write_text(
        json.dumps({"hermes": {"gatewayUrl": "https://remote.example"}}),
        encoding="utf-8",
    )

    assert service.migrate_legacy_settings(settings_path, remove_source=True) is True
    assert service.legacy_migration_status()["status"] == "complete"
    assert not settings_path.exists()
