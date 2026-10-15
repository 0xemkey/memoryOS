from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from memoryos_core.retrieval import SearchFilters


class ImportRequest(BaseModel):
    path: str
    provider: str = "auto"


class ImportUploadRequest(BaseModel):
    filename: str
    content_base64: str
    provider: str = "auto"


class ImportResponse(BaseModel):
    job_id: str
    imported: int
    skipped: int
    duplicated: int
    failed: int
    errors: list[str]
    conversation_ids: list[str]
    stages: list[str] = []
    privacy_findings: int = 0
    sanitized_messages: int = 0
    quarantined_messages: int = 0
    chunks_indexed: int = 0


class SearchRequest(BaseModel):
    query: str
    filters: SearchFilters | None = None
    limit: int = 10


class SearchResponse(BaseModel):
    results: list[dict[str, Any]]
    retrieval_mode: str | None = None
    warnings: list[str] = []


class AskRequest(SearchRequest):
    pass


class AskResponse(BaseModel):
    answer: str
    citations: list[str]
    retrieved_context: list[dict[str, Any]]
    sanitized_answer: str | None = None
    evidence_sufficient: bool | None = None
    retrieval_mode: str | None = None
    reasoning_mode: str | None = None
    warnings: list[str] = []


class SettingsResponse(BaseModel):
    settings: dict[str, Any]
