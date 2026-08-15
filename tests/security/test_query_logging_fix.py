"""Test that retrieval_events audit table stores counts only, never raw query text.

This test verifies the fix for the query logging privacy violation where
sanitized_query was stored as TEXT instead of query_length as INTEGER.

See: migrations/sanitized/002_fix_query_logging.sql
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from packages.sanitized_storage.store import SanitizedStore


@pytest.fixture
def temp_db():
    """Create a temporary sanitized database for testing."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_sanitized.sqlite3"
        store = SanitizedStore(db_path)
        store.migrate()
        yield db_path, store


def test_query_logging_schema_has_no_query_text_column(temp_db: tuple[Path, SanitizedStore]) -> None:
    """Verify the retrieval_events schema stores length only, not query text."""
    db_path, store = temp_db

    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute("PRAGMA table_info(retrieval_events)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

    # Must have query_length (integer), never sanitized_query (text)
    assert "query_length" in columns, "Schema missing query_length column"
    assert columns["query_length"] == "INTEGER", "query_length must be INTEGER type"

    # Must have result_count for audit trail
    assert "result_count" in columns, "Schema missing result_count column"
    assert columns["result_count"] == "INTEGER", "result_count must be INTEGER type"

    # Must NOT have the vulnerable column
    assert "sanitized_query" not in columns, \
        "PRIVACY VIOLATION: Schema still has sanitized_query TEXT column"


def test_log_retrieval_event_stores_length_not_text(temp_db: tuple[Path, SanitizedStore]) -> None:
    """Verify that log_retrieval_event() stores query length, not the query text."""
    db_path, store = temp_db

    # Use a distinctive query that we can search for to verify it's NOT stored
    sensitive_query = "SELECT * FROM users WHERE password = 'super-secret-password-12345'"
    result_ids = ["chunk_1", "chunk_2", "chunk_3"]
    filters = {"provider": "test"}

    # Log the event
    store.log_retrieval_event(sensitive_query, result_ids, filters)

    # Read back the audit record
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM retrieval_events LIMIT 1").fetchone()

    assert row is not None, "No audit event was logged"

    # Verify ONLY length and count are stored, not the raw query
    query_length_stored = row["query_length"]
    result_count_stored = row["result_count"]

    assert query_length_stored == len(sensitive_query), \
        f"Query length mismatch: expected {len(sensitive_query)}, got {query_length_stored}"
    assert result_count_stored == len(result_ids), \
        f"Result count mismatch: expected {len(result_ids)}, got {result_count_stored}"

    # CRITICAL: Verify the sensitive query text does NOT appear in the record
    row_dict = dict(row)
    row_str = " ".join(str(v) for v in row_dict.values())
    assert "super-secret-password-12345" not in row_str, \
        "PRIVACY VIOLATION: Raw query text found in audit record"
    assert "SELECT * FROM users" not in row_str, \
        "PRIVACY VIOLATION: Query text pattern found in audit record"


def test_query_logging_serializes_filters_not_query(temp_db: tuple[Path, SanitizedStore]) -> None:
    """Verify filters are logged but query text is never logged."""
    db_path, store = temp_db

    query = "confidential search about user data migration 2024"
    result_ids = ["chunk_abc", "chunk_def"]
    filters = {"provider": "claude", "conversation_id": "conv_123", "privacy_level": "sanitized"}

    store.log_retrieval_event(query, result_ids, filters)

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT query_length, result_count, filters_json, result_ids_json FROM retrieval_events LIMIT 1"
        ).fetchone()

    assert row is not None

    query_length, result_count, filters_json, result_ids_json = row

    # Verify counts are correct
    assert query_length == len(query)
    assert result_count == len(result_ids)

    # Verify filters ARE logged (they're metadata, not content)
    import json
    logged_filters = json.loads(filters_json)
    assert logged_filters == filters

    # Verify result IDs ARE logged (they're chunk references, not content)
    logged_ids = json.loads(result_ids_json)
    assert logged_ids == result_ids

    # Verify the query itself is NOT logged anywhere
    assert query not in filters_json
    assert query not in result_ids_json


def test_query_logging_with_long_query(temp_db: tuple[Path, SanitizedStore]) -> None:
    """Test that even very long queries are logged by length only."""
    db_path, store = temp_db

    # Create a long query that would be dangerous to log
    long_query = "SELECT * FROM conversations WHERE content LIKE '%" + ("secret" * 1000) + "%'"

    store.log_retrieval_event(long_query, ["chunk_1"], {})

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT query_length FROM retrieval_events WHERE query_length = ?",
            (len(long_query),)
        ).fetchone()

    assert row is not None, f"Should find event with query_length={len(long_query)}"

    # Verify full query text is not stored anywhere - there should be no sanitized_query TEXT column
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute("PRAGMA table_info(retrieval_events)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

    assert "sanitized_query" not in columns, \
        "retrieval_events should not have a sanitized_query TEXT column"
    assert columns.get("query_length") == "INTEGER", \
        "query_length should be INTEGER, not TEXT"


def test_query_logging_two_independent_events(temp_db: tuple[Path, SanitizedStore]) -> None:
    """Verify that two separate retrieval events are both logged with correct lengths."""
    db_path, store = temp_db

    # Log first event without calling migrate again
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO retrieval_events (event_id, query_length, result_count, filters_json, result_ids_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("event_1", 5, 1, "{}", "[]", "2026-01-01T00:00:00+00:00"),
        )
        conn.execute(
            """
            INSERT INTO retrieval_events (event_id, query_length, result_count, filters_json, result_ids_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("event_2", 29, 1, "{}", "[]", "2026-01-01T00:00:00+00:00"),
        )
        conn.commit()

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT query_length FROM retrieval_events ORDER BY query_length").fetchall()

    stored_lengths = [row[0] for row in rows]
    assert len(stored_lengths) == 2, f"Should have 2 events, got {len(stored_lengths)}"
    assert stored_lengths == [5, 29], f"Query lengths mismatch: expected [5, 29], got {stored_lengths}"
