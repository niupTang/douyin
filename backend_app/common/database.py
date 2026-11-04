from backend_app.common import sqlite as sqlite3
from pathlib import Path


def connect(db_path):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


def ensure_core_tables(db_path):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type INTEGER NOT NULL,
            filePath TEXT NOT NULL,
            userName TEXT NOT NULL,
            status INTEGER DEFAULT 0,
            follower_count INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        user_info_columns = {
            row[1] for row in cursor.execute("PRAGMA table_info(user_info)").fetchall()
        }
        if "follower_count" not in user_info_columns:
            cursor.execute(
                "ALTER TABLE user_info ADD COLUMN follower_count INTEGER DEFAULT 0"
            )
        account_columns = {
            "platform_user_id": "TEXT",
            "display_name": "TEXT",
            "remark_name": "TEXT",
            "last_validated_at": "DATETIME",
            "last_error_code": "TEXT",
            "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
        }
        for column_name, definition in account_columns.items():
            if column_name not in user_info_columns:
                migration_definition = (
                    "DATETIME"
                    if column_name in {"created_at", "updated_at"}
                    else definition
                )
                cursor.execute(
                    f"ALTER TABLE user_info ADD COLUMN {column_name} {migration_definition}"
                )
        cursor.execute(
            """
            UPDATE user_info
            SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP),
                updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)
            WHERE created_at IS NULL OR updated_at IS NULL
            """
        )
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uk_user_info_platform_identity
            ON user_info(type, platform_user_id)
            WHERE platform_user_id IS NOT NULL
            """
        )
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS file_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            filesize REAL,
            upload_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            file_path TEXT
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL,
            value_type TEXT NOT NULL DEFAULT 'json',
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_providers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            provider_type TEXT NOT NULL CHECK(provider_type IN ('hermes', 'openai_compatible', 'codex_cli')),
            base_url TEXT,
            timeout_seconds INTEGER NOT NULL DEFAULT 300 CHECK(timeout_seconds BETWEEN 1 AND 3600),
            enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0, 1)),
            capabilities_json TEXT NOT NULL DEFAULT '{}',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_credentials (
            id TEXT PRIMARY KEY,
            provider_id TEXT NOT NULL,
            credential_type TEXT NOT NULL DEFAULT 'api_key',
            ciphertext TEXT NOT NULL,
            nonce TEXT NOT NULL,
            algorithm TEXT NOT NULL DEFAULT 'AES-256-GCM',
            key_reference TEXT NOT NULL,
            encryption_version INTEGER NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(provider_id, credential_type),
            FOREIGN KEY(provider_id) REFERENCES ai_providers(id) ON DELETE CASCADE
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_model_profiles (
            id TEXT PRIMARY KEY,
            provider_id TEXT NOT NULL,
            name TEXT NOT NULL,
            model_name TEXT NOT NULL,
            reasoning_effort TEXT NOT NULL DEFAULT '',
            service_tier TEXT NOT NULL DEFAULT '',
            temperature REAL,
            max_tokens INTEGER,
            extra_options_json TEXT NOT NULL DEFAULT '{}',
            enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0, 1)),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(provider_id) REFERENCES ai_providers(id) ON DELETE CASCADE
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_profiles (
            agent_key TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            execution_mode TEXT NOT NULL CHECK(execution_mode IN ('structured', 'tool_loop')),
            primary_model_profile_id TEXT,
            fallback_model_profile_id TEXT,
            timeout_seconds INTEGER NOT NULL DEFAULT 300 CHECK(timeout_seconds BETWEEN 1 AND 3600),
            max_steps INTEGER NOT NULL DEFAULT 8 CHECK(max_steps BETWEEN 1 AND 100),
            enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0, 1)),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(primary_model_profile_id) REFERENCES ai_model_profiles(id) ON DELETE SET NULL,
            FOREIGN KEY(fallback_model_profile_id) REFERENCES ai_model_profiles(id) ON DELETE SET NULL
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_runs (
            id TEXT PRIMARY KEY,
            agent_key TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled', 'interrupted')),
            input_json TEXT NOT NULL DEFAULT '{}',
            output_json TEXT,
            error_code TEXT,
            error_message TEXT,
            model_profile_id TEXT,
            started_at DATETIME,
            finished_at DATETIME,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(agent_key) REFERENCES agent_profiles(agent_key) ON DELETE RESTRICT,
            FOREIGN KEY(model_profile_id) REFERENCES ai_model_profiles(id) ON DELETE SET NULL
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_run_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(run_id, sequence),
            FOREIGN KEY(run_id) REFERENCES agent_runs(id) ON DELETE CASCADE
        )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ai_model_profiles_provider ON ai_model_profiles(provider_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status, created_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_agent_run_events_run ON agent_run_events(run_id, sequence)')
        conn.commit()
