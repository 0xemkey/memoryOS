from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from packages.chat_normalization.hashing import stable_id


class ReasoningAnswer(BaseModel):
    answer_id: str
    sanitized_answer: str
    citation_ids: list[str]
    evidence_sufficient: bool
    warnings: list[str] = Field(default_factory=list)
    model_metadata: dict[str, Any] = Field(default_factory=dict)
    retrieval_metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def build(
        cls,
        *,
        sanitized_answer: str,
        citation_ids: list[str],
        evidence_sufficient: bool,
        warnings: list[str] | None = None,
        model_metadata: dict[str, Any] | None = None,
        retrieval_metadata: dict[str, Any] | None = None,
    ) -> "ReasoningAnswer":
        return cls(
            answer_id=stable_id("answer", [sanitized_answer, citation_ids]),
            sanitized_answer=sanitized_answer,
            citation_ids=citation_ids,
            evidence_sufficient=evidence_sufficient,
            warnings=warnings or [],
            model_metadata=model_metadata or {},
            retrieval_metadata=retrieval_metadata or {},
        )
