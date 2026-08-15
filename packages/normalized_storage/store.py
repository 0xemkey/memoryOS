from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from packages.chat_normalization.hashing import stable_id
from packages.chat_normalization.pipeline import ChatImportPipeline
from packages.common_models import ImportFailure, ImportJob, ImportResult, NormalizedSource
from packages.normalized_storage.models import (
    Base,
    NormalizedConversationRow,
    NormalizedImportJobRow,
    NormalizedMessageRow,
    NormalizedSourceRow,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def dt(value: datetime | None) -> str | None:
    return value.astimezone(timezone.utc).isoformat() if value is not None else None


class NormalizedImportStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine: Engine = create_engine(f"sqlite:///{self.db_path}", future=True)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False, future=True)

    def migrate(self) -> None:
        # Recreate engine if it was closed during deletion
        if self.engine is None:
            self.engine: Engine = create_engine(f"sqlite:///{self.db_path}", future=True)
            self.session_factory = sessionmaker(self.engine, expire_on_commit=False, future=True)
        Base.metadata.create_all(self.engine)

    def import_path(self, path: Path, provider: str = "auto") -> ImportJob:
        self.migrate()
        job_id = stable_id("job", {"path": str(path), "provider": provider, "created_at": dt(utc_now())})
        created_at = utc_now()
        pipeline = ChatImportPipeline()
        result = pipeline.import_path(path, provider)

        with self.session_factory.begin() as session:
            job = NormalizedImportJobRow(
                job_id=job_id,
                source_path=str(path),
                provider=provider,
                status="running",
                created_at=dt(created_at) or "",
            )
            session.add(job)
            if result.failures:
                self._finish_job(session, job, result, "failed")
                return self._job_to_model(job)

            persisted = ImportResult(warnings=result.warnings)
            for source in result.sources:
                if self._is_duplicate(session, source):
                    persisted.skipped_duplicates += 1
                    continue
                self._persist_source(session, source)
                persisted.imported_conversations += 1
                persisted.imported_messages += len(source.messages)
            self._finish_job(session, job, persisted, "completed")
            return self._job_to_model(job)

    def list_imports(self) -> list[ImportJob]:
        self.migrate()
        with self.session_factory() as session:
            rows = session.scalars(select(NormalizedImportJobRow).order_by(NormalizedImportJobRow.created_at)).all()
            return [self._job_to_model(row) for row in rows]

    def list_conversations(self) -> list[dict[str, Any]]:
        self.migrate()
        with self.session_factory() as session:
            rows = session.scalars(
                select(NormalizedConversationRow).order_by(NormalizedConversationRow.updated_at.desc())
            ).all()
            return [self._conversation_to_dict(row, include_messages=False) for row in rows]

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        self.migrate()
        with self.session_factory() as session:
            row = session.get(NormalizedConversationRow, conversation_id)
            return self._conversation_to_dict(row, include_messages=True) if row else None

    def _is_duplicate(self, session: Session, source: NormalizedSource) -> bool:
        existing = session.scalar(
            select(NormalizedConversationRow).where(
                NormalizedConversationRow.content_hash == source.conversation.content_hash
            )
        )
        return existing is not None

    def _persist_source(self, session: Session, source: NormalizedSource) -> None:
        if session.get(NormalizedSourceRow, source.source_fingerprint) is None:
            session.add(
                NormalizedSourceRow(
                    source_fingerprint=source.source_fingerprint,
                    source_path=source.conversation.source_file or "",
                    provider=source.conversation.provider,
                    metadata_json=json.dumps(
                        {"conversation_id": source.conversation.conversation_id}, ensure_ascii=False
                    ),
                    created_at=dt(utc_now()) or "",
                )
            )
        session.add(
            NormalizedConversationRow(
                conversation_id=source.conversation.conversation_id,
                source_fingerprint=source.source_fingerprint,
                provider=source.conversation.provider,
                remote_id=source.conversation.remote_id,
                title=source.conversation.title,
                created_at=dt(source.conversation.created_at),
                updated_at=dt(source.conversation.updated_at),
                source_file=source.conversation.source_file,
                metadata_json=json.dumps(source.conversation.metadata, ensure_ascii=False),
                content_hash=source.conversation.content_hash,
            )
        )
        for position, message in enumerate(source.messages, start=1):
            session.add(
                NormalizedMessageRow(
                    message_id=message.message_id,
                    conversation_id=message.conversation_id,
                    role=message.role,
                    content=message.content,
                    position=position,
                    created_at=dt(message.created_at),
                    metadata_json=json.dumps(message.metadata, ensure_ascii=False),
                    content_hash=message.content_hash,
                )
            )

    def _finish_job(
        self,
        session: Session,
        job: NormalizedImportJobRow,
        result: ImportResult,
        status: str,
    ) -> None:
        job.status = status
        job.imported_conversations = result.imported_conversations
        job.imported_messages = result.imported_messages
        job.skipped_duplicates = result.skipped_duplicates
        job.warnings_json = json.dumps([warning.model_dump() for warning in result.warnings])
        job.failures_json = json.dumps([failure.model_dump() for failure in result.failures])
        job.completed_at = dt(utc_now())
        session.add(job)

    def _job_to_model(self, row: NormalizedImportJobRow) -> ImportJob:
        return ImportJob(
            job_id=row.job_id,
            source_path=row.source_path,
            provider=row.provider,
            status=row.status,  # type: ignore[arg-type]
            imported_conversations=row.imported_conversations,
            imported_messages=row.imported_messages,
            skipped_duplicates=row.skipped_duplicates,
            warnings=[],
            failures=[ImportFailure(**failure) for failure in json.loads(row.failures_json or "[]")],
            created_at=datetime.fromisoformat(row.created_at),
            completed_at=datetime.fromisoformat(row.completed_at) if row.completed_at else None,
        )

    def _conversation_to_dict(
        self,
        row: NormalizedConversationRow,
        *,
        include_messages: bool,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "conversation_id": row.conversation_id,
            "provider": row.provider,
            "remote_id": row.remote_id,
            "title": row.title,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "source_file": row.source_file,
            "metadata": json.loads(row.metadata_json or "{}"),
            "content_hash": row.content_hash,
        }
        if include_messages:
            data["messages"] = [
                {
                    "message_id": message.message_id,
                    "conversation_id": message.conversation_id,
                    "role": message.role,
                    "content": message.content,
                    "position": message.position,
                    "created_at": message.created_at,
                    "metadata": json.loads(message.metadata_json or "{}"),
                    "content_hash": message.content_hash,
                }
                for message in row.messages
            ]
        return data

    def _close_all_connections(self) -> None:
        """Close all SQLAlchemy connections and reset engine.

        This must happen BEFORE file deletion on Windows, where SQLAlchemy's
        connection pool may keep file handles open even after dispose().
        """
        import gc
        import time

        # Step 1: Switch to DELETE journal mode before disposing
        # (WAL mode keeps separate -wal and -shm files open)
        try:
            session = self.session_factory()
            session.execute("PRAGMA journal_mode=DELETE")
            session.commit()
            # Get raw connection and close it explicitly
            connection = session.connection()
            session.close()
            connection.close()
        except Exception:
            pass

        # Step 2: Dispose engine to close all pooled connections
        try:
            # Close all checked-in connections in the pool
            self.engine.dispose()
        except Exception:
            pass

        # Step 3: Force garbage collection to release any remaining references
        gc.collect()
        time.sleep(0.05)

        # Step 4: Reset the engine and factory to force full re-creation next time
        self.engine = None
        self.session_factory = None

    def delete_all_data(self) -> None:
        """Securely delete all normalized import data.

        CRITICAL: Closes ALL SQLAlchemy connections before file deletion.
        Windows keeps file handles open unless pool is fully released.
        """
        import gc
        import time

        # Close all connections BEFORE attempting file deletion
        self._close_all_connections()

        # Force garbage collection to release any lingering sqlite3 handles
        gc.collect()
        time.sleep(0.02)

        # Force one more close via direct sqlite3 to ensure file is releasable
        # Explicitly close connection (context manager does NOT call close())
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("VACUUM")
            conn.close()
        except Exception:
            pass

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

        # Clean up WAL and SHM files
        wal_path = Path(str(self.db_path) + "-wal")
        shm_path = Path(str(self.db_path) + "-shm")
        if wal_path.exists():
            wal_path.unlink()
        if shm_path.exists():
            shm_path.unlink()
