from __future__ import annotations

from pathlib import Path

from memoryos_core.chunking import chunk_conversation
from memoryos_core.embeddings import EmbeddingProvider
from memoryos_core.importers import importer_for
from memoryos_core.importers.base import ImportReport
from memoryos_core.storage import SQLiteStore


def import_file(path: Path, provider: str, store: SQLiteStore, embedder: EmbeddingProvider) -> ImportReport:
    report = ImportReport()
    importer = importer_for(provider, path)
    try:
        bundles = importer.parse(path)
    except Exception as exc:
        report.failed += 1
        report.errors.append(str(exc))
        return report

    for bundle in bundles:
        try:
            if not store.save_bundle(bundle):
                report.duplicated += 1
                continue
            chunks = chunk_conversation(bundle)
            embeddings = {chunk.chunk_id: embedder.embed(chunk.content) for chunk in chunks}
            store.save_chunks(chunks, embeddings)
            report.imported += 1
            report.conversation_ids.append(bundle.conversation.conversation_id)
        except Exception as exc:
            report.failed += 1
            report.errors.append(f"{bundle.conversation.title}: {exc}")
    return report
