from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from packages.vault_crypto.store import VaultStore

RevealMode = Literal["sanitized", "partial", "full"]


class RevealRequest(BaseModel):
    sanitized_answer: str
    approved: bool = False
    mode: RevealMode = "sanitized"
    reveal_types: list[str] = Field(default_factory=list)
    selected_tokens: list[str] = Field(default_factory=list)


class RevealResponse(BaseModel):
    revealed_answer: str
    resolved_tokens: list[str]
    unresolved_tokens: list[str]
    persisted: bool = False


TOKEN_RE = re.compile(r"<[A-Z][A-Z0-9_]*_[A-F0-9]{10}>")


class RevealDeniedError(PermissionError):
    pass


class RevealGateway:
    def __init__(self, vault_store: VaultStore):
        self.vault_store = vault_store

    def reveal(self, request: RevealRequest) -> RevealResponse:
        if request.mode == "sanitized":
            return RevealResponse(revealed_answer=request.sanitized_answer, resolved_tokens=[], unresolved_tokens=[])
        if not request.approved:
            raise RevealDeniedError("Explicit user approval is required before reveal")

        tokens_in_answer = sorted(set(TOKEN_RE.findall(request.sanitized_answer)))
        selected = set(request.selected_tokens) & set(tokens_in_answer) if request.selected_tokens else set(tokens_in_answer)
        reveal_types = {item.lower() for item in request.reveal_types}
        resolved: list[str] = []
        unresolved: list[str] = []
        output = request.sanitized_answer

        for token in tokens_in_answer:
            if token not in selected:
                continue
            entity_type = self.vault_store.entity_type_for_token(token)
            if request.mode == "partial" and reveal_types and (entity_type or "").lower() not in reveal_types:
                continue
            original = self.vault_store.resolve_token(token)
            if original is None:
                unresolved.append(token)
                continue
            output = output.replace(token, original)
            resolved.append(token)

        self.vault_store.append_audit_event(
            "answer_revealed",
            None,
            {"resolved_count": len(resolved), "unresolved_count": len(unresolved), "mode": request.mode},
        )
        return RevealResponse(revealed_answer=output, resolved_tokens=resolved, unresolved_tokens=unresolved)
