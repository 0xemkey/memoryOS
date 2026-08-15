from __future__ import annotations

import re

from packages.chat_normalization.hashing import content_hash, stable_id
from packages.sanitized_storage.models import SanitizedImportPackage, SanitizedMessage


def count_tokens(text: str) -> int:
    return len(re.findall(r"\S+", text))


def render_message(message: SanitizedMessage) -> str:
    return f"{message.role}: {message.sanitized_content}"


class SanitizedChunker:
    def __init__(self, target_min_tokens: int = 80, hard_max_tokens: int = 900):
        self.target_min_tokens = target_min_tokens
        self.hard_max_tokens = hard_max_tokens

    def _split_oversized_message(self, message: SanitizedMessage) -> list[SanitizedMessage]:
        """Split an oversized message into multiple SanitizedMessage objects, each under hard_max_tokens.

        Returns list of message objects with the same message_id but truncated sanitized_content.
        If message fits, returns [message] (no split).
        """
        # Check if message (with role prefix) exceeds hard max
        rendered = render_message(message)
        token_count = count_tokens(rendered)

        if token_count <= self.hard_max_tokens:
            return [message]

        # Message exceeds limit - need to split it
        # Strategy: split by words, ensuring each part (with role prefix) stays under limit
        content = message.sanitized_content
        words = content.split()

        if not words:
            return [message]

        # Build parts, tracking rendered token count (role: + content)
        parts = []
        current_part = []
        current_tokens = count_tokens(f"{message.role}: ")  # Prefix tokens

        for word in words:
            word_tokens = count_tokens(word) + 1  # +1 for the space between words
            if current_tokens + word_tokens > self.hard_max_tokens and current_part:
                # Current part is full, flush it
                part_content = " ".join(current_part)
                parts.append(part_content)
                current_part = [word]
                current_tokens = count_tokens(f"{message.role}: ") + count_tokens(word)
            else:
                current_part.append(word)
                current_tokens += word_tokens

        if current_part:
            parts.append(" ".join(current_part))

        # Create new message objects for each part, preserving metadata and message_id
        result = []
        for part_content in parts:
            result.append(
                message.model_copy(update={"sanitized_content": part_content})
            )

        return result

    def chunk_package(self, package: SanitizedImportPackage) -> list[dict]:
        chunks: list[dict] = []
        by_conversation: dict[str, list[SanitizedMessage]] = {}
        for message in package.sanitized_messages:
            by_conversation.setdefault(message.conversation_id, []).append(message)
        titles = {conversation.conversation_id: conversation.sanitized_title for conversation in package.sanitized_conversations}
        providers = {conversation.conversation_id: conversation.provider for conversation in package.sanitized_conversations}

        for conversation_id, messages in by_conversation.items():
            ordered = sorted(messages, key=lambda item: item.position)

            # Normalize: split any oversized messages upfront
            normalized = []
            for message in ordered:
                normalized.extend(self._split_oversized_message(message))

            # Now apply standard chunking to normalized message list
            index = 0
            while index < len(normalized):
                selected = [normalized[index]]
                token_total = count_tokens(render_message(normalized[index]))
                index += 1

                # Try to pair user + assistant if both fit
                if (index < len(normalized) and selected[0].role == "user" and
                    normalized[index].role == "assistant"):
                    candidate_tokens = count_tokens(render_message(normalized[index]))
                    if token_total + candidate_tokens <= self.hard_max_tokens:
                        selected.append(normalized[index])
                        token_total += candidate_tokens
                        index += 1

                # Fill remaining capacity to reach target_min_tokens
                while index < len(normalized) and token_total < self.target_min_tokens:
                    candidate_tokens = count_tokens(render_message(normalized[index]))
                    if token_total + candidate_tokens > self.hard_max_tokens:
                        break
                    selected.append(normalized[index])
                    token_total += candidate_tokens
                    index += 1

                # Build chunk
                content = "\n\n".join(render_message(message) for message in selected)
                message_ids = [message.message_id for message in selected]
                chunk_hash = content_hash(
                    {
                        "conversation_id": conversation_id,
                        "message_ids": message_ids,
                        "content": content,
                    }
                )
                chunks.append(
                    {
                        "chunk_id": stable_id("schunk", chunk_hash),
                        "conversation_id": conversation_id,
                        "message_ids": message_ids,
                        "provider": providers[conversation_id],
                        "sanitized_title": titles[conversation_id],
                        "sanitized_content": content,
                        "privacy_level": max((message.privacy_level for message in selected), default="public"),
                        "token_references": sorted({token for message in selected for token in message.token_references}),
                        "created_at": selected[0].created_at.isoformat() if selected[0].created_at else None,
                        "content_hash": chunk_hash,
                        "token_count": token_total,
                    }
                )

        return chunks
