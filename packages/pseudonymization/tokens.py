from __future__ import annotations

import hmac
import re
from hashlib import sha256

TOKEN_ENTITY_TYPES = {
    "person": "PERSON",
    "organization": "ORG",
    "project": "PROJECT",
    "product": "PRODUCT",
    "email": "EMAIL",
    "phone": "PHONE",
    "username": "USERNAME",
    "location": "LOCATION",
    "ip_address": "IP",
    "account_number": "ACCOUNT",
    "credit_card": "CARD",
    "national_id": "ID",
}


def normalize_entity_value(entity_type: str, original_value: str) -> str:
    value = " ".join(original_value.strip().split())
    if entity_type in {"email", "username"}:
        return value.lower()
    if entity_type in {"phone", "credit_card", "account_number", "national_id"}:
        return re.sub(r"[\s().-]", "", value).upper()
    return value.casefold()


def create_pseudonym(key: bytes, entity_type: str, original_value: str) -> str:
    if not key:
        raise ValueError("pseudonym key is required")
    token_type = TOKEN_ENTITY_TYPES.get(entity_type, re.sub(r"[^A-Z0-9]", "_", entity_type.upper()))
    normalized = normalize_entity_value(entity_type, original_value)
    digest = hmac.new(key, f"{entity_type}:{normalized}".encode("utf-8"), sha256).hexdigest()
    return f"<{token_type}_{digest[:10].upper()}>"
