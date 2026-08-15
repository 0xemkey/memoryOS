from __future__ import annotations

import json
import shutil
import sqlite3
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memoryos_core.models import Chunk, ConversationBundle, NormalizedConversation, NormalizedMessage
from memoryos_core.util import content_hash, stable_id


def dt(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def from_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


class SQLiteStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "memoryos.sqlite3"

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def _connection(self):
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def migrate(self) -> None:
        migration_path = Path(__file__).parents[2] / "migrations" / "001_initial.sql"
        with self._connection() as conn:
            conn.executescript(migration_path.read_text(encoding="utf-8"))
            self._seed_settings(conn)

    def _seed_settings(self, conn: sqlite3.Connection) -> None:
        defaults = {
            "preferred_language": "English",
            "preferred_answer_length": "medium",
            "preferred_explanation_style": "clear",
            "technical_skill_level": "intermediate",
            "active_projects": [],
            "preferred_citation_behavior": "inline",
            "privacy_statement": "Your conversations and documents remain on this device.",
        }
        for key, value in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO user_settings(key, value_json) VALUES (?, ?)",
                (key, json.dumps(value)),
            )

    def create_import_job(self, provider: str, source_path: str) -> str:
        job_id = stable_id("job", {"provider": provider, "source_path": source_path, "now": dt(datetime.now(timezone.utc))})
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO import_jobs(job_id, provider, source_path, status, created_at)
                VALUES (?, ?, ?, 'running', ?)
                """,
                (job_id, provider, source_path, dt(datetime.now(timezone.utc))),
            )
        return job_id

    def finish_import_job(self, job_id: str, report: Any, status: str = "completed") -> None:
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE import_jobs
                SET status=?, imported=?, skipped=?, duplicated=?, failed=?, errors_json=?, completed_at=?
                WHERE job_id=?
                """,
                (
                    status,
                    report.imported,
                    report.skipped,
                    report.duplicated,
                    report.failed,
                    json.dumps(report.errors),
                    dt(datetime.now(timezone.utc)),
                    job_id,
                ),
            )

    def get_import_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM import_jobs WHERE job_id=?", (job_id,)).fetchone()
            return dict(row) if row else None

    def save_bundle(self, bundle: ConversationBundle) -> bool:
        with self._connection() as conn:
            exists = conn.execute(
                "SELECT 1 FROM conversations WHERE content_hash=?", (bundle.conversation.content_hash,)
            ).fetchone()
            if exists:
                return False
            conv = bundle.conversation
            conn.execute(
                """
                INSERT INTO conversations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conv.conversation_id,
                    conv.provider,
                    conv.remote_id,
                    conv.title,
                    dt(conv.created_at),
                    dt(conv.updated_at),
                    conv.source_file,
                    json.dumps(conv.metadata),
                    summarize_messages(bundle.messages),
                    conv.content_hash,
                ),
            )
            for msg in bundle.messages:
                conn.execute(
                    """
                    INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        msg.message_id,
                        msg.conversation_id,
                        msg.role,
                        msg.content,
                        dt(msg.created_at),
                        json.dumps(msg.metadata),
                        msg.ordinal,
                        msg.content_hash,
                    ),
                )
            source_hash = content_hash({"path": conv.source_file, "conversation": conv.content_hash})
            conn.execute(
                "INSERT OR IGNORE INTO sources VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    stable_id("src", source_hash),
                    "conversation",
                    conv.source_file,
                    conv.provider,
                    json.dumps(conv.metadata),
                    source_hash,
                    dt(datetime.now(timezone.utc)),
                ),
            )
            return True

    def save_chunks(self, chunks: list[Chunk], embeddings: dict[str, list[float]]) -> None:
        with self._connection() as conn:
            for chunk in chunks:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.chunk_id,
                        chunk.conversation_id,
                        chunk.provider,
                        chunk.conversation_title,
                        json.dumps(chunk.message_ids),
                        json.dumps(chunk.roles),
                        chunk.content,
                        dt(chunk.created_at),
                        dt(chunk.updated_at),
                        chunk.source_path,
                        chunk.source_type,
                        chunk.content_hash,
                        json.dumps(chunk.metadata),
                        json.dumps(embeddings.get(chunk.chunk_id)),
                    ),
                )

    def list_conversations(self) -> list[dict[str, Any]]:
        with self._connection() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM conversations ORDER BY updated_at DESC")]

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            conv = conn.execute("SELECT * FROM conversations WHERE conversation_id=?", (conversation_id,)).fetchone()
            if not conv:
                return None
            messages = conn.execute(
                "SELECT * FROM messages WHERE conversation_id=? ORDER BY ordinal", (conversation_id,)
            ).fetchall()
            data = dict(conv)
            data["messages"] = [dict(row) for row in messages]
            return data

    def all_chunks(self) -> list[dict[str, Any]]:
        with self._connection() as conn:
            return [dict(row) for row in conn.execute("SELECT rowid, * FROM chunks")]

    def keyword_search(self, query: str, filters: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
        where, params = self._filter_sql(filters, alias="c")
        sql = f"""
            SELECT c.*, bm25(chunks_fts) AS rank
            FROM chunks_fts
            JOIN chunks c ON c.rowid = chunks_fts.rowid
            WHERE chunks_fts MATCH ? {where}
            ORDER BY rank
            LIMIT ?
        """
        with self._connection() as conn:
            return [dict(row) for row in conn.execute(sql, [query, *params, limit])]

    def _filter_sql(self, filters: dict[str, Any], alias: str = "c") -> tuple[str, list[Any]]:
        clauses = []
        params: list[Any] = []
        if filters.get("provider"):
            clauses.append(f"{alias}.provider = ?")
            params.append(filters["provider"])
        if filters.get("title"):
            clauses.append(f"{alias}.conversation_title LIKE ?")
            params.append(f"%{filters['title']}%")
        if filters.get("source_type"):
            clauses.append(f"{alias}.source_type = ?")
            params.append(filters["source_type"])
        if filters.get("date_from"):
            clauses.append(f"{alias}.created_at >= ?")
            params.append(filters["date_from"])
        if filters.get("date_to"):
            clauses.append(f"{alias}.created_at <= ?")
            params.append(filters["date_to"])
        return (" AND " + " AND ".join(clauses), params) if clauses else ("", [])

    def get_settings(self) -> dict[str, Any]:
        with self._connection() as conn:
            return {row["key"]: json.loads(row["value_json"]) for row in conn.execute("SELECT * FROM user_settings")}

    def put_settings(self, values: dict[str, Any]) -> dict[str, Any]:
        with self._connection() as conn:
            for key, value in values.items():
                conn.execute(
                    "INSERT INTO user_settings(key, value_json) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json",
                    (key, json.dumps(value)),
                )
        return self.get_settings()

    def export_archive(self, target: Path) -> Path:
        target.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(self.db_path, "memoryos.sqlite3")
        return target

    def delete_all_data(self) -> None:
        if self.data_dir.exists():
            shutil.rmtree(self.data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.migrate()


def summarize_messages(messages: list[NormalizedMessage]) -> str:
    first_user = next((m.content for m in messages if m.role == "user"), messages[0].content)
    snippet = " ".join(first_user.split())
    return snippet[:500]
