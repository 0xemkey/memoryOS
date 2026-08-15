from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from packages.retrieval.embeddings import OllamaEmbeddingClient, OllamaUnavailableError, cosine
from packages.sanitized_storage.store import SanitizedStore


@dataclass
class RetrievalResponse:
    results: list[dict[str, Any]]
    degraded_mode: str | None = None
    warnings: list[str] = field(default_factory=list)


class SanitizedRetriever:
    def __init__(self, store: SanitizedStore, embedder: OllamaEmbeddingClient | None = None):
        self.store = store
        self.embedder = embedder

    def index_chunks(self, chunks: list[dict]) -> None:
        self.store.save_chunks(chunks, embeddings={})

    def search(self, query: str, filters: dict[str, Any] | None = None, limit: int = 10) -> RetrievalResponse:
        filters = filters or {}
        keyword = self.store.search_chunks_fts(query, filters, limit=limit * 2)
        semantic: list[dict[str, Any]] = []
        warnings: list[str] = []
        degraded = None
        if self.embedder is None:
            degraded = "keyword_only"
            warnings.append("Ollama embeddings are not configured; keyword-only retrieval is active. Result quality may be reduced on diverse/mixed-topic data.")
        else:
            try:
                query_embedding = self.embedder.embed(query)
                for chunk in self.store.list_chunks(filters):
                    embedding = json.loads(chunk.get("embedding_json") or "[]")
                    score = cosine(query_embedding, embedding)
                    if score > 0:
                        semantic.append({**chunk, "score": score})
                semantic.sort(key=lambda item: item["score"], reverse=True)
            except OllamaUnavailableError as exc:
                degraded = "keyword_only"
                warnings.append(str(exc))

        merged: dict[str, dict[str, Any]] = {}
        for rank, row in enumerate(keyword, start=1):
            merged[row["chunk_id"]] = {**row, "score": 1.0 / rank}
        for rank, row in enumerate(semantic[: limit * 2], start=1):
            if row["chunk_id"] in merged:
                merged[row["chunk_id"]]["score"] += row["score"]
            else:
                merged[row["chunk_id"]] = {**row, "score": row["score"] + 0.1 / rank}
        results = sorted(merged.values(), key=lambda item: item["score"], reverse=True)[:limit]
        return RetrievalResponse(results=results, degraded_mode=degraded, warnings=warnings)
