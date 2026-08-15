from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from memoryos_core.embeddings.local import EmbeddingProvider, cosine
from memoryos_core.models import SearchResult
from memoryos_core.storage import SQLiteStore


class SearchFilters(BaseModel):
    provider: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    title: str | None = None
    role: str | None = None
    source_type: str | None = None
    recency_weight: bool = False


class HybridRetriever:
    def __init__(self, store: SQLiteStore, embedder: EmbeddingProvider):
        self.store = store
        self.embedder = embedder

    def search(self, query: str, filters: SearchFilters | None = None, limit: int = 10) -> list[SearchResult]:
        filters = filters or SearchFilters()
        filter_dict = filters.model_dump(exclude_none=True)
        keyword_rows = []
        try:
            keyword_rows = self.store.keyword_search(query, filter_dict, limit=limit * 2)
        except Exception:
            keyword_rows = []

        query_embedding = self.embedder.embed(query)
        semantic_rows = []
        for row in self.store.all_chunks():
            if not self._matches(row, filters):
                continue
            embedding = json.loads(row["embedding_json"] or "[]")
            score = cosine(query_embedding, embedding)
            if score > 0:
                item = dict(row)
                item["semantic_score"] = score
                semantic_rows.append(item)
        semantic_rows.sort(key=lambda row: row["semantic_score"], reverse=True)

        merged: dict[str, dict[str, Any]] = {}
        for rank, row in enumerate(keyword_rows, start=1):
            score = 1.0 / rank
            merged[row["chunk_id"]] = {**row, "score": score, "sources": {"keyword"}}
        for rank, row in enumerate(semantic_rows[: limit * 2], start=1):
            score = float(row.get("semantic_score", 0)) + (0.2 / rank)
            existing = merged.get(row["chunk_id"])
            if existing:
                existing["score"] += score
                existing["sources"].add("semantic")
            else:
                merged[row["chunk_id"]] = {**row, "score": score, "sources": {"semantic"}}

        results = list(merged.values())
        if filters.recency_weight:
            results = [self._apply_recency(row) for row in results]
        results.sort(key=lambda row: row["score"], reverse=True)
        return [self._to_result(row) for row in results[:limit]]

    def _matches(self, row: dict[str, Any], filters: SearchFilters) -> bool:
        if filters.provider and row["provider"] != filters.provider:
            return False
        if filters.title and filters.title.lower() not in row["conversation_title"].lower():
            return False
        if filters.source_type and row["source_type"] != filters.source_type:
            return False
        if filters.role and filters.role not in json.loads(row["roles_json"]):
            return False
        if filters.date_from and row["created_at"] < filters.date_from:
            return False
        if filters.date_to and row["created_at"] > filters.date_to:
            return False
        return True

    def _apply_recency(self, row: dict[str, Any]) -> dict[str, Any]:
        age_days = max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(row["created_at"])).days)
        row["score"] += 1.0 / (1 + age_days / 30)
        return row

    def _to_result(self, row: dict[str, Any]) -> SearchResult:
        content = " ".join(row["content"].split())
        return SearchResult(
            chunk_id=row["chunk_id"],
            score=round(float(row["score"]), 4),
            provider=row["provider"],
            conversation_title=row["conversation_title"],
            conversation_id=row["conversation_id"],
            message_ids=json.loads(row["message_ids_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            snippet=content[:300],
            source_type=row["source_type"],
        )
