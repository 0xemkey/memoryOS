from __future__ import annotations

from memoryos_core.models import Citation, SearchResult


def citation_for_result(result: SearchResult, message_index: int | None = None) -> Citation:
    return Citation(
        provider=result.provider,
        conversation_title=result.conversation_title,
        date=result.created_at.date().isoformat(),
        message_id=result.message_ids[0] if result.message_ids else result.chunk_id,
        message_index=message_index,
    )
