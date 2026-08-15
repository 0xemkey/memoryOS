from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import Callable

from packages.chat_normalization.hashing import stable_id
from packages.privacy_detection.models import PrivacyFinding
from packages.privacy_detection.policy import POLICY_VERSION, action_for, sensitivity_for


@dataclass(frozen=True)
class PatternSpec:
    entity_type: str
    pattern: re.Pattern[str]
    confidence: float
    validator: Callable[[str], bool] | None = None


def luhn_valid(value: str) -> bool:
    digits = [int(char) for char in re.sub(r"\D", "", value)]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def valid_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def valid_secret_url(value: str) -> bool:
    lowered = value.lower()
    return any(key in lowered for key in ("token=", "access_token=", "api_key=", "apikey=", "secret="))


PATTERNS = [
    PatternSpec("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL), 0.99),
    PatternSpec("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"), 0.98),
    PatternSpec("access_token_url", re.compile(r"https?://[^\s]+", re.IGNORECASE), 0.95, valid_secret_url),
    PatternSpec("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), 0.96),
    PatternSpec("api_key", re.compile(r"\b(?:sk|pk|ghp|xoxb|AKIA)[A-Za-z0-9_-]{16,}\b"), 0.95),
    PatternSpec("password", re.compile(r"(?i)\b(?:password|passwd|pwd|şifre|sifre)\s*[:=]\s*([^\s,;]{6,})"), 0.9),
    PatternSpec("recovery_code", re.compile(r"(?i)\b(?:recovery code|backup code|kurtarma kodu)\s*[:=]?\s*([A-Z0-9-]{8,})\b"), 0.88),
    # Phone pattern with date-exclusion validator to prevent false positives on timestamps/dates.
    # Validator excludes patterns matching: YYYY-MM-DD, DD.MM.YYYY, DD-MM-YY, YYYY.MM.DD (with optional time HH:MM or HH-MM).
    # Known limitation: does NOT exclude US-style dates (MM/DD/YYYY) or written-month dates (25 Jul 2026) - these may still false-positive.
    PatternSpec("phone", re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)"), 0.82, lambda v: not re.match(r"^\d{1,4}[\s.-]\d{1,2}[\s.-]\d{1,4}(\s\d{1,2}[:-]?\d{1,2})?$", v)),
    PatternSpec(
        "person",
        re.compile(
            r"\b(?:Person|person|Name|name|Contact|contact|User|user|Kisi|kisi|Kişi|kişi|Adı|adı|Adi|adi|Ad|ad)\s*[:=]?\s+"
            r"([A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü'-]{1,40}(?:\s+[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü'-]{1,40}){0,2})\b"
        ),
        0.72,
    ),
    PatternSpec(
        "person",
        re.compile(r"\b([A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü'-]{1,40})\s+should\s+contact\b"),
        0.7,
    ),
    PatternSpec("ip_address", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), 0.9, valid_ip),
    PatternSpec("credit_card", re.compile(r"\b(?:\d[ -]?){13,19}\b"), 0.9, luhn_valid),
    PatternSpec("account_number", re.compile(r"(?i)\b(?:account|iban|hesap)\s*(?:no|number|numarası)?\s*[:=]?\s*([A-Z0-9]{10,34})\b"), 0.8),
    PatternSpec("national_id", re.compile(r"(?i)\b(?:tc|tckn|ssn|national id)\s*[:=]?\s*([0-9]{9,11})\b"), 0.78),
]


def pattern_findings(message_id: str, text: str) -> list[PrivacyFinding]:
    findings: list[PrivacyFinding] = []
    for spec in PATTERNS:
        for match in spec.pattern.finditer(text):
            remove_whole_match = spec.entity_type in {
                "password",
                "recovery_code",
                "account_number",
                "national_id",
            }
            original = match.group(0) if remove_whole_match else match.group(1) if match.groups() else match.group(0)
            start, end = match.span(0) if remove_whole_match else match.span(1) if match.groups() else match.span(0)
            if spec.validator and not spec.validator(original):
                continue
            sensitivity = sensitivity_for(spec.entity_type)
            findings.append(
                PrivacyFinding(
                    finding_id=stable_id("finding", [message_id, start, end, spec.entity_type, original]),
                    message_id=message_id,
                    start_index=start,
                    end_index=end,
                    original_text=original,
                    entity_type=spec.entity_type,
                    sensitivity=sensitivity,
                    confidence=spec.confidence,
                    recommended_action=action_for(spec.entity_type, sensitivity),
                    detector="pattern",
                    policy_version=POLICY_VERSION,
                )
            )
    return findings
