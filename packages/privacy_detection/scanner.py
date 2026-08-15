from __future__ import annotations

from packages.common_models import NormalizedMessage
from packages.privacy_detection.detectors import pattern_findings
from packages.privacy_detection.interfaces import ContextClassifier, LocalNERProvider
from packages.privacy_detection.local_adapters import (
    DeterministicContextClassifier,
    DeterministicPlaceholderNER,
)
from packages.privacy_detection.models import PrivacyFinding


class PrivacyScanner:
    def __init__(
        self,
        ner_provider: LocalNERProvider | None = None,
        classifier: ContextClassifier | None = None,
    ):
        self.ner_provider = ner_provider or DeterministicPlaceholderNER()
        self.classifier = classifier or DeterministicContextClassifier()

    def scan_message(self, message: NormalizedMessage) -> list[PrivacyFinding]:
        findings = [
            *pattern_findings(message.message_id, message.content),
            *self.ner_provider.find_entities(message.message_id, message.content),
        ]
        return resolve_overlaps(findings)

    def scan_messages(self, messages: list[NormalizedMessage]) -> list[PrivacyFinding]:
        findings: list[PrivacyFinding] = []
        for message in messages:
            findings.extend(self.scan_message(message))
        return findings


def resolve_overlaps(findings: list[PrivacyFinding]) -> list[PrivacyFinding]:
    ranked = sorted(
        findings,
        key=lambda item: (
            item.start_index,
            -(item.end_index - item.start_index),
            -item.confidence,
            item.entity_type,
        ),
    )
    accepted: list[PrivacyFinding] = []
    occupied: list[tuple[int, int]] = []
    for finding in ranked:
        if any(finding.start_index < end and finding.end_index > start for start, end in occupied):
            continue
        accepted.append(finding)
        occupied.append((finding.start_index, finding.end_index))
    return sorted(accepted, key=lambda item: (item.message_id, item.start_index, item.end_index))
