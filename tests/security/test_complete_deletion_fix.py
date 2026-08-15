"""Test that DELETE /data cascades across all storage tiers and keychain.

This test verifies the fix for incomplete deletion where only legacy MVP data
was deleted but vault.sqlite3 and sanitized.sqlite3 remained on disk.

Deletes:
1. Normalized DB (raw imports)
2. Sanitized DB (pseudonymized content)
3. Vault DB (encrypted mappings)
4. Vault keychain entry (encryption key)
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from apps.orchestrator.private_brain import PrivateBrainConfig, PrivateBrainService
from packages.vault_crypto.keys import EphemeralKeyProvider


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for all database files."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def private_brain_with_data(temp_data_dir: Path) -> PrivateBrainService:
    """Create a PrivateBrainService with populated databases."""
    config = PrivateBrainConfig(
        data_dir=temp_data_dir,
        normalized_db=temp_data_dir / "normalized.sqlite3",
        vault_db=temp_data_dir / "vault.sqlite3",
        sanitized_db=temp_data_dir / "sanitized.sqlite3",
        use_legacy_mvp=False,
        ollama_base_url="http://127.0.0.1:11434",
        chat_model="llama3.1",
        embedding_model="nomic-embed-text",
    )

    key_provider = EphemeralKeyProvider(allow_unsafe_development_mode=True)
    service = PrivateBrainService(config, vault_key_provider=key_provider)

    # Populate each database with sample data
    service.normalized_store.migrate()
    service.sanitized_store.migrate()
    service.vault_store.migrate()

    # Add sample data to normalized DB
    conn = sqlite3.connect(config.normalized_db)
    conn.execute(
        """
        INSERT INTO normalized_sources (source_fingerprint, source_path, provider, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("abc123", "/path/to/export.json", "claude", "{}", "2026-01-01T00:00:00+00:00"),
    )
    conn.execute(
        """
        INSERT INTO normalized_conversations (conversation_id, source_fingerprint, provider, remote_id, title, created_at, updated_at, source_file, metadata_json, content_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "conv_123",
            "abc123",
            "claude",
            None,
            "Test Conversation",
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            "/path",
            "{}",
            "hash123",
        ),
    )
    conn.commit()
    conn.close()

    # Add sample data to vault DB
    conn = sqlite3.connect(config.vault_db)
    conn.execute(
        """
        INSERT INTO vault_entities VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("<PERSON_ABC123>", "person", b"encrypted_data", "fingerprint", "v1", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
    )
    conn.commit()
    conn.close()

    # Add sample data to sanitized DB
    conn = sqlite3.connect(config.sanitized_db)
    conn.execute(
        """
        INSERT INTO sanitized_conversations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "san_conv_123",
            "claude",
            None,
            "Sanitized Conversation",
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            None,
            "{}",
            "hash456",
        ),
    )
    conn.commit()
    conn.close()

    return service


def test_delete_all_data_removes_all_four_databases() -> None:
    """Verify that delete_all_data() removes normalized, sanitized, vault, and clears keychain.

    NOTE: This test creates its own fresh service to avoid file locking issues
    from the fixture's active store references.
    """
    import tempfile

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        # Create fresh config and service
        tmp_path = Path(tmpdir)
        config = PrivateBrainConfig(
            data_dir=tmp_path,
            normalized_db=tmp_path / "normalized.sqlite3",
            vault_db=tmp_path / "vault.sqlite3",
            sanitized_db=tmp_path / "sanitized.sqlite3",
            use_legacy_mvp=False,
            ollama_base_url="http://127.0.0.1:11434",
            chat_model="llama3.1",
            embedding_model="nomic-embed-text",
        )

        key_provider = EphemeralKeyProvider(allow_unsafe_development_mode=True)
        service = PrivateBrainService(config, vault_key_provider=key_provider)

        # Populate databases
        service.normalized_store.migrate()
        service.sanitized_store.migrate()
        service.vault_store.migrate()

        normalized_db = config.normalized_db
        sanitized_db = config.sanitized_db
        vault_db = config.vault_db

        # Verify databases exist before deletion
        assert normalized_db.exists(), "Normalized DB should exist before deletion"
        assert sanitized_db.exists(), "Sanitized DB should exist before deletion"
        assert vault_db.exists(), "Vault DB should exist before deletion"

        # CRITICAL: Close engine BEFORE deletion
        service.normalized_store.engine.dispose()

        # Perform deletion
        results = service.delete_all_data()

        # Verify deletion results show SUCCESS
        assert results["status"] == "success", \
            f"Deletion must succeed with 'success' status. Got: {results['status']}\n  Errors: {results.get('errors')}"
        assert results["normalized_deleted"] is True, "Normalized DB deletion must be flagged"
        assert results["sanitized_deleted"] is True, "Sanitized DB deletion must be flagged"
        assert results["vault_deleted"] is True, "Vault DB deletion must be flagged"
        assert results["keychain_cleared"] is True, "Keychain clearing must be flagged"
        assert not results.get("errors"), \
            f"Success status means zero errors, but got: {results.get('errors')}"

        # Verify databases are actually gone
        assert not normalized_db.exists(), \
            f"PRIVACY VIOLATION: Normalized DB still exists after deletion"
        assert not sanitized_db.exists(), \
            f"PRIVACY VIOLATION: Sanitized DB still exists after deletion"
        assert not vault_db.exists(), \
            f"PRIVACY VIOLATION: Vault DB still exists after deletion"


def test_delete_recreates_empty_schema_after_deletion(private_brain_with_data: PrivateBrainService) -> None:
    """Verify that after deletion, running migrations recreates empty schema."""
    service = private_brain_with_data
    normalized_db = service.config.normalized_db
    sanitized_db = service.config.sanitized_db
    vault_db = service.config.vault_db

    # Delete all data
    results = service.delete_all_data()
    assert results["status"] == "success"

    # Re-migrate to recreate schema
    service.normalized_store.migrate()
    service.sanitized_store.migrate()
    service.vault_store.migrate()

    # Verify databases are recreated but empty
    with sqlite3.connect(normalized_db) as conn:
        rows = conn.execute("SELECT COUNT(*) FROM normalized_conversations").fetchone()
        assert rows[0] == 0, "Normalized DB should be empty after deletion and recreation"

    with sqlite3.connect(sanitized_db) as conn:
        rows = conn.execute("SELECT COUNT(*) FROM sanitized_conversations").fetchone()
        assert rows[0] == 0, "Sanitized DB should be empty after deletion and recreation"

    with sqlite3.connect(vault_db) as conn:
        rows = conn.execute("SELECT COUNT(*) FROM vault_entities").fetchone()
        assert rows[0] == 0, "Vault DB should be empty after deletion and recreation"


def test_delete_is_idempotent(private_brain_with_data: PrivateBrainService) -> None:
    """Verify that delete_all_data() can be called multiple times safely."""
    service = private_brain_with_data

    # First deletion
    results1 = service.delete_all_data()
    assert results1["status"] == "success"

    # Second deletion (databases don't exist)
    results2 = service.delete_all_data()
    assert results2["status"] == "success"

    # Should not error on re-deletion
    assert not results2.get("errors"), "Re-deletion should not produce errors"


def test_delete_handles_locked_file_gracefully(private_brain_with_data: PrivateBrainService) -> None:
    """Verify that partial deletion failure is reported clearly, not silently hidden."""
    service = private_brain_with_data

    # Simulate one store failing to delete (but others succeed)
    # This tests that partial failures are caught and reported
    with patch.object(service.normalized_store, 'delete_all_data', side_effect=OSError("File is locked")):
        results = service.delete_all_data()

        # CRITICAL: Should report "partial_failure", not "success"
        assert results["status"] == "partial_failure", \
            f"Must report partial_failure when ANY deletion fails; got status={results['status']}"

        # Error must be in the list
        assert len(results.get("errors", [])) > 0, \
            "Errors list must not be empty when status is partial_failure"

        # The error message should clearly indicate which component failed
        error_text = " ".join(results.get("errors", []))
        assert "normalized" in error_text.lower(), \
            f"Error message must mention which store failed, got: {error_text}"

        # Deletion flags should reflect actual status
        assert results["normalized_deleted"] is False, \
            "normalized_deleted must be False when deletion failed"


def test_delete_does_not_leave_data_accessible(private_brain_with_data: PrivateBrainService) -> None:
    """Verify that deleted data is not just moved but actually inaccessible."""
    service = private_brain_with_data
    distinctive_value = "super_secret_conversation_content"

    # Add distinctive data to each DB
    # Note: Explicitly close connection (sqlite3 context manager only handles transactions, not close)
    conn = sqlite3.connect(service.config.sanitized_db)
    conn.execute(
        """
        INSERT INTO sanitized_messages VALUES
        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "msg_123",
            "san_conv_123",
            "user",
            distinctive_value,
            "sanitized",
            "[]",
            "[]",
            "[]",
            None,
            "2026-01-01T00:00:00+00:00",
            "{}",
            "hash_xyz",
        ),
    )
    conn.commit()
    conn.close()  # CRITICAL: Context manager does NOT call close()

    # Delete all data
    results = service.delete_all_data()
    assert results["status"] == "success"

    # Ensure distinctive value is not found in temp dir after deletion
    import os
    for root, dirs, files in os.walk(service.config.data_dir):
        for file in files:
            if file.endswith(".sqlite3"):
                filepath = Path(root) / file
                if filepath.exists():
                    content = filepath.read_bytes()
                    assert distinctive_value.encode() not in content, \
                        f"Sensitive data found in {filepath} after deletion"


