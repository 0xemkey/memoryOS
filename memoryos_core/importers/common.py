from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from memoryos_core.importers.base import ImporterError
from memoryos_core.models import ConversationBundle, NormalizedConversation, NormalizedMessage
from memoryos_core.util import coalesce_datetime, content_hash, parse_datetime, stable_id


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ImporterError(f"Invalid JSON in {path}: {exc}") from exc


def text_from_parts(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(filter(None, (text_from_parts(item) for item in value)))
    if isinstance(value, dict):
        if "text" in value:
            return text_from_parts(value["text"])
        if "content" in value:
            return text_from_parts(value["content"])
        if "parts" in value:
            return text_from_parts(value["parts"])
    return str(value)


def make_bundle(
    *,
    provider: str,
    title: str | None,
    source_file: Path,
    raw: Any,
    raw_messages: list[dict[str, Any]],
    remote_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ConversationBundle:
    if not raw_messages:
        raise ImporterError(f"No messages found in {source_file}")

    conv_hash = content_hash({"provider": provider, "remote_id": remote_id, "messages": raw_messages})
    conversation_id = stable_id("conv", {"provider": provider, "remote_id": remote_id, "hash": conv_hash})

    parsed_messages: list[NormalizedMessage] = []
    dates = []
    for index, raw_message in enumerate(raw_messages, start=1):
        content = text_from_parts(raw_message.get("content") or raw_message.get("text") or raw_message.get("parts"))
        if not content.strip():
            continue
        created_at = parse_datetime(
            raw_message.get("created_at")
            or raw_message.get("create_time")
            or raw_message.get("timestamp")
            or raw_message.get("date")
        )
        dates.append(created_at)
        role = str(raw_message.get("role") or raw_message.get("author") or "unknown").lower()
        if role not in {"system", "user", "assistant", "tool"}:
            role = "unknown"
        msg_hash = content_hash({"conversation": conversation_id, "ordinal": index, "role": role, "content": content})
        parsed_messages.append(
            NormalizedMessage(
                message_id=stable_id("msg", msg_hash),
                conversation_id=conversation_id,
                role=role,  # type: ignore[arg-type]
                content=content.strip(),
                created_at=coalesce_datetime(created_at),
                metadata={k: v for k, v in raw_message.items() if k not in {"content", "text", "parts"}},
                ordinal=index,
                content_hash=msg_hash,
            )
        )

    if not parsed_messages:
        raise ImporterError(f"No non-empty messages found in {source_file}")

    created_at = min(message.created_at for message in parsed_messages)
    updated_at = max(message.created_at for message in parsed_messages)
    conversation = NormalizedConversation(
        conversation_id=conversation_id,
        provider=provider,
        remote_id=remote_id,
        title=(title or "Untitled conversation").strip() or "Untitled conversation",
        created_at=created_at,
        updated_at=updated_at,
        source_file=str(source_file),
        metadata=metadata or {"raw_type": type(raw).__name__},
        content_hash=conv_hash,
    )
    return ConversationBundle(conversation=conversation, messages=parsed_messages)
