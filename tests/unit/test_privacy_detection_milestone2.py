from __future__ import annotations

from packages.common_models import NormalizedMessage
from packages.privacy_detection import PrivacyScanner
from packages.privacy_detection.detectors import luhn_valid, pattern_findings
from packages.privacy_detection.scanner import resolve_overlaps


def message(content: str, message_id: str = "msg_test") -> NormalizedMessage:
    return NormalizedMessage(
        message_id=message_id,
        conversation_id="conv_test",
        role="user",
        content=content,
        position=1,
        metadata={},
        content_hash="hash",
    )


def test_detects_email_phone_ip_and_secret_url_with_offsets() -> None:
    text = "Email me at mehmet@example.com or +90 555 123 45 67. Server is 192.168.1.2. URL https://x.test?a=1&token=secret."
    findings = PrivacyScanner().scan_message(message(text))
    by_type = {finding.entity_type: finding for finding in findings}

    assert {"email", "phone", "ip_address", "access_token_url"} <= set(by_type)
    email = by_type["email"]
    assert text[email.start_index : email.end_index] == "mehmet@example.com"
    assert by_type["access_token_url"].recommended_action == "remove"


def test_credentials_are_never_retain_by_default() -> None:
    text = "password: hunter22 and key sk_1234567890abcdefABCDEF"
    findings = PrivacyScanner().scan_message(message(text))
    credential_findings = [item for item in findings if item.sensitivity == "credential"]

    assert credential_findings
    assert all(item.recommended_action == "remove" for item in credential_findings)


def test_turkish_password_and_project_detection() -> None:
    text = "şifre: cokgizli123 ve Proje Falcon konuşuldu."
    findings = PrivacyScanner().scan_message(message(text))
    types = {finding.entity_type for finding in findings}

    assert "password" in types
    assert "project" in types


def test_person_detection_requires_clear_context() -> None:
    text = "Contact Mehmet about the sanitized import. The Falcon engine is unrelated."
    findings = PrivacyScanner().scan_message(message(text))
    by_type = {finding.entity_type: finding for finding in findings}

    assert by_type["person"].original_text == "Mehmet"
    assert "Falcon" not in {finding.original_text for finding in findings}


def test_credit_card_validation_controls_false_positive() -> None:
    assert luhn_valid("4111 1111 1111 1111")
    assert not luhn_valid("4111 1111 1111 1112")
    findings = pattern_findings("msg", "number 4111 1111 1111 1112 is not valid")
    assert all(finding.entity_type != "credit_card" for finding in findings)


def test_overlap_resolution_prefers_longer_span() -> None:
    text = "Use https://example.com?token=sk_1234567890abcdefABCDEF"
    findings = PrivacyScanner().scan_message(message(text))

    assert [finding.entity_type for finding in findings] == ["access_token_url"]


def test_finding_ids_and_policy_are_stable() -> None:
    msg = message("Contact a@example.com", "msg_stable")
    first = PrivacyScanner().scan_message(msg)
    second = PrivacyScanner().scan_message(msg)

    assert first[0].finding_id == second[0].finding_id
    assert first[0].policy_version == "privacy-detection-v1"


def test_scanner_uses_local_interfaces_without_network(monkeypatch) -> None:
    def fail_network(*args, **kwargs):
        raise AssertionError("network call attempted")

    monkeypatch.setattr("socket.create_connection", fail_network)
    findings = PrivacyScanner().scan_message(message("Email local@example.com"))

    assert findings[0].entity_type == "email"


def test_resolve_overlaps_is_deterministic() -> None:
    findings = pattern_findings("msg", "https://example.com?token=secretvalue")
    first = resolve_overlaps(findings)
    second = resolve_overlaps(list(reversed(findings)))

    assert [item.finding_id for item in first] == [item.finding_id for item in second]


def test_phone_detector_excludes_date_patterns_regression() -> None:
    text = "The event occurred on 2026-07-25T12:03:00+00:00 in our logs. Date formats like 25.07.2026 and 25-07-26 12-03 should not be detected as phone numbers."
    findings = PrivacyScanner().scan_message(message(text))
    phone_findings = [f for f in findings if f.entity_type == "phone"]

    assert not phone_findings, f"Date patterns were incorrectly detected as phones: {[f.original_text for f in phone_findings]}"


def test_phone_detector_still_detects_real_phone_numbers() -> None:
    text = "Call 555-867-5309 or +1-555-867-5309 or 1 (555) 867-5309"
    findings = PrivacyScanner().scan_message(message(text))
    phone_findings = [f for f in findings if f.entity_type == "phone"]

    assert len(phone_findings) >= 1, "Real phone numbers should be detected"
    assert any("555" in f.original_text for f in phone_findings), "Should detect area code pattern"
