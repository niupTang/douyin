import sqlite3

import pytest

from backend_app.agent.secret_store import (
    MemoryMasterKeyProvider,
    SecretStore,
    SecretStoreError,
)
from backend_app.common.database import ensure_core_tables


def test_secret_store_round_trip_never_contains_plaintext():
    store = SecretStore(MemoryMasterKeyProvider())

    encrypted = store.encrypt("sk-sensitive-value", "test-installation")

    assert store.decrypt(encrypted.as_dict()) == "sk-sensitive-value"
    assert "sk-sensitive-value" not in encrypted.ciphertext
    assert encrypted.algorithm == "AES-256-GCM"


def test_secret_store_rejects_different_master_key():
    encrypted = SecretStore(MemoryMasterKeyProvider()).encrypt("sk-secret", "one")

    with pytest.raises(SecretStoreError, match="无法解密"):
        SecretStore(MemoryMasterKeyProvider()).decrypt(encrypted.as_dict())


def test_ai_database_schema_enforces_encrypted_credentials(tmp_path):
    db_path = tmp_path / "database.db"
    ensure_core_tables(db_path)

    with sqlite3.connect(db_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]

    assert {
        "app_settings",
        "ai_providers",
        "ai_credentials",
        "ai_model_profiles",
        "agent_profiles",
        "agent_runs",
        "agent_run_events",
    }.issubset(table_names)
    assert journal_mode.lower() == "wal"
