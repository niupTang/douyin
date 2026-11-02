import base64
import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import wraps

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from flask import jsonify

from .public_keys import TRUSTED_LICENSE_PUBLIC_KEYS


class LicenseValidationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _decode_b64url(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _public_keys() -> dict[str, str]:
    keys = dict(TRUSTED_LICENSE_PUBLIC_KEYS)
    configured = os.environ.get("SAU_LICENSE_PUBLIC_KEYS_JSON", "").strip()
    if configured:
        try:
            parsed = json.loads(configured)
            if isinstance(parsed, dict):
                keys.update({str(key): str(value) for key, value in parsed.items()})
        except ValueError as exc:
            raise LicenseValidationError("LICENSE_CONFIGURATION_INVALID", "许可证公钥配置无效") from exc
    return keys


def _parse_time(value: str | None, field: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError) as exc:
        raise LicenseValidationError("LICENSE_PAYLOAD_INVALID", f"许可证字段 {field} 无效") from exc


@dataclass(frozen=True)
class LicenseContext:
    envelope: dict
    payload: dict
    installed_at: datetime

    def entitlement(self, name: str) -> bool:
        return bool((self.payload.get("entitlements") or {}).get(name))

    def status(self, now: datetime | None = None) -> dict:
        current = now or datetime.now(timezone.utc)
        expires_at = _parse_time(self.payload.get("expiresAt"), "expiresAt")
        offline_until = _parse_time(self.payload.get("offlineGraceUntil"), "offlineGraceUntil")
        if expires_at and current >= expires_at:
            return {"valid": False, "reasonCode": "LICENSE_EXPIRED", "message": "商业授权已到期"}
        if not offline_until or current >= offline_until:
            return {"valid": False, "reasonCode": "OFFLINE_GRACE_EXPIRED", "message": "离线授权已超过 7 天，请联网验证"}
        return {"valid": True, "reasonCode": None, "message": "许可证有效"}


def verify_license(envelope: dict, expected_device_id: str) -> LicenseContext:
    if not isinstance(envelope, dict) or envelope.get("version") != 1:
        raise LicenseValidationError("LICENSE_FORMAT_INVALID", "许可证格式无效")
    if envelope.get("algorithm") != "Ed25519":
        raise LicenseValidationError("LICENSE_ALGORITHM_INVALID", "许可证签名算法不受支持")
    public_key_value = _public_keys().get(str(envelope.get("kid") or ""))
    if not public_key_value:
        raise LicenseValidationError("LICENSE_KEY_UNKNOWN", "许可证签名密钥不受信任")
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise LicenseValidationError("LICENSE_PAYLOAD_INVALID", "许可证载荷无效")
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    try:
        public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_value, validate=True))
        public_key.verify(_decode_b64url(str(envelope.get("signature") or "")), canonical)
    except (ValueError, TypeError, InvalidSignature) as exc:
        raise LicenseValidationError("LICENSE_SIGNATURE_INVALID", "许可证签名验证失败") from exc
    if payload.get("deviceId") != expected_device_id:
        raise LicenseValidationError("LICENSE_DEVICE_MISMATCH", "许可证不属于当前设备")
    context = LicenseContext(envelope, payload, datetime.now(timezone.utc))
    status = context.status()
    if not status["valid"]:
        raise LicenseValidationError(status["reasonCode"], status["message"])
    return context


class LicenseRegistry:
    def __init__(self):
        self._lock = threading.RLock()
        self._context: LicenseContext | None = None

    def install(self, envelope: dict, device_id: str) -> LicenseContext:
        context = verify_license(envelope, device_id)
        with self._lock:
            self._context = context
        return context

    def clear(self) -> None:
        with self._lock:
            self._context = None

    def context(self) -> LicenseContext | None:
        with self._lock:
            return self._context

    def public_status(self) -> dict:
        context = self.context()
        if not context:
            return {"activated": False, "valid": False, "reasonCode": "LICENSE_REQUIRED", "message": "软件尚未激活"}
        return {
            "activated": True,
            **context.status(),
            "plan": context.payload.get("plan"),
            "expiresAt": context.payload.get("expiresAt"),
            "offlineGraceUntil": context.payload.get("offlineGraceUntil"),
            "entitlements": context.payload.get("entitlements") or {},
        }

    def require(self, entitlement: str) -> tuple[bool, dict]:
        context = self.context()
        if not context:
            return False, {"reasonCode": "LICENSE_REQUIRED", "message": "请先使用卡密激活软件"}
        status = context.status()
        if not status["valid"]:
            return False, status
        if not context.entitlement(entitlement):
            return False, {"reasonCode": "ENTITLEMENT_DENIED", "message": "当前套餐不包含此功能"}
        return True, status


license_registry = LicenseRegistry()


def require_entitlement(name: str):
    def decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            allowed, status = license_registry.require(name)
            if not allowed:
                return jsonify({"code": 403, "message": status["message"], "data": {"reasonCode": status["reasonCode"]}}), 403
            return function(*args, **kwargs)
        return wrapper
    return decorator
