import hashlib
import json
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class KouboStore:
    def __init__(self, database_path):
        self.database_path = Path(database_path)

    @contextmanager
    def connect(self):
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self):
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS koubo_projects (
                    id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL DEFAULT '',
                    script TEXT NOT NULL DEFAULT '',
                    script_version INTEGER NOT NULL DEFAULT 1,
                    title TEXT NOT NULL DEFAULT '',
                    tags TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'draft',
                    edit_template TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS koubo_devices (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    last_seen_at TEXT,
                    revoked_at TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS koubo_binding_codes (
                    code_hash TEXT PRIMARY KEY,
                    device_type TEXT NOT NULL DEFAULT 'mobile',
                    expires_at TEXT NOT NULL,
                    used_at TEXT
                );
                CREATE TABLE IF NOT EXISTS koubo_edit_jobs (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    worker_id TEXT,
                    template_snapshot TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    progress INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT,
                    lease_expires_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS koubo_assets (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    storage_path TEXT NOT NULL,
                    original_name TEXT,
                    size INTEGER NOT NULL DEFAULT 0,
                    checksum TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS koubo_upload_sessions (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    original_name TEXT NOT NULL,
                    total_size INTEGER NOT NULL,
                    chunk_size INTEGER NOT NULL,
                    total_chunks INTEGER NOT NULL,
                    received_chunks TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'uploading',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS koubo_publish_events (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    status TEXT NOT NULL,
                    platform_url TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )
            binding_columns = {
                row[1] for row in connection.execute(
                    "PRAGMA table_info(koubo_binding_codes)"
                ).fetchall()
            }
            if "device_type" not in binding_columns:
                connection.execute(
                    "ALTER TABLE koubo_binding_codes ADD COLUMN device_type TEXT NOT NULL DEFAULT 'mobile'"
                )

    @staticmethod
    def token_hash(token):
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create_project(self, payload):
        project_id = str(uuid.uuid4())
        now = utc_now()
        tags = payload.get("tags") if isinstance(payload.get("tags"), list) else []
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO koubo_projects
                (id, topic, script, title, tags, status, edit_template, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    project_id,
                    str(payload.get("topic", "")).strip(),
                    str(payload.get("script", "")).strip(),
                    str(payload.get("title", "")).strip(),
                    json.dumps(tags, ensure_ascii=False),
                    "draft",
                    payload.get("edit_template"),
                    now,
                    now,
                ),
            )
        return self.get_project(project_id)

    def list_projects(self):
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM koubo_projects ORDER BY updated_at DESC"
            ).fetchall()
        return [self._project(row) for row in rows]

    def get_project(self, project_id):
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM koubo_projects WHERE id = ?", (project_id,)
            ).fetchone()
        return self._project(row) if row else None

    def update_script(self, project_id, script):
        now = utc_now()
        with self.connect() as connection:
            result = connection.execute(
                """UPDATE koubo_projects
                SET script = ?, script_version = script_version + 1,
                    status = 'synced', updated_at = ?
                WHERE id = ?""",
                (script.strip(), now, project_id),
            )
        return self.get_project(project_id) if result.rowcount else None

    def set_project_status(self, project_id, status):
        with self.connect() as connection:
            result = connection.execute(
                "UPDATE koubo_projects SET status = ?, updated_at = ? WHERE id = ?",
                (status, utc_now(), project_id),
            )
        return self.get_project(project_id) if result.rowcount else None

    def create_binding_code(self, lifetime_minutes=10, device_type="mobile"):
        if device_type not in {"mobile", "worker"}:
            raise ValueError("invalid device type")
        code = secrets.token_urlsafe(24)
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=lifetime_minutes)).isoformat()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO koubo_binding_codes (code_hash, device_type, expires_at) VALUES (?, ?, ?)",
                (self.token_hash(code), device_type, expires_at),
            )
        return {"code": code, "type": device_type, "expires_at": expires_at}

    def claim_binding_code(self, code, name, device_type="mobile"):
        now = datetime.now(timezone.utc)
        code_hash = self.token_hash(code)
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM koubo_binding_codes WHERE code_hash = ?", (code_hash,)
            ).fetchone()
            if (
                not row
                or row["used_at"]
                or row["device_type"] != device_type
                or datetime.fromisoformat(row["expires_at"]) <= now
            ):
                return None
            token = secrets.token_urlsafe(48)
            device_id = str(uuid.uuid4())
            connection.execute(
                """INSERT INTO koubo_devices
                (id, name, type, token_hash, last_seen_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (device_id, name, device_type, self.token_hash(token), utc_now(), utc_now()),
            )
            connection.execute(
                "UPDATE koubo_binding_codes SET used_at = ? WHERE code_hash = ?",
                (utc_now(), code_hash),
            )
        return {"device_id": device_id, "token": token, "type": device_type}

    def list_devices(self):
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT id, name, type, last_seen_at, revoked_at, created_at
                FROM koubo_devices ORDER BY created_at DESC"""
            ).fetchall()
        return [dict(row) for row in rows]

    def revoke_device(self, device_id):
        with self.connect() as connection:
            result = connection.execute(
                "UPDATE koubo_devices SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
                (utc_now(), device_id),
            )
        return result.rowcount > 0

    def record_publish(self, project_id, platform, status, platform_url=None, error_message=None):
        event_id = str(uuid.uuid4())
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO koubo_publish_events
                (id, project_id, platform, status, platform_url, error_message, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    event_id,
                    project_id,
                    str(platform),
                    status,
                    platform_url,
                    error_message,
                    utc_now(),
                ),
            )
            connection.execute(
                "UPDATE koubo_projects SET status = ?, updated_at = ? WHERE id = ?",
                ("published" if status == "success" else "publish_failed", utc_now(), project_id),
            )
        return {
            "id": event_id,
            "project_id": project_id,
            "platform": str(platform),
            "status": status,
            "platform_url": platform_url,
            "error_message": error_message,
        }

    def authenticate(self, token, device_type=None):
        if not token:
            return None
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM koubo_devices WHERE token_hash = ? AND revoked_at IS NULL",
                (self.token_hash(token),),
            ).fetchone()
            if not row or (device_type and row["type"] != device_type):
                return None
            connection.execute(
                "UPDATE koubo_devices SET last_seen_at = ? WHERE id = ?",
                (utc_now(), row["id"]),
            )
        return dict(row)

    def create_edit_job(self, project_id, template, snapshot=None):
        project = self.get_project(project_id)
        if not project:
            return None
        job_id = str(uuid.uuid4())
        now = utc_now()
        snapshot = snapshot or {"id": template, "version": 1}
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO koubo_edit_jobs
                (id, project_id, template_snapshot, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)""",
                (job_id, project_id, json.dumps(snapshot), now, now),
            )
            connection.execute(
                "UPDATE koubo_projects SET status = 'waiting_edit', edit_template = ?, updated_at = ? WHERE id = ?",
                (template, now, project_id),
            )
        return self.get_job(job_id)

    def add_asset(self, project_id, kind, storage_path, original_name, size, checksum=None):
        asset_id = str(uuid.uuid4())
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO koubo_assets
                (id, project_id, kind, storage_path, original_name, size, checksum, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (asset_id, project_id, kind, storage_path, original_name, size, checksum, now),
            )
            if kind == "raw_video":
                connection.execute(
                    "UPDATE koubo_projects SET status = 'uploaded', updated_at = ? WHERE id = ?",
                    (now, project_id),
                )
            elif kind == "cover":
                connection.execute(
                    "UPDATE koubo_projects SET status = 'waiting_review', updated_at = ? WHERE id = ?",
                    (now, project_id),
                )
        return {
            "id": asset_id,
            "project_id": project_id,
            "kind": kind,
            "storage_path": storage_path,
            "original_name": original_name,
            "size": size,
            "checksum": checksum,
            "created_at": now,
        }

    def list_assets(self, project_id):
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM koubo_assets WHERE project_id = ? ORDER BY created_at",
                (project_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_asset(self, asset_id):
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM koubo_assets WHERE id = ?", (asset_id,)
            ).fetchone()
        return dict(row) if row else None

    def create_upload_session(
        self, project_id, device_id, original_name, total_size, chunk_size, total_chunks
    ):
        session_id = str(uuid.uuid4())
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO koubo_upload_sessions
                (id, project_id, device_id, original_name, total_size, chunk_size,
                 total_chunks, received_chunks, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, '[]', ?, ?)""",
                (
                    session_id,
                    project_id,
                    device_id,
                    original_name,
                    total_size,
                    chunk_size,
                    total_chunks,
                    now,
                    now,
                ),
            )
        return self.get_upload_session(session_id)

    def get_upload_session(self, session_id):
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM koubo_upload_sessions WHERE id = ?", (session_id,)
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["received_chunks"] = json.loads(result["received_chunks"])
        return result

    def mark_chunk_received(self, session_id, device_id, chunk_index):
        with self.connect() as connection:
            row = connection.execute(
                "SELECT received_chunks FROM koubo_upload_sessions WHERE id = ? AND device_id = ? AND status = 'uploading'",
                (session_id, device_id),
            ).fetchone()
            if not row:
                return None
            received = set(json.loads(row["received_chunks"]))
            received.add(int(chunk_index))
            connection.execute(
                "UPDATE koubo_upload_sessions SET received_chunks = ?, updated_at = ? WHERE id = ?",
                (json.dumps(sorted(received)), utc_now(), session_id),
            )
        return self.get_upload_session(session_id)

    def complete_upload_session(self, session_id, device_id):
        with self.connect() as connection:
            result = connection.execute(
                """UPDATE koubo_upload_sessions
                SET status = 'completed', updated_at = ?
                WHERE id = ? AND device_id = ? AND status = 'uploading'""",
                (utc_now(), session_id, device_id),
            )
        return self.get_upload_session(session_id) if result.rowcount else None

    def update_job(self, job_id, worker_id, status, progress=0, error_message=None):
        now = utc_now()
        project_status = {
            "editing": "editing",
            "completed": "waiting_cover",
            "failed": "edit_failed",
        }.get(status)
        with self.connect() as connection:
            row = connection.execute(
                "SELECT project_id FROM koubo_edit_jobs WHERE id = ? AND worker_id = ?",
                (job_id, worker_id),
            ).fetchone()
            if not row:
                return None
            connection.execute(
                """UPDATE koubo_edit_jobs
                SET status = ?, progress = ?, error_message = ?, updated_at = ?
                WHERE id = ? AND worker_id = ?""",
                (status, progress, error_message, now, job_id, worker_id),
            )
            if project_status:
                connection.execute(
                    "UPDATE koubo_projects SET status = ?, updated_at = ? WHERE id = ?",
                    (project_status, now, row["project_id"]),
                )
        return self.get_job(job_id)

    def get_job(self, job_id):
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM koubo_edit_jobs WHERE id = ?", (job_id,)
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["template_snapshot"] = json.loads(result["template_snapshot"])
        return result

    def claim_job(self, worker_id, lease_minutes=15):
        now = datetime.now(timezone.utc)
        lease = (now + timedelta(minutes=lease_minutes)).isoformat()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT * FROM koubo_edit_jobs
                WHERE status = 'queued'
                   OR (status = 'editing' AND lease_expires_at < ?)
                ORDER BY created_at LIMIT 1""",
                (now.isoformat(),),
            ).fetchone()
            if not row:
                return None
            connection.execute(
                """UPDATE koubo_edit_jobs
                SET status = 'editing', worker_id = ?, lease_expires_at = ?, updated_at = ?
                WHERE id = ?""",
                (worker_id, lease, utc_now(), row["id"]),
            )
            connection.execute(
                "UPDATE koubo_projects SET status = 'editing', updated_at = ? WHERE id = ?",
                (utc_now(), row["project_id"]),
            )
        job = self.get_job(row["id"])
        job["project"] = self.get_project(row["project_id"])
        job["assets"] = self.list_assets(row["project_id"])
        return job

    @staticmethod
    def _project(row):
        if not row:
            return None
        result = dict(row)
        result["tags"] = json.loads(result["tags"] or "[]")
        return result
