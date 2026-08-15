from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant", "tool"]
ImportStatus = Literal["running", "completed", "failed"]


class NormalizedConversation(BaseModel):
    conversation_id: str
    provider: str
    remote_id: str | None = None
    title: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    source_file: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    content_hash: str


class NormalizedMessage(BaseModel):
    message_id: str
    conversation_id: str
    role: Role
    content: str
    position: int
    created_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    content_hash: str


class NormalizedSource(BaseModel):
    conversation: NormalizedConversation
    messages: list[NormalizedMessage]
    source_fingerprint: str


class ImportWarning(BaseModel):
    code: str
    message: str
    source_ref: str | None = None


class ImportFailure(BaseModel):
    code: str
    message: str
    source_ref: str | None = None


class ImportJob(BaseModel):
    job_id: str
    source_path: str
    provider: str
    status: ImportStatus
    imported_conversations: int = 0
    imported_messages: int = 0
    skipped_duplicates: int = 0
    warnings: list[ImportWarning] = Field(default_factory=list)
    failures: list[ImportFailure] = Field(default_factory=list)
    created_at: datetime
    completed_at: datetime | None = None


class ImportResult(BaseModel):
    imported_conversations: int = 0
    imported_messages: int = 0
    skipped_duplicates: int = 0
    warnings: list[ImportWarning] = Field(default_factory=list)
    failures: list[ImportFailure] = Field(default_factory=list)
    sources: list[NormalizedSource] = Field(default_factory=list)
