"""SQLCipher keys and verified, offline migration of a local SQLite database."""
import json
import os
from pathlib import Path
import shutil
import uuid
from datetime import datetime, timezone

from sqlcipher3 import dbapi2 as cipher


SQLITE_HEADER = b'SQLite format 3\x00'
KEY_SERVICE = 'Sunbird OS Database'


class DatabaseEncryptionError(RuntimeError):
    pass


class DatabasePasswordStore:
    def get(self, reference):
        import keyring
        password = keyring.get_password(KEY_SERVICE, reference)
        if not password:
            raise DatabaseEncryptionError('数据库密码不在当前用户的系统凭据库中，请使用原密码恢复配置')
        return password

    def set(self, reference, password):
        import keyring
        keyring.set_password(KEY_SERVICE, reference, password)

    def delete(self, reference):
        import keyring
        keyring.delete_password(KEY_SERVICE, reference)


def metadata_path(database):
    return Path(str(database) + '.cipher.json')


def plaintext_header(database):
    with Path(database).open('rb') as stream:
        return stream.read(16) == SQLITE_HEADER


def apply_key(connection, password):
    if not isinstance(password, str) or not password:
        raise DatabaseEncryptionError('数据库加密密码不能为空')
    # SQLite PRAGMA does not accept DB-API placeholders; escape the SQL literal.
    connection.execute("PRAGMA key = '" + password.replace("'", "''") + "'")
    connection.execute('PRAGMA temp_store=MEMORY')
    connection.execute('SELECT count(*) FROM sqlite_master').fetchone()


def open_database(database, *args, password_store=None, **kwargs):
    path = None if str(database) == ':memory:' else Path(database)
    if kwargs.get('uri') and str(database).startswith('file:'):
        from urllib.parse import urlsplit, unquote
        path = Path(unquote(urlsplit(str(database)).path))
    sidecar = metadata_path(path) if path is not None else None
    metadata = None
    if sidecar is not None and sidecar.exists():
        metadata = json.loads(sidecar.read_text(encoding='utf-8'))
        if metadata.get('version') != 1 or metadata.get('cipher') != 'sqlcipher':
            raise DatabaseEncryptionError('数据库加密配置版本不受支持')
    elif path is not None and path.is_file() and path.stat().st_size and not plaintext_header(path):
        raise DatabaseEncryptionError('数据库已加密或格式损坏，但缺少 .cipher.json 配置；不会创建明文替代文件')
    connection = cipher.connect(database, *args, **kwargs)
    try:
        if metadata:
            password = (password_store or DatabasePasswordStore()).get(metadata['key_reference'])
            apply_key(connection, password)
        return connection
    except BaseException:
        connection.close()
        raise


def _manifest(connection, schema='main'):
    tables = connection.execute(
        f"SELECT name FROM {schema}.sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return {
        name: connection.execute(f'SELECT count(*) FROM {schema}."' + name.replace('"', '""') + '"').fetchone()[0]
        for (name,) in tables
    }


def _write_metadata(path, metadata):
    temporary = Path(str(path) + '.tmp')
    with temporary.open('x', encoding='utf-8') as stream:
        json.dump(metadata, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def encrypt_database(database, password, *, password_store=None):
    """Call only after stopping every process using this database."""
    database = Path(database).resolve()
    if database.drive.upper() != 'E:':
        raise DatabaseEncryptionError('数据库和迁移文件必须位于 E 盘')
    if not database.is_file():
        raise DatabaseEncryptionError('数据库文件不存在')
    if not isinstance(password, str) or not password:
        raise DatabaseEncryptionError('数据库加密密码不能为空')
    store = password_store or DatabasePasswordStore()
    if not plaintext_header(database):
        connection = cipher.connect(str(database))
        try:
            apply_key(connection, password)
        finally:
            connection.close()
        sidecar = metadata_path(database)
        if sidecar.exists():
            existing = json.loads(sidecar.read_text(encoding='utf-8'))
            try:
                if store.get(existing['key_reference']) == password:
                    return {'status': 'already_encrypted', 'database': str(database)}
            except (KeyError, DatabaseEncryptionError):
                pass
        reference = 'db-' + uuid.uuid4().hex
        store.set(reference, password)
        _write_metadata(sidecar, {'version': 1, 'cipher': 'sqlcipher', 'key_reference': reference})
        return {'status': 'already_encrypted', 'database': str(database)}
    sidecar = metadata_path(database)
    if sidecar.exists():
        raise DatabaseEncryptionError('明文数据库已有加密配置，请先检查未完成的迁移')
    reference = 'db-' + uuid.uuid4().hex
    metadata = {'version': 1, 'cipher': 'sqlcipher', 'key_reference': reference}
    temporary = database.with_name(database.name + '.encrypting-' + uuid.uuid4().hex)
    backup_dir = database.parent / 'backups'
    backup_dir.mkdir(exist_ok=True)
    backup = backup_dir / ('database-encrypted-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8] + '.db')
    source = cipher.connect(str(database), timeout=5)
    metadata_written = False
    replaced = False
    key_saved = False
    try:
        if not source.execute('PRAGMA cipher_version').fetchone():
            raise DatabaseEncryptionError('当前数据库驱动不支持 SQLCipher')
        # This fails if an active reader/writer prevents leaving WAL mode.
        source.execute('PRAGMA busy_timeout=5000')
        source.execute('PRAGMA journal_mode=DELETE').fetchone()
        source.execute('PRAGMA temp_store=MEMORY')
        source.execute('BEGIN EXCLUSIVE')
        expected = _manifest(source)
        schema = source.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()
        user_version = source.execute('PRAGMA user_version').fetchone()[0]
        application_id = source.execute('PRAGMA application_id').fetchone()[0]
        source.execute('ATTACH DATABASE ? AS encrypted KEY ?', (str(temporary), password))
        source.execute("SELECT sqlcipher_export('encrypted')").fetchone()
        source.execute(f'PRAGMA encrypted.user_version={user_version}')
        source.execute(f'PRAGMA encrypted.application_id={application_id}')
        source.commit()
        source.execute('DETACH DATABASE encrypted')
        check = cipher.connect(str(temporary))
        try:
            apply_key(check, password)
            if check.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or _manifest(check) != expected:
                raise DatabaseEncryptionError('加密副本的数据完整性校验失败')
            if check.execute('PRAGMA cipher_integrity_check').fetchall():
                raise DatabaseEncryptionError('加密页校验失败')
            actual_schema = check.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()
            if actual_schema != schema:
                raise DatabaseEncryptionError('加密副本的表、索引或触发器结构不匹配')
        finally:
            check.close()
        store.set(reference, password)
        key_saved = True
        shutil.copy2(temporary, backup)
        _write_metadata(metadata_path(backup), metadata)
        _write_metadata(sidecar, metadata)
        metadata_written = True
        source.close()
        with temporary.open('r+b') as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, database)
        replaced = True
        return {'status': 'encrypted', 'database': str(database), 'backup': str(backup),
                'tables': len(expected), 'rows': sum(expected.values())}
    finally:
        source.close()
        if not replaced:
            if metadata_written:
                sidecar.unlink(missing_ok=True)
            if key_saved and not backup.exists():
                store.delete(reference)
        temporary.unlink(missing_ok=True)
