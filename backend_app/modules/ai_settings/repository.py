import json
import uuid

from backend_app.common.database import connect


def _json_dump(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _json_load(value, default=None):
    try:
        return json.loads(value) if value not in (None, "") else default
    except (TypeError, json.JSONDecodeError):
        return default


def _row_dict(row):
    if row is None:
        return None
    data = dict(row)
    for key in ("enabled",):
        if key in data:
            data[key] = bool(data[key])
    for key in ("capabilities_json", "extra_options_json"):
        if key in data:
            data[key.removesuffix("_json")] = _json_load(data.pop(key), {})
    return data


def set_app_setting(db_path, key, value, value_type="json"):
    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO app_settings(key, value_json, value_type, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value_json=excluded.value_json,
                value_type=excluded.value_type,
                updated_at=CURRENT_TIMESTAMP
            """,
            (key, _json_dump(value), value_type),
        )


def get_app_setting(db_path, key, default=None):
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT value_json FROM app_settings WHERE key=?", (key,)
        ).fetchone()
    return _json_load(row["value_json"], default) if row else default


def list_app_settings(db_path):
    with connect(db_path) as connection:
        rows = connection.execute("SELECT key, value_json FROM app_settings").fetchall()
    return {row["key"]: _json_load(row["value_json"]) for row in rows}


def save_provider(db_path, provider):
    provider_id = provider.get("id") or uuid.uuid4().hex
    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO ai_providers(
                id, name, provider_type, base_url, timeout_seconds, enabled,
                capabilities_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                provider_type=excluded.provider_type,
                base_url=excluded.base_url,
                timeout_seconds=excluded.timeout_seconds,
                enabled=excluded.enabled,
                capabilities_json=excluded.capabilities_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                provider_id,
                provider["name"],
                provider["provider_type"],
                provider.get("base_url"),
                provider["timeout_seconds"],
                int(provider.get("enabled", True)),
                _json_dump(provider.get("capabilities") or {}),
            ),
        )
    return get_provider(db_path, provider_id)


def get_provider(db_path, provider_id):
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM ai_providers WHERE id=?", (provider_id,)
        ).fetchone()
    return _row_dict(row)


def list_providers(db_path):
    with connect(db_path) as connection:
        rows = connection.execute(
            "SELECT * FROM ai_providers ORDER BY created_at, id"
        ).fetchall()
    return [_row_dict(row) for row in rows]


def delete_provider(db_path, provider_id):
    with connect(db_path) as connection:
        cursor = connection.execute("DELETE FROM ai_providers WHERE id=?", (provider_id,))
    return cursor.rowcount > 0


def save_credential(db_path, provider_id, encrypted, credential_type="api_key"):
    credential_id = uuid.uuid4().hex
    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO ai_credentials(
                id, provider_id, credential_type, ciphertext, nonce, algorithm,
                key_reference, encryption_version, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(provider_id, credential_type) DO UPDATE SET
                ciphertext=excluded.ciphertext,
                nonce=excluded.nonce,
                algorithm=excluded.algorithm,
                key_reference=excluded.key_reference,
                encryption_version=excluded.encryption_version,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                credential_id,
                provider_id,
                credential_type,
                encrypted["ciphertext"],
                encrypted["nonce"],
                encrypted["algorithm"],
                encrypted["key_reference"],
                encrypted["encryption_version"],
            ),
        )


def get_credential(db_path, provider_id, credential_type="api_key"):
    with connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT * FROM ai_credentials
            WHERE provider_id=? AND credential_type=?
            """,
            (provider_id, credential_type),
        ).fetchone()
    return dict(row) if row else None


def delete_credential(db_path, provider_id, credential_type="api_key"):
    with connect(db_path) as connection:
        cursor = connection.execute(
            "DELETE FROM ai_credentials WHERE provider_id=? AND credential_type=?",
            (provider_id, credential_type),
        )
    return cursor.rowcount > 0


def save_model_profile(db_path, profile):
    profile_id = profile.get("id") or uuid.uuid4().hex
    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO ai_model_profiles(
                id, provider_id, name, model_name, reasoning_effort, service_tier,
                temperature, max_tokens, extra_options_json, enabled,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                provider_id=excluded.provider_id,
                name=excluded.name,
                model_name=excluded.model_name,
                reasoning_effort=excluded.reasoning_effort,
                service_tier=excluded.service_tier,
                temperature=excluded.temperature,
                max_tokens=excluded.max_tokens,
                extra_options_json=excluded.extra_options_json,
                enabled=excluded.enabled,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                profile_id,
                profile["provider_id"],
                profile["name"],
                profile["model_name"],
                profile.get("reasoning_effort") or "",
                profile.get("service_tier") or "",
                profile.get("temperature"),
                profile.get("max_tokens"),
                _json_dump(profile.get("extra_options") or {}),
                int(profile.get("enabled", True)),
            ),
        )
    return get_model_profile(db_path, profile_id)


def get_model_profile(db_path, profile_id):
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM ai_model_profiles WHERE id=?", (profile_id,)
        ).fetchone()
    return _row_dict(row)


def list_model_profiles(db_path, enabled_only=False):
    query = "SELECT * FROM ai_model_profiles"
    params = ()
    if enabled_only:
        query += " WHERE enabled=1"
    query += " ORDER BY created_at, id"
    with connect(db_path) as connection:
        rows = connection.execute(query, params).fetchall()
    return [_row_dict(row) for row in rows]


def delete_model_profile(db_path, profile_id):
    with connect(db_path) as connection:
        cursor = connection.execute(
            "DELETE FROM ai_model_profiles WHERE id=?", (profile_id,)
        )
    return cursor.rowcount > 0


def save_agent_profile(db_path, profile):
    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO agent_profiles(
                agent_key, name, execution_mode, primary_model_profile_id,
                fallback_model_profile_id, timeout_seconds, max_steps, enabled,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(agent_key) DO UPDATE SET
                name=excluded.name,
                execution_mode=excluded.execution_mode,
                primary_model_profile_id=excluded.primary_model_profile_id,
                fallback_model_profile_id=excluded.fallback_model_profile_id,
                timeout_seconds=excluded.timeout_seconds,
                max_steps=excluded.max_steps,
                enabled=excluded.enabled,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                profile["agent_key"],
                profile["name"],
                profile["execution_mode"],
                profile.get("primary_model_profile_id"),
                profile.get("fallback_model_profile_id"),
                profile.get("timeout_seconds", 300),
                profile.get("max_steps", 8),
                int(profile.get("enabled", True)),
            ),
        )
    return get_agent_profile(db_path, profile["agent_key"])


def get_agent_profile(db_path, agent_key):
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM agent_profiles WHERE agent_key=?", (agent_key,)
        ).fetchone()
    return _row_dict(row)


def list_agent_profiles(db_path):
    with connect(db_path) as connection:
        rows = connection.execute(
            "SELECT * FROM agent_profiles ORDER BY created_at, agent_key"
        ).fetchall()
    return [_row_dict(row) for row in rows]
