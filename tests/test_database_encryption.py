import json
from pathlib import Path
import sqlite3
from contextlib import closing

import pytest
from sqlcipher3 import dbapi2 as cipher

from backend_app.common.database_encryption import (
    DatabaseEncryptionError, apply_key, encrypt_database, metadata_path, open_database,
)
from backend_app.common.database import ensure_core_tables


class PasswordStore:
    def __init__(self):
        self.values = {}

    def set(self, reference, password):
        self.values[reference] = password

    def get(self, reference):
        if reference not in self.values:
            raise DatabaseEncryptionError('missing password')
        return self.values[reference]

    def delete(self, reference):
        del self.values[reference]


def plain_database(path):
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript('''
            CREATE TABLE sample(id INTEGER PRIMARY KEY AUTOINCREMENT, value TEXT);
            CREATE INDEX idx_sample ON sample(value);
            CREATE TABLE audit(value TEXT);
            CREATE TRIGGER sample_audit AFTER INSERT ON sample BEGIN INSERT INTO audit VALUES(new.value); END;
            INSERT INTO sample(value) VALUES('中文内容');
            PRAGMA user_version=9;
        ''')


def test_migration_encrypts_database_and_backup_preserving_schema_and_rows(tmp_path):
    path = tmp_path / 'database.db'
    plain_database(path)
    store = PasswordStore()
    result = encrypt_database(path, 'test-password', password_store=store)
    assert result['status'] == 'encrypted'
    assert path.read_bytes()[:16] != b'SQLite format 3\x00'
    assert 'test-password' not in metadata_path(path).read_text()
    with sqlite3.connect(path) as conn:
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute('SELECT * FROM sample').fetchall()
    for database in (path, Path(result['backup'])):
        conn = open_database(database, password_store=store)
        try:
            assert conn.execute('SELECT value FROM sample').fetchone()[0] == '中文内容'
            assert conn.execute('PRAGMA user_version').fetchone()[0] == 9
            conn.execute("INSERT INTO sample(value) VALUES('more')")
            assert conn.execute('SELECT count(*) FROM audit').fetchone()[0] == 2
            conn.rollback()
        finally:
            conn.close()


def test_wrong_password_cannot_read_or_change_encrypted_database(tmp_path):
    path = tmp_path / 'database.db'
    plain_database(path)
    store = PasswordStore()
    encrypt_database(path, 'correct', password_store=store)
    reference = json.loads(metadata_path(path).read_text())['key_reference']
    store.values[reference] = 'wrong'
    with pytest.raises(cipher.DatabaseError):
        open_database(path, password_store=store)
    conn = cipher.connect(path)
    try:
        apply_key(conn, 'correct')
        assert conn.execute('SELECT count(*) FROM sample').fetchone()[0] == 1
    finally:
        conn.close()


def test_missing_metadata_fails_closed_and_original_password_can_restore_access(tmp_path):
    path = tmp_path / 'database.db'
    plain_database(path)
    store = PasswordStore()
    encrypt_database(path, 'correct', password_store=store)
    metadata_path(path).unlink()
    with pytest.raises(DatabaseEncryptionError, match='缺少'):
        open_database(path, password_store=store)
    encrypt_database(path, 'correct', password_store=store)
    conn = open_database(path, password_store=store)
    assert conn.execute('SELECT count(*) FROM sample').fetchone()[0] == 1
    conn.close()


def test_migration_failure_before_replace_leaves_plain_original_usable(tmp_path, monkeypatch):
    from backend_app.common import database_encryption as module
    path = tmp_path / 'database.db'
    plain_database(path)
    original_replace = module.os.replace

    def fail_final_replace(source, destination):
        if Path(destination) == path:
            raise OSError('file held by another process')
        return original_replace(source, destination)

    monkeypatch.setattr(module.os, 'replace', fail_final_replace)
    with pytest.raises(OSError):
        encrypt_database(path, 'correct', password_store=PasswordStore())
    with sqlite3.connect(path) as conn:
        assert conn.execute('SELECT count(*) FROM sample').fetchone()[0] == 1
    assert not metadata_path(path).exists()


def test_business_repository_reads_encrypted_database(tmp_path, monkeypatch):
    from backend_app.common import database_encryption as module
    from backend_app.modules.accounts import repository
    path = tmp_path / 'database.db'
    ensure_core_tables(path)
    store = PasswordStore()
    encrypt_database(path, 'correct', password_store=store)
    monkeypatch.setattr(module, 'DatabasePasswordStore', lambda: store)
    from backend_app.common.database import connect
    with connect(path) as conn:
        conn.execute("INSERT INTO user_info(type,filePath,userName) VALUES(3,'fixture','test')")
    with repository.sqlite3.connect(path) as conn:
        assert conn.execute('SELECT userName FROM user_info').fetchone()[0] == 'test'
