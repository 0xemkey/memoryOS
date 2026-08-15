from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from packages.chat_normalization.hashing import content_hash, stable_id
from packages.pseudonymization import create_pseudonym, normalize_entity_value
from packages.vault_crypto.crypto import VaultCipher
from packages.vault_crypto.keys import KeyProvider


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class VaultEntity:
    token: str
    entity_type: str
    encrypted_original_value: bytes
    normalized_fingerprint: str
    key_version: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ReviewItem:
    review_item_id: str
    message_ref: str
    token: str | None
    entity_type: str
    recommended_action: str
    status: str
    confidence: float
    created_at: str
    updated_at: str


class VaultStore:
    def __init__(self, db_path: Path, key_provider: KeyProvider):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.key_provider = key_provider

    def migrate(self) -> None:
        sql = Path(__file__).parents[2] / "migrations" / "vault" / "001_initial.sql"
        conn = sqlite3.connect(self.db_path)
        conn.executescript(sql.read_text(encoding="utf-8"))
        conn.close()

    def upsert_entity(self, entity_type: str, original_value: str) -> str:
        self.migrate()
        key = self.key_provider.get_key()
        token = create_pseudonym(key, entity_type, original_value)
        normalized = normalize_entity_value(entity_type, original_value)
        fingerprint = content_hash({"entity_type": entity_type, "normalized": normalized})
        encrypted = VaultCipher(key).encrypt_text(original_value)
        now = utc_now()
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("SELECT token FROM vault_entities WHERE token=?", (token,)).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO vault_entities(
                  token, entity_type, encrypted_original_value, normalized_fingerprint,
                  key_version, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    token,
                    entity_type,
                    encrypted,
                    fingerprint,
                    self.key_provider.key_version,
                    now,
                    now,
                ),
            )
        else:
            conn.execute("UPDATE vault_entities SET updated_at=? WHERE token=?", (now, token))
        conn.commit()
        conn.close()
        return token

    def resolve_token(self, token: str) -> str | None:
        self.migrate()
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT encrypted_original_value FROM vault_entities WHERE token=?", (token,)
        ).fetchone()
        conn.close()
        if row is None:
            return None
        return VaultCipher(self.key_provider.get_key()).decrypt_text(row[0])

    def entity_type_for_token(self, token: str) -> str | None:
        self.migrate()
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("SELECT entity_type FROM vault_entities WHERE token=?", (token,)).fetchone()
        conn.close()
        return row[0] if row else None

    def create_review_item(
        self,
        *,
        message_ref: str,
        entity_type: str,
        recommended_action: str,
        confidence: float,
        token: str | None = None,
    ) -> ReviewItem:
        self.migrate()
        now = utc_now()
        review_item_id = stable_id(
            "review",
            [message_ref, entity_type, recommended_action, confidence, token],
        )
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT OR IGNORE INTO vault_review_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                review_item_id,
                message_ref,
                token,
                entity_type,
                recommended_action,
                "pending",
                confidence,
                now,
                now,
            ),
        )
        conn.commit()
        conn.close()
        return self.get_review_item(review_item_id)  # type: ignore[return-value]

    def list_review_items(self) -> list[ReviewItem]:
        self.migrate()
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("SELECT * FROM vault_review_items ORDER BY created_at").fetchall()
        conn.close()
        return [ReviewItem(*row) for row in rows]

    def get_review_item(self, review_item_id: str) -> ReviewItem | None:
        self.migrate()
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT * FROM vault_review_items WHERE review_item_id=?", (review_item_id,)
        ).fetchone()
        conn.close()
        return ReviewItem(*row) if row else None

    def update_review_item(self, review_item_id: str, *, status: str, action: str | None = None) -> ReviewItem | None:
        self.migrate()
        now = utc_now()
        conn = sqlite3.connect(self.db_path)
        if action is None:
            conn.execute(
                "UPDATE vault_review_items SET status=?, updated_at=? WHERE review_item_id=?",
                (status, now, review_item_id),
            )
        else:
            conn.execute(
                """
                UPDATE vault_review_items
                SET status=?, recommended_action=?, updated_at=?
                WHERE review_item_id=?
                """,
                (status, action, now, review_item_id),
            )
        conn.commit()
        conn.close()
        return self.get_review_item(review_item_id)

    def append_audit_event(self, event_type: str, subject_ref: str | None, metadata: dict) -> None:
        self.migrate()
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO vault_audit_events VALUES (?, ?, ?, ?, ?)",
            (
                stable_id("audit", [event_type, subject_ref, metadata, utc_now()]),
                event_type,
                subject_ref,
                __import__("json").dumps(metadata, sort_keys=True),
                utc_now(),
            ),
        )
        conn.commit()
        conn.close()

    def audit_events(self) -> list[tuple]:
        self.migrate()
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("SELECT event_type, subject_ref, metadata_json FROM vault_audit_events").fetchall()
        conn.close()
        return rows

    def raw_database_bytes(self) -> bytes:
        return self.db_path.read_bytes()

    def delete_all_data(self) -> None:
        """Securely delete all vault data including encrypted mappings and audit events.

        Explicitly closes SQLite connection before deletion (context manager
        only handles transactions, not connection close).
        """
        import time
        import gc
        from pathlib import Path as _Path

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
        wal_path = _Path(str(self.db_path) + "-wal")
        shm_path = _Path(str(self.db_path) + "-shm")
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

    def clear_keychain_entry(self) -> None:
        """Clear the OS keychain entry for the vault encryption key."""
        try:
            import keyring
            service_name = "MemoryOS"
            username = "vault_key"
            keyring.delete_password(service_name, username)
        except Exception:
            # If keyring operation fails, it may mean the entry doesn't exist or keyring is unavailable
            # This is not a fatal error for data deletion
            pass