def test_vault_keychain_clearance_called(private_brain_with_data: PrivateBrainService) -> None:
    """Verify that clear_keychain_entry() is called during deletion."""
    service = private_brain_with_data

    with patch.object(service.vault_store, 'clear_keychain_entry') as mock_clear:
        results = service.delete_all_data()
        mock_clear.assert_called_once()
        assert results["keychain_cleared"], "Keychain should be reported as cleared"


def test_deletion_result_structure(private_brain_with_data: PrivateBrainService) -> None:
    """Verify the deletion result dictionary has all required fields."""
    service = private_brain_with_data

    results = service.delete_all_data()

    # Must have status
    assert "status" in results
    assert results["status"] in ["success", "partial_failure"]

    # Must have flags for each store
    assert "normalized_deleted" in results
    assert "sanitized_deleted" in results
    assert "vault_deleted" in results
    assert "keychain_cleared" in results

    # Must have errors list
    assert "errors" in results
    assert isinstance(results["errors"], list)


def test_app_works_after_deletion_without_restart(private_brain_with_data: PrivateBrainService) -> None:
    """Verify that after deletion + schema recreation, the app still works in the same process.

    This tests the endpoint behavior: DELETE /data calls delete_all_data(), then
    calls migrate() to recreate empty schema. Confirms the app doesn't crash with
    'no such table' errors on the next operation.
    """
    service = private_brain_with_data

    # Delete all data
    results = service.delete_all_data()
    assert results["status"] == "success"

    # Recreate empty schema (as the DELETE /data endpoint does)
    if results.get("normalized_deleted"):
        service.normalized_store.migrate()
    if results.get("sanitized_deleted"):
        service.sanitized_store.migrate()
    if results.get("vault_deleted"):
        service.vault_store.migrate()

    # Verify the schema was recreated by doing a trivial operation
    # (just verify tables exist by calling list_conversations - no crash)
    try:
        conversations = service.list_conversations()
        assert conversations == [], "Conversations should be empty after deletion"
    except Exception as e:
        pytest.fail(f"App crashed after deletion with: {e}. "
                   "This suggests migrate() wasn't called after delete_all_data().")

    # Verify vault can still do crypto operations (key setup, etc.)
    try:
        token = service.vault_store.upsert_entity("person", "John Doe")
        assert token is not None, "Vault should work after deletion"
    except Exception as e:
        pytest.fail(f"Vault failed after deletion with: {e}")
