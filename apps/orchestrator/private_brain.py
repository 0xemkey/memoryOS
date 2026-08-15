from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packages.chat_normalization import ChatImportPipeline
from packages.normalized_storage import NormalizedImportStore
from packages.normalized_storage.config import normalized_db_path
from packages.privacy_detection import PrivacyScanner
from packages.reasoning import BoundedReasoningWorkflow, OllamaChatClient, SanitizedReasoner
from packages.retrieval import OllamaEmbeddingClient, SanitizedChunker, SanitizedRetriever
from packages.sanitized_storage import SanitizationService, SanitizedStore
from packages.vault_crypto import EphemeralKeyProvider, KeyProvider, KeyringKeyProvider, RevealGateway, RevealRequest, VaultStore


@dataclass
class PrivateBrainConfig:
    data_dir: Path
    normalized_db: Path
    vault_db: Path
    sanitized_db: Path
    use_legacy_mvp: bool
    ollama_base_url: str
    chat_model: str
    embedding_model: str


def get_private_brain_config() -> PrivateBrainConfig:
    data_dir = Path(os.getenv("MEMORYOS_DATA_DIR", ".memoryos_data")).expanduser()
    return PrivateBrainConfig(
        data_dir=data_dir,
        normalized_db=Path(os.getenv("MEMORYOS_NORMALIZED_DB", str(normalized_db_path()))).expanduser(),
        vault_db=Path(os.getenv("MEMORYOS_VAULT_DB", str(data_dir / "vault.sqlite3"))).expanduser(),
        sanitized_db=Path(os.getenv("MEMORYOS_SANITIZED_DB", str(data_dir / "sanitized.sqlite3"))).expanduser(),
        use_legacy_mvp=os.getenv("MEMORYOS_USE_LEGACY_MVP", "false").lower() == "true",
        ollama_base_url=os.getenv("MEMORYOS_OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        chat_model=os.getenv("MEMORYOS_CHAT_MODEL", "llama3.1"),
        embedding_model=os.getenv("MEMORYOS_EMBEDDING_MODEL", "nomic-embed-text"),
    )


class PrivateBrainService:
    def __init__(self, config: PrivateBrainConfig | None = None, vault_key_provider: KeyProvider | None = None):
        self.config = config or get_private_brain_config()
        self.config.data_dir.mkdir(parents=True, exist_ok=True)
        self.normalized_store = NormalizedImportStore(self.config.normalized_db)
        self.sanitized_store = SanitizedStore(self.config.sanitized_db)
        key_provider = vault_key_provider or (
            EphemeralKeyProvider(allow_unsafe_development_mode=True)
            if os.getenv("MEMORYOS_UNSAFE_EPHEMERAL_VAULT", "false").lower() == "true"
            else KeyringKeyProvider()
        )
        self.vault_store = VaultStore(
            self.config.vault_db,
            key_provider,
        )
        self.scanner = PrivacyScanner()

    def import_file(self, path: Path, provider: str = "auto") -> dict[str, Any]:
        job = self.normalized_store.import_path(path, provider)
        result = ChatImportPipeline().import_path(path, provider)
        stats = {
            "job_id": job.job_id,
            "imported_conversations": 0,
            "imported_messages": 0,
            "skipped_duplicates": job.skipped_duplicates,
            "privacy_findings": 0,
            "sanitized_messages": 0,
            "quarantined_messages": 0,
            "chunks_indexed": 0,
            "warnings": [warning.model_dump() for warning in job.warnings],
            "failures": [failure.model_dump() for failure in job.failures],
            "stages": [
                "reading_export",
                "normalizing",
                "privacy_scanning",
                "pseudonymizing",
                "sanitizing",
                "chunking",
                "indexing",
            ],
        }
        if job.status == "failed" or result.failures:
            stats["status"] = "failed"
            stats["failures"].extend(failure.model_dump() for failure in result.failures)
            return stats

        sanitizer = SanitizationService(self.scanner, self.vault_store)
        chunker = SanitizedChunker()
        retriever = SanitizedRetriever(self.sanitized_store)
        for source in result.sources:
            package = sanitizer.sanitize_source(source)
            self.sanitized_store.save_package(package)
            chunks = chunker.chunk_package(package)
            retriever.index_chunks(chunks)
            stats["imported_conversations"] += len(package.sanitized_conversations)
            stats["imported_messages"] += len(source.messages)
            stats["privacy_findings"] += package.privacy_statistics.get("findings", 0)
            stats["sanitized_messages"] += package.privacy_statistics.get("sanitized_messages", 0)
            stats["quarantined_messages"] += package.privacy_statistics.get("quarantined_messages", 0)
            stats["chunks_indexed"] += len(chunks)
        stats["status"] = "completed"
        return stats

    def list_conversations(self) -> list[dict[str, Any]]:
        self.sanitized_store.migrate()
        conn = sqlite3.connect(self.config.sanitized_db)
        try:
            conn.row_factory = sqlite3.Row
            return [
                {
                    "conversation_id": row["conversation_id"],
                    "provider": row["provider"],
                    "title": row["sanitized_title"],
                    "updated_at": row["updated_at"],
                    "privacy_level": "sanitized",
                }
                for row in conn.execute("SELECT * FROM sanitized_conversations ORDER BY updated_at DESC")
            ]
        finally:
            conn.close()

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        self.sanitized_store.migrate()
        conn = sqlite3.connect(self.config.sanitized_db)
        try:
            conn.row_factory = sqlite3.Row
            conversation = conn.execute(
                "SELECT * FROM sanitized_conversations WHERE conversation_id=?", (conversation_id,)
            ).fetchone()
            if conversation is None:
                return None
            messages = conn.execute(
                "SELECT * FROM sanitized_messages WHERE conversation_id=? ORDER BY rowid",
                (conversation_id,),
            ).fetchall()
        finally:
            conn.close()
        return {
            "conversation_id": conversation["conversation_id"],
            "provider": conversation["provider"],
            "title": conversation["sanitized_title"],
            "updated_at": conversation["updated_at"],
            "messages": [
                {
                    "message_id": message["message_id"],
                    "role": message["role"],
                    "content": message["sanitized_content"],
                    "ordinal": index + 1,
                    "created_at": message["created_at"],
                    "privacy_level": message["privacy_level"],
                }
                for index, message in enumerate(messages)
            ],
        }

    def search(self, query: str, filters: dict[str, Any] | None = None, limit: int = 10) -> dict[str, Any]:
        retriever = SanitizedRetriever(self.sanitized_store)
        response = retriever.search(query, filters=filters, limit=limit)
        return {
            "results": [self._result_to_ui(item) for item in response.results],
            "retrieval_mode": response.degraded_mode or "hybrid",
            "warnings": response.warnings,
        }

    def ask(self, query: str, filters: dict[str, Any] | None = None, limit: int = 6) -> dict[str, Any]:
        retriever = SanitizedRetriever(self.sanitized_store)
        chat_client = OllamaChatClient(base_url=self.config.ollama_base_url, model=self.config.chat_model)
        workflow = BoundedReasoningWorkflow(retriever, SanitizedReasoner(chat_client))
        answer, state = workflow.run(query, filters=filters)
        evidence = self._chunks_by_ids(state.retrieved_source_ids)
        return {
            "answer_id": answer.answer_id,
            "answer": answer.sanitized_answer,
            "sanitized_answer": answer.sanitized_answer,
            "citations": answer.citation_ids,
            "citation_ids": answer.citation_ids,
            "evidence_sufficient": answer.evidence_sufficient,
            "warnings": answer.warnings + state.warnings,
            "retrieval_mode": "keyword_fallback" if any("keyword-only" in w for w in state.warnings) else "hybrid",
            "reasoning_mode": answer.model_metadata.get("mode", "unknown"),
            "retrieved_context": [self._result_to_ui(item) for item in evidence],
            "state": state.model_dump(mode="json"),
        }

    def reveal_answer(self, sanitized_answer: str, mode: str, reveal_types: list[str] | None = None) -> dict[str, Any]:
        response = RevealGateway(self.vault_store).reveal(
            RevealRequest(
                sanitized_answer=sanitized_answer,
                approved=True,
                mode=mode,  # type: ignore[arg-type]
                reveal_types=reveal_types or [],
            )
        )
        return response.model_dump()

    def diagnostics(self) -> dict[str, Any]:
        return {
            "privacy_vault": "ready" if self.config.vault_db.parent.exists() else "unavailable",
            "vault_key_provider": self.vault_store.key_provider.key_version,
            "normalized_storage": "ready",
            "sanitized_storage": "ready",
            "fts_index": "ready",
            "embedding_model": self.config.embedding_model,
            "reasoning_model": self.config.chat_model,
            "retrieval_mode": "keyword_fallback",
            "reasoning_mode": "ollama_or_deterministic_fallback",
            "container_isolation": "UNVERIFIED",
            "legacy_mvp_default": self.config.use_legacy_mvp,
        }

    def delete_all_data(self) -> dict[str, Any]:
        """Cascade delete all data across normalized, sanitized, and vault databases.

        This is the privacy-critical deletion operation. It must wipe:
        1. Normalized imports (raw conversations before sanitization)
        2. Sanitized content (pseudonymized conversations)
        3. Vault mappings (encrypted entity values)
        4. Vault keychain entry (encryption key)

        Returns a report of what was deleted.
        """
        results = {
            "normalized_deleted": False,
            "sanitized_deleted": False,
            "vault_deleted": False,
            "keychain_cleared": False,
            "errors": [],
        }

        try:
            self.normalized_store.delete_all_data()
            results["normalized_deleted"] = True
        except Exception as exc:
            results["errors"].append(f"Failed to delete normalized data: {exc}")

        try:
            self.sanitized_store.delete_all_data()
            results["sanitized_deleted"] = True
        except Exception as exc:
            results["errors"].append(f"Failed to delete sanitized data: {exc}")

        try:
            self.vault_store.delete_all_data()
            results["vault_deleted"] = True
        except Exception as exc:
            results["errors"].append(f"Failed to delete vault data: {exc}")

        try:
            self.vault_store.clear_keychain_entry()
            results["keychain_cleared"] = True
        except Exception as exc:
            results["errors"].append(f"Failed to clear keychain: {exc}")

        if results["errors"]:
            results["status"] = "partial_failure"
        else:
            results["status"] = "success"

        return results

    def _chunks_by_ids(self, chunk_ids: list[str]) -> list[dict[str, Any]]:
        if not chunk_ids:
            return []
        self.sanitized_store.migrate()
        placeholders = ",".join("?" for _ in chunk_ids)
        conn = sqlite3.connect(self.config.sanitized_db)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"SELECT * FROM sanitized_chunks WHERE chunk_id IN ({placeholders})",
                chunk_ids,
            ).fetchall()
        finally:
            conn.close()
        by_id = {row["chunk_id"]: dict(row) for row in rows}
        return [by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in by_id]

    def _result_to_ui(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "chunk_id": item["chunk_id"],
            "score": float(item.get("score", 0)),
            "provider": item["provider"],
            "conversation_title": item["sanitized_title"],
            "conversation_id": item["conversation_id"],
            "message_ids": __import__("json").loads(item["message_ids_json"]) if "message_ids_json" in item else item.get("message_ids", []),
            "created_at": item.get("created_at"),
            "snippet": " ".join(item["sanitized_content"].split())[:300],
            "source_type": "conversation",
            "privacy_level": item.get("privacy_level"),
        }
