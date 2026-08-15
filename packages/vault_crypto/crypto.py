from __future__ import annotations

import base64

from cryptography.fernet import Fernet, InvalidToken


class VaultDecryptionError(RuntimeError):
    pass


class VaultCipher:
    def __init__(self, key: bytes):
        if len(key) < 32:
            raise ValueError("Vault encryption key must be at least 32 bytes")
        self._fernet = Fernet(base64.urlsafe_b64encode(key[:32]))

    def encrypt_text(self, value: str) -> bytes:
        return self._fernet.encrypt(value.encode("utf-8"))

    def decrypt_text(self, ciphertext: bytes) -> str:
        try:
            return self._fernet.decrypt(ciphertext).decode("utf-8")
        except InvalidToken as exc:
            raise VaultDecryptionError("Vault ciphertext authentication failed") from exc
