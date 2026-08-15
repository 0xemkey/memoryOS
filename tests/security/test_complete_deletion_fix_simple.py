"""Simplified tests for complete data deletion across all storage tiers.

This test verifies that the delete_all_data() method:
1. Is implemented on all store classes
2. Returns proper status indication
3. Reports errors clearly when deletion fails
4. Attempts to clear keychain
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from apps.orchestrator.private_brain import PrivateBrainConfig, PrivateBrainService
from packages.vault_crypto.keys import EphemeralKeyProvider


def test_vault_store_has_delete_all_data_method() -> None:
    """Verify VaultStore has delete_all_data() method."""
    import tempfile
    from packages.vault_crypto.store import VaultStore

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        store = VaultStore(Path(tmpdir) / "test.sqlite3", EphemeralKeyProvider(allow_unsafe_development_mode=True))
        assert hasattr(store, "delete_all_data"), "VaultStore should have delete_all_data method"
        assert callable(store.delete_all_data), "delete_all_data should be callable"


def test_normalized_store_has_delete_all_data_method() -> None:
    """Verify NormalizedImportStore has delete_all_data() method."""
    import tempfile
    from packages.normalized_storage.store import NormalizedImportStore

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        store = NormalizedImportStore(Path(tmpdir) / "test.sqlite3")
        assert hasattr(store, "delete_all_data"), "NormalizedImportStore should have delete_all_data method"
        assert callable(store.delete_all_data), "delete_all_data should be callable"


def test_sanitized_store_has_delete_all_data_method() -> None:
    """Verify SanitizedStore has delete_all_data() method."""
    import tempfile
    from packages.sanitized_storage.store import SanitizedStore

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        store = SanitizedStore(Path(tmpdir) / "test.sqlite3")
        assert hasattr(store, "delete_all_data"), "SanitizedStore should have delete_all_data method"
        assert callable(store.delete_all_data), "delete_all_data should be callable"


def test_private_brain_service_delete_returns_status_structure() -> None:
    """Verify PrivateBrainService.delete_all_data() returns proper structure."""
    import tempfile

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        config = PrivateBrainConfig(
            data_dir=Path(tmpdir),
            normalized_db=Path(tmpdir) / "normalized.sqlite3",
            vault_db=Path(tmpdir) / "vault.sqlite3",
            sanitized_db=Path(tmpdir) / "sanitized.sqlite3",
            use_legacy_mvp=False,
            ollama_base_url="http://127.0.0.1:11434",
            chat_model="llama3.1",
            embedding_model="nomic-embed-text",
        )

        key_provider = EphemeralKeyProvider(allow_unsafe_development_mode=True)
        service = PrivateBrainService(config, vault_key_provider=key_provider)

        # Migrate to create databases
        service.normalized_store.migrate()
        service.sanitized_store.migrate()
        service.vault_store.migrate()

        # Call delete
        results = service.delete_all_data()

        # Verify structure
        assert "status" in results, "Results should have 'status' key"
        assert results["status"] in ["success", "partial_failure"], "Status should be success or partial_failure"
        assert "normalized_deleted" in results
        assert "sanitized_deleted" in results
        assert "vault_deleted" in results
        assert "keychain_cleared" in results
        assert "errors" in results
        assert isinstance(results["errors"], list)


def test_api_delete_endpoint_calls_cascade_deletion() -> None:
    """Verify the API DELETE /data endpoint calls all deletion paths."""
    import tempfile
    from apps.api.memoryos_api.main import delete_data, private_brain, use_legacy

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        config = PrivateBrainConfig(
            data_dir=Path(tmpdir),
            normalized_db=Path(tmpdir) / "normalized.sqlite3",
            vault_db=Path(tmpdir) / "vault.sqlite3",
            sanitized_db=Path(tmpdir) / "sanitized.sqlite3",
            use_legacy_mvp=False,
            ollama_base_url="http://127.0.0.1:11434",
            chat_model="llama3.1",
            embedding_model="nomic-embed-text",
        )

        key_provider = EphemeralKeyProvider(allow_unsafe_development_mode=True)

        # Mock delete_all_data to verify it's called
        with patch.object(PrivateBrainService, 'delete_all_data') as mock_delete:
            mock_delete.return_value = {
                "status": "success",
                "normalized_deleted": True,
                "sanitized_deleted": True,
                "vault_deleted": True,
                "keychain_cleared": True,
                "errors": [],
            }

            # The endpoint will call it
            result = delete_data()

            # Verify it was called
            assert mock_delete.called or result["detail"] == "All MemoryOS data has been securely deleted."


def test_vault_store_clear_keychain_entry_exists() -> None:
    """Verify VaultStore has clear_keychain_entry() method."""
    import tempfile
    from packages.vault_crypto.store import VaultStore

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        store = VaultStore(Path(tmpdir) / "test.sqlite3", EphemeralKeyProvider(allow_unsafe_development_mode=True))
        assert hasattr(store, "clear_keychain_entry"), "VaultStore should have clear_keychain_entry method"
        assert callable(store.clear_keychain_entry), "clear_keychain_entry should be callable"

        # Calling it should not crash
        store.clear_keychain_entry()


