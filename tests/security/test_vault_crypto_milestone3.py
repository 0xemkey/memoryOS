from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from packages.pseudonymization import create_pseudonym
from packages.vault_crypto import EphemeralKeyProvider, KeyUnavailableError, StaticKeyProvider, VaultCipher, VaultStore
from packages.vault_crypto.crypto import VaultDecryptionError


KEY_A = b"a" * 32
KEY_B = b"b" * 32


def test_pseudonyms_are_stable_and_typed() -> None:
    first = create_pseudonym(KEY_A, "email", "Mehmet@Example.com")
    second = create_pseudonym(KEY_A, "email", "mehmet@example.com")

    assert first == second
    assert first.startswith("<EMAIL_")
    assert first.endswith(">")


def test_pseudonyms_differ_across_vault_keys() -> None:
    assert create_pseudonym(KEY_A, "person", "Mehmet") != create_pseudonym(KEY_B, "person", "Mehmet")


def test_collision_resistance_at_test_scale() -> None:
    tokens = {create_pseudonym(KEY_A, "person", f"person-{index}") for index in range(1000)}

    assert len(tokens) == 1000


def test_vault_cipher_encrypts_and_rejects_corruption() -> None:
    cipher = VaultCipher(KEY_A)
    encrypted = cipher.encrypt_text("secret original")

    assert b"secret original" not in encrypted
    assert cipher.decrypt_text(encrypted) == "secret original"
    with pytest.raises(VaultDecryptionError):
        cipher.decrypt_text(encrypted[:-3] + b"abc")


def test_ephemeral_key_mode_is_disabled_by_default() -> None:
    with pytest.raises(KeyUnavailableError):
        EphemeralKeyProvider()


def test_vault_store_persists_no_plaintext(tmp_path: Path) -> None:
    store = VaultStore(tmp_path / "vault.sqlite3", StaticKeyProvider(KEY_A))
    token = store.upsert_entity("person", "Mehmet")

    assert store.resolve_token(token) == "Mehmet"
    assert b"Mehmet" not in store.raw_database_bytes()


def test_vault_store_is_stable_and_does_not_duplicate(tmp_path: Path) -> None:
    store = VaultStore(tmp_path / "vault.sqlite3", StaticKeyProvider(KEY_A))
    first = store.upsert_entity("organization", "Roketsan")
    second = store.upsert_entity("organization", "ROKETSAN")

    with sqlite3.connect(tmp_path / "vault.sqlite3") as conn:
        count = conn.execute("SELECT COUNT(*) FROM vault_entities").fetchone()[0]

    assert first == second
    assert count == 1


def test_wrong_key_cannot_decrypt(tmp_path: Path) -> None:
    db_path = tmp_path / "vault.sqlite3"
    token = VaultStore(db_path, StaticKeyProvider(KEY_A)).upsert_entity("project", "Falcon")

    with pytest.raises(VaultDecryptionError):
        VaultStore(db_path, StaticKeyProvider(KEY_B)).resolve_token(token)
