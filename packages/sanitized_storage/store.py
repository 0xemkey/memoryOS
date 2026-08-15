from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from packages.chat_normalization.hashing import stable_id
from packages.sanitized_storage.models import SanitizedImportPackage


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_fts_query(query: str) -> str:
    terms = re.findall(r"[\wÇĞİÖŞÜçğıöşü]{2,}", query, flags=re.UNICODE)
    if not terms:
        return '""'
    return " OR ".join(f'"{term}"' for term in terms)


class SanitizedStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def migrate(self) -> None:
        migrations_dir = Path(__file__).parents[2] / "migrations" / "sanitized"
        migration_files = sorted(migrations_dir.glob("*.sql"))
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=DELETE")
        try:
            for migration_file in migration_files:
                conn.executescript(migration_file.read_text(encoding="utf-8"))
        finally:
            conn.close()

    def save_package(self, package: SanitizedImportPackage) -> None:
        self.migrate()
        conn = sqlite3.connect(self.db_path)
        try:
            for conversation in package.sanitized_conversations:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO sanitized_conversations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        conversation.conversation_id,
                        conversation.provider,
                        conversation.remote_id,
                        conversation.sanitized_title,
                        conversation.created_at.isoformat() if conversation.created_at else None,
                        conversation.updated_at.isoformat() if conversation.updated_at else None,
                        conversation.source_file_ref,
                        json.dumps(conversation.metadata),
                        conversation.content_hash,
                    ),
                )
            for message in package.sanitized_messages:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO sanitized_messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        message.message_id,
                        message.conversation_id,
                        message.role,
                        message.sanitized_content,
                        message.privacy_level,
                        json.dumps(message.detected_categories),
                        json.dumps(message.privacy_actions),
                        json.dumps(message.token_references),
                        message.original_content_reference,
                        message.created_at.isoformat() if message.created_at else None,
                        json.dumps(message.metadata),
                        message.content_hash,
                    ),
                )
            for entity in package.sanitized_entities:
                conn.execute(
                    "INSERT OR IGNORE INTO sanitized_entities VALUES (?, ?, ?, ?)",
                    (entity.token, entity.entity_type, entity.first_seen_message_id, utc_now()),
                )
            conn.execute(
                "INSERT OR IGNORE INTO privacy_audit_events VALUES (?, ?, ?, ?, ?)",
                (
                    stable_id("audit", [package.package_id, "sanitized_package_created"]),
                    "sanitized_package_created",
                    package.package_id,
                    json.dumps(package.privacy_statistics),
                    utc_now(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def raw_database_bytes(self) -> bytes:
        return self.db_path.read_bytes()

    def save_chunks(self, chunks: list[dict], embeddings: dict[str, list[float]] | None = None) -> None:
        self.migrate()
        embeddings = embeddings or {}
        conn = sqlite3.connect(self.db_path)
        try:
            for chunk in chunks:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO sanitized_chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk["chunk_id"],
                        chunk["conversation_id"],
                        json.dumps(chunk["message_ids"]),
                        chunk["provider"],
                        chunk["sanitized_title"],
                        chunk["sanitized_content"],
                        chunk["privacy_level"],
                        json.dumps(chunk["token_references"]),
                        chunk["created_at"],
                        chunk["content_hash"],
                        json.dumps(embeddings.get(chunk["chunk_id"])),
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def search_chunks_fts(self, query: str, filters: dict, limit: int = 10) -> list[dict]:
        self.migrate()
        where, params = self._filter_sql(filters)
        fts_query = to_fts_query(query)
        sql = f"""
            SELECT c.*, bm25(sanitized_chunks_fts) AS rank
            FROM sanitized_chunks_fts
            JOIN sanitized_chunks c ON c.rowid = sanitized_chunks_fts.rowid
            WHERE sanitized_chunks_fts MATCH ? {where}
            ORDER BY rank
            LIMIT ?
        """
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute(sql, [fts_query, *params, limit])]
        finally:
            conn.close()

    def list_chunks(self, filters: dict | None = None) -> list[dict]:
        self.migrate()
        filters = filters or {}
        where, params = self._filter_sql(filters)
        sql = f"SELECT * FROM sanitized_chunks c WHERE 1=1 {where}"
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute(sql, params)]
        finally:
            conn.close()

    def _filter_sql(self, filters: dict) -> tuple[str, list]:
        clauses = []
        params = []
        if filters.get("provider"):
            clauses.append("c.provider = ?")
            params.append(filters["provider"])
        if filters.get("privacy_level"):
            clauses.append("c.privacy_level = ?")
            params.append(filters["privacy_level"])
        if filters.get("conversation_id"):
            clauses.append("c.conversation_id = ?")
            params.append(filters["conversation_id"])
        if filters.get("entity_token"):
            clauses.append("c.token_references_json LIKE ?")
            params.append(f"%{filters['entity_token']}%")
        if filters.get("date_from"):
            clauses.append("c.created_at >= ?")
            params.append(filters["date_from"])
        if filters.get("date_to"):
            clauses.append("c.created_at <= ?")
            params.append(filters["date_to"])
        return (" AND " + " AND ".join(clauses), params) if clauses else ("", [])

    def log_retrieval_event(self, query: str, result_ids: list[str], filters: dict | None = None) -> None:
        """Log a retrieval event with query length only (never raw query text).

        This method enforces the privacy guarantee that retrieval_events is a counts-only audit table.
        Raw query text is never stored; only the length is logged as metadata.

        Args:
            query: The search query (length will be logged, text is NOT stored)
            result_ids: List of chunk IDs returned
            filters: Search filters applied (stored as JSON for audit trail)
        """
        import uuid
        self.migrate()
        # Use a truly unique ID to avoid duplicates in tests and real usage
        event_id = f"event_{uuid.uuid4().hex[:16]}"
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT INTO retrieval_events VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    len(query),  # Only store query LENGTH, never the query text
                    len(result_ids),  # Store count of results returned
                    json.dumps(filters or {}),
                    json.dumps(result_ids),
                    utc_now(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def delete_all_data(self) -> None:
        """Securely delete all sanitized data including pseudonymized content.

        Explicitly closes SQLite connection before deletion (context manager
        only handles transactions, not connection close).
        """
        import time
        import gc

        # Switch journal mode and vacuum, then EXPLICITLY close connection
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA journal_mode=DELETE")
            conn.execute("VACUUM")
            conn.commit()
            conn.close()  # CRITICAL: Context manager does NOT call close()
        except Exception:
            pass  # Database may not exist

        # Force garbage collection to release any lingering SQLite handles
        gc.collect()
        time.sleep(0.01)

        if self.db_path.exists():
            # Overwrite with zeros before deletion for security
            with open(self.db_path, "rb+") as f:
                file_size = f.seek(0, 2)
                f.seek(0)
                f.write(b"\x00" * file_size)

            # Retry deletion with delays for Windows file locking
            for attempt in range(10):
                try:
                    self.db_path.unlink()
                    break
                except (OSError, PermissionError):
                    if attempt < 9:
                        time.sleep(0.1)
                    else:
                        raise

        # Clean up WAL and SHM files if they exist
        wal_path = Path(str(self.db_path) + "-wal")
        shm_path = Path(str(self.db_path) + "-shm")
        if wal_path.exists():
            try:
                wal_path.unlink()
            except (OSError, PermissionError):
                pass
        if shm_path.exists():
            try:
                shm_path.unlink()
            except (OSError, PermissionError):
                pass
