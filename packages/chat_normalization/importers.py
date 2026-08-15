from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from packages.chat_normalization.hashing import content_hash, stable_id
from packages.common_models import NormalizedConversation, NormalizedMessage, NormalizedSource


class ImporterError(ValueError):
    pass


class ChatImporter(ABC):
    provider: str

    @abstractmethod
    def parse(self, path: Path) -> list[NormalizedSource]:
        raise NotImplementedError


def parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        if value > 10_000_000_000:
            value = value / 1000
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ImporterError(f"Invalid JSON: {exc}") from exc


def coerce_role(value: Any) -> str:
    role = str(value or "").lower()
    if role == "human":
        role = "user"
    if role not in {"system", "user", "assistant", "tool"}:
        raise ImporterError(f"Unsupported message role: {value!r}")
    return role


def text_from_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(part for part in (text_from_value(item) for item in value) if part)
    if isinstance(value, dict):
        for key in ("text", "content", "parts", "data"):
            if key in value:
                return text_from_value(value[key])
    return str(value)


def make_source(
    *,
    provider: str,
    title: str | None,
    source_file: Path,
    raw_conversation: dict[str, Any],
    raw_messages: list[dict[str, Any]],
    remote_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> NormalizedSource:
    if not raw_messages:
        raise ImporterError("Conversation contains no messages")

    source_fingerprint = content_hash({"path": str(source_file), "payload": raw_conversation})
    normalized_payload = {"provider": provider, "remote_id": remote_id, "messages": raw_messages}
    conversation_hash = content_hash(normalized_payload)
    conversation_id = stable_id("conv", normalized_payload)
    messages: list[NormalizedMessage] = []
    warnings: list[str] = []

    for index, raw_message in enumerate(raw_messages, start=1):
        content = text_from_value(raw_message.get("content") or raw_message.get("text"))
        if not content.strip():
            raise ImporterError(f"Message {index} is empty")
        role = coerce_role(raw_message.get("role") or raw_message.get("sender"))
        message_hash = content_hash(
            {
                "conversation_id": conversation_id,
                "index": index,
                "role": role,
                "content": content,
            }
        )
        created_at = parse_datetime(
            raw_message.get("created_at") or raw_message.get("create_time") or raw_message.get("timestamp")
        )
        if created_at is None:
            warnings.append(f"Message {index} has no valid timestamp")
        messages.append(
            NormalizedMessage(
                message_id=stable_id("msg", message_hash),
                conversation_id=conversation_id,
                role=role,  # type: ignore[arg-type]
                content=content.strip(),
                position=index,
                created_at=created_at,
                metadata={
                    key: value
                    for key, value in raw_message.items()
                    if key not in {"role", "sender", "content", "text"}
                },
                content_hash=message_hash,
            )
        )

    created_dates = [message.created_at for message in messages if message.created_at is not None]
    conversation = NormalizedConversation(
        conversation_id=conversation_id,
        provider=provider,
        remote_id=remote_id,
        title=(title or "Untitled conversation").strip() or "Untitled conversation",
        created_at=min(created_dates) if created_dates else None,
        updated_at=max(created_dates) if created_dates else None,
        source_file=str(source_file),
        metadata={**(metadata or {}), "normalization_warnings": warnings},
        content_hash=conversation_hash,
    )
    return NormalizedSource(
        conversation=conversation,
        messages=messages,
        source_fingerprint=source_fingerprint,
    )


class GenericJsonImporter(ChatImporter):
    provider = "generic_json"

    def parse(self, path: Path) -> list[NormalizedSource]:
        raw = load_json(path)
        if isinstance(raw, dict) and "conversations" in raw:
            conversations = raw["conversations"]
        else:
            conversations = raw if isinstance(raw, list) else [raw]
        if not isinstance(conversations, list):
            raise ImporterError("Generic JSON must be an object, list, or contain conversations")

        sources: list[NormalizedSource] = []
        for index, item in enumerate(conversations, start=1):
            if not isinstance(item, dict):
                raise ImporterError(f"Conversation {index} is not an object")
            messages = item.get("messages")
            if not isinstance(messages, list):
                raise ImporterError(f"Conversation {index} does not contain a messages list")
            sources.append(
                make_source(
                    provider=str(item.get("provider") or self.provider),
                    title=item.get("title"),
                    source_file=path,
                    raw_conversation=item,
                    raw_messages=messages,
                    remote_id=item.get("conversation_id") or item.get("id"),
                    metadata={key: value for key, value in item.items() if key != "messages"},
                )
            )
        return sources


class ClaudeImporter(ChatImporter):
    provider = "claude"

    def parse(self, path: Path) -> list[NormalizedSource]:
        raw = load_json(path)
        conversations = raw if isinstance(raw, list) else raw.get("conversations") if isinstance(raw, dict) else None
        if conversations is None:
            conversations = [raw]
        if not isinstance(conversations, list):
            raise ImporterError("Claude export must be a conversation object or list")

        sources: list[NormalizedSource] = []
        warnings: list[str] = []
        for index, item in enumerate(conversations, start=1):
            if not isinstance(item, dict):
                raise ImporterError(f"Claude conversation {index} is not an object")
            messages = item["chat_messages"] if "chat_messages" in item else item.get("messages")
            if not isinstance(messages, list):
                raise ImporterError(f"Claude conversation {index} does not contain messages")
            if not messages:
                warnings.append(f"Claude conversation {index} has no messages and was skipped")
                continue
            raw_messages: list[dict[str, Any]] = []
            for message_index, message in enumerate(messages, start=1):
                if not isinstance(message, dict):
                    raise ImporterError(f"Claude conversation {index} message {message_index} is not an object")
                role = message.get("sender") or message.get("role")
                if role == "human":
                    role = "user"
                content = message.get("text") or message.get("content")
                raw_messages.append(
                    {
                        "role": role,
                        "content": content,
                        "created_at": message.get("created_at") or message.get("updated_at"),
                        "uuid": message.get("uuid"),
                        "attachments": message.get("attachments"),
                        "files": message.get("files"),
                        "parent_message_uuid": message.get("parent_message_uuid"),
                    }
                )
            source = make_source(
                provider=self.provider,
                title=item.get("name") or item.get("title"),
                source_file=path,
                raw_conversation=item,
                raw_messages=raw_messages,
                remote_id=item.get("uuid") or item.get("id"),
                metadata={
                    "source_format": "claude_export",
                    "account": item.get("account"),
                    "summary": item.get("summary"),
                    "normalization_warnings": warnings,
                },
            )
            sources.append(source)
        if not sources and warnings:
            raise ImporterError("; ".join(warnings))
        return sources


class MarkdownImporter(ChatImporter):
    provider = "markdown"

    def parse(self, path: Path) -> list[NormalizedSource]:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            raise ImporterError("Markdown file is empty")
        title = next((line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("#")), path.stem)
        return [
            make_source(
                provider=self.provider,
                title=title,
                source_file=path,
                raw_conversation={"title": title},
                raw_messages=[{"role": "user", "content": text}],
                remote_id=str(path.resolve()),
                metadata={"source_format": "markdown"},
            )
        ]


class PlainTextImporter(ChatImporter):
    provider = "plain_text"

    def parse(self, path: Path) -> list[NormalizedSource]:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            raise ImporterError("Plain-text file is empty")
        return [
            make_source(
                provider=self.provider,
                title=path.stem,
                source_file=path,
                raw_conversation={"title": path.stem},
                raw_messages=[{"role": "user", "content": text}],
                remote_id=str(path.resolve()),
                metadata={"source_format": "plain_text"},
            )
        ]
