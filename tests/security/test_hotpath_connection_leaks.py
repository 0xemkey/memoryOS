"""Test that hot-path connection leaks are fixed - handles released properly.

These tests verify that sqlite3 connections are explicitly closed (not relying on
context manager which only manages transactions). The proof: immediately after
calling the function 20-30 times, we can delete/rename the database file on Windows,
which only succeeds if all file handles are actually released.

This is a regression test for the fix that replaced:
  with sqlite3.connect(db) as conn:  # WRONG - doesn't call close()
      ...

with:
  conn = sqlite3.connect(db)
  try:
      ...
  finally:
      conn.close()  # CORRECT - explicitly closes OS file handle
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from apps.orchestrator.private_brain import PrivateBrainConfig, PrivateBrainService
from packages.sanitized_storage.store import SanitizedStore
from packages.vault_crypto.keys import EphemeralKeyProvider


def test_search_chunks_fts_releases_handles() -> None:
    """Verify search_chunks_fts() actually closes connection handles.

    Proof: call 25 times in a loop, then immediately rename the DB file.
    If handles leaked, rename would fail with PermissionError on Windows.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_sanitized.sqlite3"
        store = SanitizedStore(db_path)

        # Create schema and add test data
        store.migrate()
        store.save_chunks(
            [
                {
                    "chunk_id": "chunk_1",
                    "conversation_id": "conv_1",
                    "message_ids": [1, 2],
                    "provider": "claude",
                    "sanitized_title": "Test",
                    "sanitized_content": "test content here",
                    "privacy_level": "sanitized",
                    "token_references": [],
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "content_hash": "abc123",
                }
            ]
        )

        # Call search_chunks_fts 25 times - each one should close its handle
        for i in range(25):
            results = store.search_chunks_fts("test", {}, limit=10)
            assert isinstance(results, list), f"Search {i} should return list"

        # Force garbage collection to release any lingering references
        import gc
        import time
        gc.collect()
        time.sleep(0.05)

        # If handles leaked, this rename will fail with PermissionError on Windows
        # (file locked by unclosed connections). If fixed, rename succeeds.
        try:
            new_path = Path(tmpdir) / "test_sanitized_renamed.sqlite3"
            db_path.rename(new_path)
            # If we get here, the handle was actually released
            assert new_path.exists(), "Renamed file should exist"
        except PermissionError as e:
            pytest.fail(
                f"search_chunks_fts leaked file handles: {e}\n"
                "Context manager did not close() connections - fix incomplete."
            )


def test_log_retrieval_event_releases_handles() -> None:
    """Verify log_retrieval_event() actually closes connection handles.

    Proof: call 25 times in a loop, then immediately rename the DB file.
    If handles leaked, rename would fail with PermissionError on Windows.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_sanitized.sqlite3"
        store = SanitizedStore(db_path)

        # Create schema
        store.migrate()

        # Call log_retrieval_event 25 times - each one should close its handle
        for i in range(25):
            store.log_retrieval_event(
                query=f"test query {i}",
                result_ids=[f"chunk_{j}" for j in range(5)],
                filters={"provider": "claude"},
            )

        # Force garbage collection to release any lingering references
        import gc
        import time
        gc.collect()
        time.sleep(0.05)

        # If handles leaked, this rename will fail with PermissionError on Windows
        try:
            new_path = Path(tmpdir) / "test_sanitized_renamed.sqlite3"
            db_path.rename(new_path)
            # If we get here, the handle was actually released
            assert new_path.exists(), "Renamed file should exist"
        except PermissionError as e:
            pytest.fail(
                f"log_retrieval_event leaked file handles: {e}\n"
                "Context manager did not close() connections - fix incomplete."
            )


def test_get_chunks_by_ids_releases_handles() -> None:
    """Verify _chunks_by_ids() actually closes connection handles.

    Proof: call 25 times in a loop, then immediately rename the DB file.
    If handles leaked, rename would fail with PermissionError on Windows.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)

        # Create fresh config and service
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

        # Create schema and add test data
        service.sanitized_store.migrate()
        service.sanitized_store.save_chunks(
            [
                {
                    "chunk_id": f"chunk_{i}",
                    "conversation_id": "conv_1",
                    "message_ids": [1, 2],
                    "provider": "claude",
                    "sanitized_title": "Test",
                    "sanitized_content": f"test content {i}",
                    "privacy_level": "sanitized",
                    "token_references": [],
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "content_hash": f"hash_{i}",
                }
                for i in range(5)
            ]
        )

        chunk_ids = [f"chunk_{i}" for i in range(5)]

        # Call _chunks_by_ids 25 times - each one should close its handle
        for _ in range(25):
            results = service._chunks_by_ids(chunk_ids)
            assert isinstance(results, list), "_chunks_by_ids should return list"

        # Force garbage collection to release any lingering references
        import gc
        import time
        gc.collect()
        time.sleep(0.05)

        # If handles leaked, this rename will fail with PermissionError on Windows
        db_path = config.sanitized_db
        try:
            new_path = Path(tmpdir) / "sanitized_renamed.sqlite3"
            db_path.rename(new_path)
            # If we get here, the handle was actually released
            assert new_path.exists(), "Renamed file should exist"
        except PermissionError as e:
            pytest.fail(
                f"_chunks_by_ids leaked file handles: {e}\n"
                "Context manager did not close() connections - fix incomplete."
            )
