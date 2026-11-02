import base64
import json
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend_app.licensing.service import LicenseValidationError, verify_license


def signed_license(monkeypatch, *, device_id="dev_test_1234567890", expires_delta=30, offline_delta=7):
    private_key = Ed25519PrivateKey.generate()
    public_raw = private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    monkeypatch.setenv(
        "SAU_LICENSE_PUBLIC_KEYS_JSON",
        json.dumps({"test-key": base64.b64encode(public_raw).decode("ascii")}),
    )
    now = datetime.now(timezone.utc)
    payload = {
        "licenseId": "lic_test",
        "credentialId": 1,
        "deviceId": device_id,
        "plan": "pro",
        "issuedAt": now.isoformat(),
        "expiresAt": (now + timedelta(days=expires_delta)).isoformat(),
        "refreshAfter": (now + timedelta(days=1)).isoformat(),
        "offlineGraceUntil": (now + timedelta(days=offline_delta)).isoformat(),
        "entitlements": {"aiAnalysis": True},
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = base64.urlsafe_b64encode(private_key.sign(canonical)).rstrip(b"=").decode("ascii")
    return {"version": 1, "kid": "test-key", "algorithm": "Ed25519", "payload": payload, "signature": signature}


def test_verifies_valid_signed_license(monkeypatch):
    envelope = signed_license(monkeypatch)
    context = verify_license(envelope, "dev_test_1234567890")
    assert context.entitlement("aiAnalysis") is True
    assert context.status()["valid"] is True


def test_rejects_modified_payload(monkeypatch):
    envelope = signed_license(monkeypatch)
    envelope["payload"]["plan"] = "enterprise"
    with pytest.raises(LicenseValidationError) as error:
        verify_license(envelope, "dev_test_1234567890")
    assert error.value.code == "LICENSE_SIGNATURE_INVALID"


def test_rejects_license_from_another_device(monkeypatch):
    envelope = signed_license(monkeypatch)
    with pytest.raises(LicenseValidationError) as error:
        verify_license(envelope, "dev_other_1234567890")
    assert error.value.code == "LICENSE_DEVICE_MISMATCH"


def test_rejects_expired_offline_grace(monkeypatch):
    envelope = signed_license(monkeypatch, offline_delta=-1)
    with pytest.raises(LicenseValidationError) as error:
        verify_license(envelope, "dev_test_1234567890")
    assert error.value.code == "OFFLINE_GRACE_EXPIRED"
