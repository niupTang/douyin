import base64
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


ALGORITHM = "AES-256-GCM"
ENCRYPTION_VERSION = 1


class SecretStoreError(RuntimeError):
    """Raised when the operating-system secret store cannot be used safely."""


class KeyringMasterKeyProvider:
    def __init__(self, service_name="Sunbird OS AI"):
        self.service_name = service_name

    def get_or_create(self, key_reference):
        try:
            import keyring

            encoded = keyring.get_password(self.service_name, key_reference)
            if encoded:
                key = base64.urlsafe_b64decode(encoded.encode("ascii"))
                if len(key) != 32:
                    raise SecretStoreError("系统安全存储中的 AI 主密钥格式无效")
                return key
            key = os.urandom(32)
            keyring.set_password(
                self.service_name,
                key_reference,
                base64.urlsafe_b64encode(key).decode("ascii"),
            )
            return key
        except SecretStoreError:
            raise
        except Exception as exc:
            raise SecretStoreError("系统安全存储不可用，无法安全保存 AI 密钥") from exc


class MemoryMasterKeyProvider:
    """Test-only master-key provider that never touches the operating system."""

    def __init__(self):
        self.keys = {}

    def get_or_create(self, key_reference):
        return self.keys.setdefault(key_reference, os.urandom(32))


@dataclass(frozen=True)
class EncryptedSecret:
    ciphertext: str
    nonce: str
    algorithm: str
    key_reference: str
    encryption_version: int

    def as_dict(self):
        return {
            "ciphertext": self.ciphertext,
            "nonce": self.nonce,
            "algorithm": self.algorithm,
            "key_reference": self.key_reference,
            "encryption_version": self.encryption_version,
        }


class SecretStore:
    def __init__(self, master_key_provider=None):
        self.master_key_provider = master_key_provider or KeyringMasterKeyProvider()

    @staticmethod
    def _aad(key_reference, encryption_version):
        return f"sunbird-ai:{key_reference}:v{encryption_version}".encode("utf-8")

    def encrypt(self, plaintext, key_reference):
        plaintext = str(plaintext or "")
        if not plaintext:
            raise ValueError("密钥不能为空")
        key = self.master_key_provider.get_or_create(key_reference)
        nonce = os.urandom(12)
        ciphertext = AESGCM(key).encrypt(
            nonce,
            plaintext.encode("utf-8"),
            self._aad(key_reference, ENCRYPTION_VERSION),
        )
        return EncryptedSecret(
            ciphertext=base64.urlsafe_b64encode(ciphertext).decode("ascii"),
            nonce=base64.urlsafe_b64encode(nonce).decode("ascii"),
            algorithm=ALGORITHM,
            key_reference=key_reference,
            encryption_version=ENCRYPTION_VERSION,
        )

    def decrypt(self, encrypted):
        if encrypted.get("algorithm") != ALGORITHM:
            raise SecretStoreError("不支持的 AI 密钥加密算法")
        version = int(encrypted.get("encryption_version") or 0)
        if version != ENCRYPTION_VERSION:
            raise SecretStoreError("不支持的 AI 密钥加密版本")
        key_reference = str(encrypted.get("key_reference") or "")
        if not key_reference:
            raise SecretStoreError("AI 密钥缺少系统安全存储引用")
        try:
            key = self.master_key_provider.get_or_create(key_reference)
            nonce = base64.urlsafe_b64decode(str(encrypted["nonce"]).encode("ascii"))
            ciphertext = base64.urlsafe_b64decode(str(encrypted["ciphertext"]).encode("ascii"))
            plaintext = AESGCM(key).decrypt(
                nonce,
                ciphertext,
                self._aad(key_reference, version),
            )
            return plaintext.decode("utf-8")
        except SecretStoreError:
            raise
        except Exception as exc:
            raise SecretStoreError("AI 密钥无法解密，请重新配置") from exc
