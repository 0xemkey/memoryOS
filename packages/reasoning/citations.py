from __future__ import annotations

import re

CITATION_RE = re.compile(r"\[source:([A-Za-z0-9_-]+)\]", re.IGNORECASE)


def extract_citation_ids(text: str) -> list[str]:
    return list(dict.fromkeys(match.group(1) for match in CITATION_RE.finditer(text)))


def validate_citations(text: str, allowed_ids: set[str]) -> tuple[str, list[str], list[str]]:
    citation_ids = extract_citation_ids(text)
    invalid = [citation_id for citation_id in citation_ids if citation_id not in allowed_ids]
    cleaned = text
    for citation_id in invalid:
        cleaned = re.sub(rf"\[source:{re.escape(citation_id)}\]", "", cleaned, flags=re.IGNORECASE)
    valid = [citation_id for citation_id in citation_ids if citation_id in allowed_ids]
    return cleaned.strip(), valid, invalid
