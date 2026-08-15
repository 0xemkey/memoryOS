from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RecommendedAction = Literal["retain", "pseudonymize", "quarantine", "remove", "review"]
Sensitivity = Literal["public", "personal", "sensitive_personal", "company_confidential", "credential", "unknown"]


class PrivacyFinding(BaseModel):
    finding_id: str
    message_id: str
    start_index: int = Field(ge=0)
    end_index: int = Field(ge=0)
    original_text: str
    entity_type: str
    sensitivity: Sensitivity
    confidence: float = Field(ge=0.0, le=1.0)
    recommended_action: RecommendedAction
    detector: str
    policy_version: str
