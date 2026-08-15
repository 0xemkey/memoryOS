from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from packages.chat_normalization.hashing import content_hash, stable_id


class SanitizedConversation(BaseModel):
    conversation_id: str
    provider: str
    remote_id: str | None = None
    sanitized_title: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    source_file_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    content_hash: str


class SanitizedMessage(BaseModel):
    message_id: str
    conversation_id: str
    role: str
    sanitized_content: str
    position: int
    privacy_level: str
    detected_categories: list[str] = Field(default_factory=list)
    privacy_actions: list[str] = Field(default_factory=list)
    token_references: list[str] = Field(default_factory=list)
    original_content_reference: str | None = None
    created_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    content_hash: str


class SanitizedEntity(BaseModel):
    token: str
    entity_type: str
    first_seen_message_id: str


class SanitizedImportPackage(BaseModel):
    package_id: str
    sanitized_conversations: list[SanitizedConversation]
    sanitized_messages: list[SanitizedMessage]
    sanitized_entities: list[SanitizedEntity] = Field(default_factory=list)
    privacy_statistics: dict[str, int] = Field(default_factory=dict)
    policy_version: str
    schema_version: str = "sanitized-package-v1"
    package_hash: str

    @classmethod
    def build(
        cls,
        *,
        conversations: list[SanitizedConversation],
        messages: list[SanitizedMessage],
        entities: list[SanitizedEntity],
        privacy_statistics: dict[str, int],
        policy_version: str,
    ) -> "SanitizedImportPackage":
        payload = {
            "conversations": [item.model_dump(mode="json") for item in conversations],
            "messages": [item.model_dump(mode="json") for item in messages],
            "entities": [item.model_dump(mode="json") for item in entities],
            "privacy_statistics": privacy_statistics,
            "policy_version": policy_version,
            "schema_version": "sanitized-package-v1",
        }
        package_hash = content_hash(payload)
        return cls(
            package_id=stable_id("pkg", package_hash),
            sanitized_conversations=conversations,
            sanitized_messages=messages,
            sanitized_entities=entities,
            privacy_statistics=privacy_statistics,
            policy_version=policy_version,
            package_hash=package_hash,
        )

    @model_validator(mode="after")
    def validate_package_hash(self) -> "SanitizedImportPackage":
        payload = {
            "conversations": [item.model_dump(mode="json") for item in self.sanitized_conversations],
            "messages": [item.model_dump(mode="json") for item in self.sanitized_messages],
            "entities": [item.model_dump(mode="json") for item in self.sanitized_entities],
            "privacy_statistics": self.privacy_statistics,
            "policy_version": self.policy_version,
            "schema_version": self.schema_version,
        }
        expected = content_hash(payload)
        if self.package_hash != expected:
            raise ValueError("sanitized package hash mismatch")
        return self
