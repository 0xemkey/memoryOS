from __future__ import annotations

import re

from packages.chat_normalization.hashing import stable_id
from packages.privacy_detection.interfaces import ContextClassifier, LocalNERProvider
from packages.privacy_detection.models import PrivacyFinding
from packages.privacy_detection.policy import POLICY_VERSION, action_for, sensitivity_for


class DeterministicPlaceholderNER(LocalNERProvider):
    """Local placeholder NER with conservative, explainable patterns."""

    entity_patterns = {
        "project": re.compile(r"\b(?:Project|Proje)\s+[A-ZÇĞİÖŞÜ][\wÇĞİÖŞÜçğıöşü-]+\b"),
        "organization": re.compile(r"\b[A-ZÇĞİÖŞÜ][\wÇĞİÖŞÜçğıöşü-]+\s+(?:Inc|Ltd|AŞ|AS|Corp|Company)\b"),
        "username": re.compile(r"(?<!\w)@[A-Za-z0-9_]{3,32}\b"),
    }

    def find_entities(self, message_id: str, text: str) -> list[PrivacyFinding]:
        findings: list[PrivacyFinding] = []
        for entity_type, pattern in self.entity_patterns.items():
            for match in pattern.finditer(text):
                sensitivity = sensitivity_for(entity_type)
                findings.append(
                    PrivacyFinding(
                        finding_id=stable_id("finding", [message_id, match.start(), match.end(), entity_type]),
                        message_id=message_id,
                        start_index=match.start(),
                        end_index=match.end(),
                        original_text=match.group(0),
                        entity_type=entity_type,
                        sensitivity=sensitivity,
                        confidence=0.65,
                        recommended_action=action_for(entity_type, sensitivity),
                        detector="placeholder_ner",
                        policy_version=POLICY_VERSION,
                    )
                )
        return findings


class DeterministicContextClassifier(ContextClassifier):
    def classify(self, text: str) -> str:
        lowered = text.lower()
        if any(word in lowered for word in ("password", "api key", "token", "şifre", "sifre")):
            return "credential"
        if any(word in lowered for word in ("medical", "diagnosis", "finance", "salary", "maaş")):
            return "sensitive_personal"
        if any(word in lowered for word in ("company confidential", "internal project", "gizli proje")):
            return "company_confidential"
        return "unknown"
