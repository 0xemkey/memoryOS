from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from packages.chat_normalization import ChatImportPipeline
from packages.common_models import NormalizedMessage, NormalizedSource
from packages.privacy_detection import PrivacyScanner
from packages.sanitized_storage import SanitizationService, SanitizedImportPackage, SanitizedStore
from packages.vault_crypto import StaticKeyProvider, VaultStore


ROOT = Path(__file__).parents[1]
KEY = b"c" * 32


def source_from_fixture() -> NormalizedSource:
    result = ChatImportPipeline().import_path(ROOT / "fixtures" / "private_brain_generic.json")
    return result.sources[0]


def sanitizer(tmp_path: Path) -> SanitizationService:
    return SanitizationService(
        scanner=PrivacyScanner(),
        vault_store=VaultStore(tmp_path / "vault.sqlite3", StaticKeyProvider(KEY)),
    )


def test_pseudonym_replacement_and_repeated_entity_consistency(tmp_path: Path) -> None:
    source = source_from_fixture()
    source.messages[0] = source.messages[0].model_copy(
        update={"content": "Email mehmet@example.com and mehmet@example.com about Proje Falcon."}
    )
    package = sanitizer(tmp_path).sanitize_source(source)
    text = package.sanitized_messages[0].sanitized_content

    assert "mehmet@example.com" not in text
    assert text.count("<EMAIL_") == 2
    assert len(set(package.sanitized_messages[0].token_references)) == 2
    assert any(entity.entity_type == "email" for entity in package.sanitized_entities)


def test_credential_is_removed_not_pseudonymized(tmp_path: Path) -> None:
    source = source_from_fixture()
    source.messages[0] = source.messages[0].model_copy(update={"content": "password: hunter22"})
    package = sanitizer(tmp_path).sanitize_source(source)

    assert "hunter22" not in package.sanitized_messages[0].sanitized_content
    assert "[REMOVED_PASSWORD]" in package.sanitized_messages[0].sanitized_content
    assert package.sanitized_messages[0].token_references == []


def test_quarantine_excludes_sensitive_message(tmp_path: Path) -> None:
    source = source_from_fixture()
    source.messages[0] = source.messages[0].model_copy(update={"content": "card 4111 1111 1111 1111"})
    package = sanitizer(tmp_path).sanitize_source(source)

    assert len(package.sanitized_messages) == 1
    assert package.privacy_statistics["quarantined_messages"] == 1


def test_sanitized_package_hash_detects_tampering(tmp_path: Path) -> None:
    package = sanitizer(tmp_path).sanitize_source(source_from_fixture())
    payload = package.model_dump()
    payload["sanitized_messages"][0]["sanitized_content"] = "tampered"

    with pytest.raises(ValidationError):
        SanitizedImportPackage(**payload)


def test_sanitized_database_contains_no_raw_pseudonymized_value(tmp_path: Path) -> None:
    source = source_from_fixture()
    source.messages[0] = source.messages[0].model_copy(update={"content": "Contact mehmet@example.com"})
    package = sanitizer(tmp_path).sanitize_source(source)
    store = SanitizedStore(tmp_path / "sanitized.sqlite3")
    store.save_package(package)

    assert b"mehmet@example.com" not in store.raw_database_bytes()
    assert b"<EMAIL_" in store.raw_database_bytes()


def test_second_pass_blocks_remaining_high_risk(monkeypatch, tmp_path: Path) -> None:
    source = source_from_fixture()
    original_scan = PrivacyScanner.scan_message
    calls = {"count": 0}

    def injected_second_pass(self, message: NormalizedMessage):
        calls["count"] += 1
        if calls["count"] > 1:
            return original_scan(self, message.model_copy(update={"content": "password: stillbad"}))
        return []

    monkeypatch.setattr(PrivacyScanner, "scan_message", injected_second_pass)
    package = sanitizer(tmp_path).sanitize_source(source)

    assert package.sanitized_messages == []
    assert package.privacy_statistics["blocked_second_pass"] >= 1
