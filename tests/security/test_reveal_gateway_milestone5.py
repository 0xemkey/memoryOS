from __future__ import annotations

from pathlib import Path

import pytest

from packages.vault_crypto import RevealGateway, RevealRequest, StaticKeyProvider, VaultStore
from packages.vault_crypto.reveal import RevealDeniedError


KEY = b"d" * 32


def store(tmp_path: Path) -> VaultStore:
    return VaultStore(tmp_path / "vault.sqlite3", StaticKeyProvider(KEY))


def test_reveal_requires_approval(tmp_path: Path) -> None:
    vault = store(tmp_path)
    token = vault.upsert_entity("person", "Mehmet")

    with pytest.raises(RevealDeniedError):
        RevealGateway(vault).reveal(RevealRequest(sanitized_answer=f"{token} approved it", mode="full"))


def test_full_reveal_resolves_only_tokens_present_in_answer(tmp_path: Path) -> None:
    vault = store(tmp_path)
    present = vault.upsert_entity("person", "Mehmet")
    absent = vault.upsert_entity("project", "Falcon")

    response = RevealGateway(vault).reveal(
        RevealRequest(sanitized_answer=f"{present} approved it", approved=True, mode="full")
    )

    assert response.revealed_answer == "Mehmet approved it"
    assert present in response.resolved_tokens
    assert absent not in response.resolved_tokens


def test_partial_reveal_by_entity_type(tmp_path: Path) -> None:
    vault = store(tmp_path)
    person = vault.upsert_entity("person", "Mehmet")
    project = vault.upsert_entity("project", "Falcon")

    response = RevealGateway(vault).reveal(
        RevealRequest(
            sanitized_answer=f"{person} works on {project}",
            approved=True,
            mode="partial",
            reveal_types=["person"],
        )
    )

    assert response.revealed_answer == f"Mehmet works on {project}"
    assert response.resolved_tokens == [person]


def test_unknown_token_remains_unresolved(tmp_path: Path) -> None:
    vault = store(tmp_path)
    response = RevealGateway(vault).reveal(
        RevealRequest(sanitized_answer="<PERSON_ABCDEF1234> did it", approved=True, mode="full")
    )

    assert response.revealed_answer == "<PERSON_ABCDEF1234> did it"
    assert response.unresolved_tokens == ["<PERSON_ABCDEF1234>"]


def test_revealed_answer_is_not_persisted_and_audit_is_safe(tmp_path: Path) -> None:
    vault = store(tmp_path)
    token = vault.upsert_entity("person", "Mehmet")
    response = RevealGateway(vault).reveal(
        RevealRequest(sanitized_answer=f"{token} did it", approved=True, mode="full")
    )

    assert response.persisted is False
    db_bytes = vault.raw_database_bytes()
    assert b"Mehmet did it" not in db_bytes
    events = vault.audit_events()
    assert events
    assert "Mehmet" not in str(events)


def test_review_workflow(tmp_path: Path) -> None:
    vault = store(tmp_path)
    item = vault.create_review_item(
        message_ref="vault://messages/msg_1",
        entity_type="person",
        recommended_action="pseudonymize",
        confidence=0.8,
    )

    assert item.status == "pending"
    approved = vault.update_review_item(item.review_item_id, status="approved")
    changed = vault.update_review_item(item.review_item_id, status="changed", action="remove")
    rejected = vault.update_review_item(item.review_item_id, status="rejected")

    assert approved is not None
    assert changed is not None and changed.recommended_action == "remove"
    assert rejected is not None and rejected.status == "rejected"
