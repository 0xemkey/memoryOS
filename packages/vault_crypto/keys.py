from __future__ import annotations

import base64
import os
from abc import ABC, abstractmethod

import keyring


class KeyUnavailableError(RuntimeError):
    pass


class KeyProvider(ABC):
    @abstractmethod
    def get_key(self) -> bytes:
        raise NotImplementedError

    @property
    def key_version(self) -> str:
        return "v1"


class KeyringKeyProvider(KeyProvider):
    def __init__(self, service_name: str = "memoryos-private-brain", username: str = "default-vault"):
        self.service_name = service_name
        self.username = username

    def get_key(self) -> bytes:
        stored = keyring.get_password(self.service_name, self.username)
        if stored is None:
            key = os.urandom(32)
            keyring.set_password(self.service_name, self.username, base64.urlsafe_b64encode(key).decode("ascii"))
            return key
        try:
            return base64.urlsafe_b64decode(stored.encode("ascii"))
        except Exception as exc:
            raise KeyUnavailableError("Vault key in OS keychain is unreadable") from exc


class StaticKeyProvider(KeyProvider):
    def __init__(self, key: bytes, key_version: str = "test-v1"):
        if len(key) < 32:
            raise ValueError("test key must be at least 32 bytes")
        self._key = key[:32]
        self._key_version = key_version

    def get_key(self) -> bytes:
        return self._key

    @property
    def key_version(self) -> str:
        return self._key_version


class EphemeralKeyProvider(KeyProvider):
    def __init__(self, *, allow_unsafe_development_mode: bool = False):
        if not allow_unsafe_development_mode:
            raise KeyUnavailableError("Ephemeral vault keys are unsafe and disabled by default")
        self._key = os.urandom(32)

    def get_key(self) -> bytes:
        return self._key

    @property
    def key_version(self) -> str:
        return "unsafe-ephemeral"
