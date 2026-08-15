from __future__ import annotations

from packages.privacy_detection.models import RecommendedAction, Sensitivity

POLICY_VERSION = "privacy-detection-v1"


def sensitivity_for(entity_type: str) -> Sensitivity:
    credential_types = {
        "api_key",
        "access_token_url",
        "jwt",
        "private_key",
        "password",
        "recovery_code",
    }
    sensitive_types = {"credit_card", "national_id", "account_number"}
    personal_types = {"email", "phone", "person", "username", "ip_address", "location"}
    confidential_types = {"organization", "project", "product"}
    if entity_type in credential_types:
        return "credential"
    if entity_type in sensitive_types:
        return "sensitive_personal"
    if entity_type in personal_types:
        return "personal"
    if entity_type in confidential_types:
        return "company_confidential"
    return "unknown"


def action_for(entity_type: str, sensitivity: Sensitivity) -> RecommendedAction:
    if sensitivity == "credential":
        return "remove"
    if sensitivity == "sensitive_personal":
        return "quarantine"
    if sensitivity in {"personal", "company_confidential"}:
        return "pseudonymize"
    if sensitivity == "unknown":
        return "review"
    return "retain"
