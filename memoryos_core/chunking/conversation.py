from __future__ import annotations

from memoryos_core.models import Chunk, ConversationBundle, NormalizedMessage
from memoryos_core.util import content_hash, stable_id


def approx_tokens(text: str) -> int:
    return max(1, len(text.split()))


def render_message(message: NormalizedMessage) -> str:
    return f"{message.role}: {message.content}"


def chunk_conversation(bundle: ConversationBundle, min_tokens: int = 120, max_tokens: int = 800) -> list[Chunk]:
    messages = bundle.messages
    chunks: list[Chunk] = []
    index = 0
    while index < len(messages):
        selected: list[NormalizedMessage] = []
        token_count = 0
        if messages[index].role == "user":
            selected.append(messages[index])
            token_count += approx_tokens(messages[index].content)
            if index + 1 < len(messages) and messages[index + 1].role == "assistant":
                selected.append(messages[index + 1])
                token_count += approx_tokens(messages[index + 1].content)
                index += 2
            else:
                index += 1
        else:
            selected.append(messages[index])
            token_count += approx_tokens(messages[index].content)
            index += 1

        while index < len(messages) and token_count < min_tokens:
            next_message = messages[index]
            candidate_tokens = approx_tokens(next_message.content)
            if token_count + candidate_tokens > max_tokens and selected:
                break
            selected.append(next_message)
            token_count += candidate_tokens
            index += 1

        text = "\n\n".join(render_message(message) for message in selected)
        chunk_hash = content_hash(
            {
                "conversation_id": bundle.conversation.conversation_id,
                "message_ids": [m.message_id for m in selected],
                "content": text,
            }
        )
        chunks.append(
            Chunk(
                chunk_id=stable_id("chunk", chunk_hash),
                conversation_id=bundle.conversation.conversation_id,
                provider=bundle.conversation.provider,
                conversation_title=bundle.conversation.title,
                message_ids=[m.message_id for m in selected],
                roles=[m.role for m in selected],
                content=text,
                created_at=min(m.created_at for m in selected),
                updated_at=max(m.created_at for m in selected),
                source_path=bundle.conversation.source_file,
                content_hash=chunk_hash,
                metadata={"token_estimate": token_count},
            )
        )
    return chunks
