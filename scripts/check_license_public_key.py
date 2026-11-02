"""Fail release builds when no trusted license public key is embedded."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_app.licensing.public_keys import TRUSTED_LICENSE_PUBLIC_KEYS


if not TRUSTED_LICENSE_PUBLIC_KEYS:
    raise SystemExit(
        "No desktop license public key is embedded. Add the production Ed25519 "
        "public key to backend_app/licensing/public_keys.py before packaging."
    )

for key_id, encoded in TRUSTED_LICENSE_PUBLIC_KEYS.items():
    if not key_id or not encoded:
        raise SystemExit("Desktop license public key configuration contains an empty value.")

print(f"License public key check passed ({len(TRUSTED_LICENSE_PUBLIC_KEYS)} key(s)).")
