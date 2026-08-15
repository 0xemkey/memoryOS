from __future__ import annotations

from collections import Counter

from packages.chat_normalization.hashing import content_hash
from packages.common_models import NormalizedSource
from packages.privacy_detection import PrivacyFinding, PrivacyScanner
from packages.privacy_detection.policy import POLICY_VERSION
from packages.sanitized_storage.models import (
    SanitizedConversation,
    SanitizedEntity,
    SanitizedImportPackage,
    SanitizedMessage,
)
from packages.vault_crypto import VaultStore


class SanitizationError(RuntimeError):
    pass


class SanitizationService:
    def __init__(self, scanner: PrivacyScanner, vault_store: VaultStore):
        self.scanner = scanner
        self.vault_store = vault_store

    def sanitize_source(self, source: NormalizedSource) -> SanitizedImportPackage:
        sanitized_messages: list[SanitizedMessage] = []
        entities_by_token: dict[str, SanitizedEntity] = {}
        stats: Counter[str] = Counter()

        for message in source.messages:
            findings = self.scanner.scan_message(message)
            stats["findings"] += len(findings)
            if any(finding.recommended_action in {"quarantine", "review"} for finding in findings):
                stats["quarantined_messages"] += 1
                continue
            sanitized_text, tokens = self._apply_findings(message.content, findings, message.message_id)
            second_pass = self.scanner.scan_message(message.model_copy(update={"content": sanitized_text}))
            high_risk = [
                finding
                for finding in second_pass
                if finding.recommended_action in {"remove", "quarantine"}
            ]
            if high_risk:
                stats["blocked_second_pass"] += 1
                continue
            for finding, token in tokens:
                entities_by_token.setdefault(
                    token,
                    SanitizedEntity(
                        token=token,
                        entity_type=finding.entity_type,
                        first_seen_message_id=message.message_id,
                    ),
                )
            stats["sanitized_messages"] += 1
            sanitized_messages.append(
                SanitizedMessage(
                    message_id=message.message_id,
                    conversation_id=message.conversation_id,
                    role=message.role,
                    sanitized_content=sanitized_text,
                    position=message.position,
                    privacy_level=self._privacy_level(findings),
                    detected_categories=sorted({finding.entity_type for finding in findings}),
                    privacy_actions=sorted({finding.recommended_action for finding in findings}),
                    token_references=[token for _, token in tokens],
                    original_content_reference=f"vault://messages/{message.message_id}",
                    created_at=message.created_at,
                    metadata={"source_fingerprint": source.source_fingerprint},
                    content_hash=content_hash(
                        {
                            "message_id": message.message_id,
                            "sanitized_content": sanitized_text,
                        }
                    ),
                )
            )

        conversation = SanitizedConversation(
            conversation_id=source.conversation.conversation_id,
            provider=source.conversation.provider,
            remote_id=source.conversation.remote_id,
            sanitized_title=source.conversation.title,
            created_at=source.conversation.created_at,
            updated_at=source.conversation.updated_at,
            source_file_ref=f"source://{source.source_fingerprint}",
            metadata={"source_fingerprint": source.source_fingerprint},
            content_hash=content_hash(
                {
                    "conversation_id": source.conversation.conversation_id,
                    "messages": [message.content_hash for message in sanitized_messages],
                }
            ),
        )
        return SanitizedImportPackage.build(
            conversations=[conversation] if sanitized_messages else [],
            messages=sanitized_messages,
            entities=list(entities_by_token.values()),
            privacy_statistics=dict(stats),
            policy_version=POLICY_VERSION,
        )

    def _apply_findings(
        self,
        text: str,
        findings: list[PrivacyFinding],
        message_id: str,
    ) -> tuple[str, list[tuple[PrivacyFinding, str]]]:
        output = text
        tokens: list[tuple[PrivacyFinding, str]] = []
        for finding in sorted(findings, key=lambda item: item.start_index, reverse=True):
            if finding.recommended_action == "retain":
                continue
            if finding.recommended_action == "remove":
                replacement = f"[REMOVED_{finding.entity_type.upper()}]"
            elif finding.recommended_action == "pseudonymize":
                try:
                    replacement = self.vault_store.upsert_entity(finding.entity_type, finding.original_text)
                except Exception as exc:
                    raise SanitizationError(f"Failed to pseudonymize finding for {message_id}") from exc
                tokens.append((finding, replacement))
            else:
                continue
            output = output[: finding.start_index] + replacement + output[finding.end_index :]
        return output, [item for item in reversed(tokens)]

    def _privacy_level(self, findings: list[PrivacyFinding]) -> str:
        if any(finding.sensitivity == "credential" for finding in findings):
            return "credential_removed"
        if any(finding.sensitivity == "company_confidential" for finding in findings):
            return "company_confidential"
        if any(finding.sensitivity == "personal" for finding in findings):
            return "personal"
        return "public"
