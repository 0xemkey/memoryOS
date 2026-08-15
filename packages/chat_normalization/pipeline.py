from __future__ import annotations

from pathlib import Path

from packages.chat_normalization.hashing import content_hash
from memoryos_core.importers import (
    IMPORTERS,
    Importer as ChatImporter,
    ImporterError,
)
from packages.common_models import ImportFailure, ImportResult, ImportWarning, NormalizedSource
from packages.common_models.chat import NormalizedConversation, NormalizedMessage


class ChatImportPipeline:
    def __init__(self, importers: dict[str, ChatImporter] | None = None):
        self.importers = importers or {key: cls() for key, cls in IMPORTERS.items()}
        self._seen_hashes: set[str] = set()

    def import_path(self, path: Path, provider: str = "generic_json") -> ImportResult:
        if not path.exists() or not path.is_file():
            return ImportResult(
                failures=[
                    ImportFailure(
                        code="file_not_found",
                        message=f"Import file does not exist: {path}",
                        source_ref=str(path),
                    )
                ]
            )
        try:
            importer = self._select_importer(path, provider)
        except ImporterError as exc:
            return ImportResult(
                failures=[ImportFailure(code="unsupported_provider", message=str(exc), source_ref=str(path))]
            )
        try:
            sources = importer.parse(path)
        except ImporterError as exc:
            return ImportResult(failures=[ImportFailure(code="parse_error", message=str(exc), source_ref=str(path))])

        result = ImportResult()
        for source in sources:
            try:
                duplicate_key = content_hash(source.conversation.model_dump(mode="json"))
                if duplicate_key in self._seen_hashes:
                    result.skipped_duplicates += 1
                    continue
                self._seen_hashes.add(duplicate_key)
                result.imported_conversations += 1
                result.imported_messages += len(source.messages)
                converted_messages = []
                for msg in source.messages:
                    msg_data = msg.model_dump()
                    if "ordinal" in msg_data:
                        msg_data["position"] = msg_data.pop("ordinal")
                    converted_messages.append(NormalizedMessage(**msg_data))
                normalized_source = NormalizedSource(
                    conversation=NormalizedConversation(**source.conversation.model_dump()),
                    messages=converted_messages,
                    source_fingerprint=duplicate_key,
                )
                result.sources.append(normalized_source)
                result.warnings.extend(
                    ImportWarning(code="missing_timestamp", message=warning, source_ref=str(path))
                    for warning in source.conversation.metadata.get("normalization_warnings", [])
                )
            except Exception as exc:
                result.imported_conversations -= 1
                result.imported_messages -= len(source.messages)
                result.failures.append(
                    ImportFailure(code="model_validation_error", message=str(exc), source_ref=str(path))
                )
        return result

    def _select_importer(self, path: Path, provider: str) -> ChatImporter:
        if provider == "auto":
            if path.suffix.lower() == ".md":
                provider = "markdown"
            elif path.suffix.lower() == ".txt":
                provider = "gemini" if self._looks_like_gemini(path) else "plain_text"
            else:
                provider = "generic_json"
        try:
            return self.importers[provider]
        except KeyError as exc:
            raise ImporterError(f"Unsupported provider/import format: {provider}") from exc

    def _looks_like_gemini(self, path: Path) -> bool:
        try:
            sample = path.read_text(encoding="utf-8")[:4096]
        except UnicodeDecodeError:
            return False
        return '"conversation_turns"' in sample and ("\"user_turn\"" in sample or "\"system_turn\"" in sample)
