from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant", "tool", "unknown"]
SourceType = Literal["conversation", "document"]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class NormalizedConversation(BaseModel):
    conversation_id: str = Field(default_factory=new_id)
    provider: str
    remote_id: str | None = None
    title: str
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)
    source_file: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    content_hash: str


class NormalizedMessage(BaseModel):
    message_id: str = Field(default_factory=new_id)
    conversation_id: str
    role: Role = "unknown"
    content: str
    created_at: datetime = Field(default_factory=now_utc)
    metadata: dict[str, Any] = Field(default_factory=dict)
    ordinal: int = 0
    content_hash: str


class ConversationBundle(BaseModel):
    conversation: NormalizedConversation
    messages: list[NormalizedMessage]


class Chunk(BaseModel):
    chunk_id: str = Field(default_factory=new_id)
    conversation_id: str
    provider: str
    conversation_title: str
    message_ids: list[str]
    roles: list[str]
    content: str
    created_at: datetime
    updated_at: datetime
    source_path: str | None = None
    source_type: SourceType = "conversation"
    content_hash: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResult(BaseModel):
    chunk_id: str
    score: float
    provider: str
    conversation_title: str
    conversation_id: str
    message_ids: list[str]
    created_at: datetime
    snippet: str
    source_type: SourceType


class Citation(BaseModel):
    provider: str
    conversation_title: str
    date: str
    message_id: str
    message_index: int | None = None

    def render(self) -> str:
        suffix = f"Message {self.message_index}" if self.message_index is not None else self.message_id
        return f"[Source: {self.provider} | {self.conversation_title} | {self.date} | {suffix}]"
