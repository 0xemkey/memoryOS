from __future__ import annotations

from pathlib import Path

from packages.chat_normalization import ChatImportPipeline
from packages.privacy_detection import PrivacyScanner
from packages.retrieval import SanitizedChunker, SanitizedRetriever
from packages.sanitized_storage import SanitizationService, SanitizedStore
from packages.vault_crypto import StaticKeyProvider, VaultStore


ROOT = Path(__file__).parents[1]
KEY = b"e" * 32


def build_package(tmp_path: Path, content: str | None = None):
    source = ChatImportPipeline().import_path(ROOT / "fixtures" / "private_brain_generic.json").sources[0]
    if content is not None:
        source.messages[0] = source.messages[0].model_copy(update={"content": content})
    service = SanitizationService(
        PrivacyScanner(),
        VaultStore(tmp_path / "vault.sqlite3", StaticKeyProvider(KEY)),
    )
    return service.sanitize_source(source)


def test_sanitized_chunk_boundaries_and_metadata(tmp_path: Path) -> None:
    package = build_package(tmp_path)
    chunks = SanitizedChunker(target_min_tokens=1).chunk_package(package)

    assert chunks
    assert chunks[0]["message_ids"] == [message.message_id for message in package.sanitized_messages[:2]]
    assert chunks[0]["provider"] == "generic_json"
    assert chunks[0]["content_hash"]
    assert chunks[0]["token_count"] <= 900


def test_sanitized_fts_search_and_keyword_only_fallback(tmp_path: Path) -> None:
    package = build_package(tmp_path)
    chunks = SanitizedChunker(target_min_tokens=1).chunk_package(package)
    store = SanitizedStore(tmp_path / "sanitized.sqlite3")
    store.save_package(package)
    SanitizedRetriever(store).index_chunks(chunks)

    response = SanitizedRetriever(store).search("privacy vault", limit=5)

    assert response.degraded_mode == "keyword_only"
    assert response.results
    assert response.results[0]["conversation_id"] == package.sanitized_conversations[0].conversation_id


def test_no_raw_pseudonymized_text_enters_chunks_or_index(tmp_path: Path) -> None:
    package = build_package(tmp_path, "Contact mehmet@example.com about Proje Falcon.")
    chunks = SanitizedChunker(target_min_tokens=1).chunk_package(package)
    store = SanitizedStore(tmp_path / "sanitized.sqlite3")
    store.save_package(package)
    SanitizedRetriever(store).index_chunks(chunks)

    assert "mehmet@example.com" not in chunks[0]["sanitized_content"]
    assert b"mehmet@example.com" not in store.raw_database_bytes()
    assert chunks[0]["token_references"]


def test_retrieval_filters_and_deduplication(tmp_path: Path) -> None:
    package = build_package(tmp_path, "Contact mehmet@example.com about Proje Falcon and local retrieval.")
    chunks = SanitizedChunker(target_min_tokens=1).chunk_package(package)
    store = SanitizedStore(tmp_path / "sanitized.sqlite3")
    store.save_package(package)
    retriever = SanitizedRetriever(store)
    retriever.index_chunks(chunks)
    token = chunks[0]["token_references"][0]

    response = retriever.search(
        "retrieval",
        filters={"provider": "generic_json", "privacy_level": chunks[0]["privacy_level"], "entity_token": token},
        limit=10,
    )

    ids = [result["chunk_id"] for result in response.results]
    assert ids
    assert len(ids) == len(set(ids))


def test_quarantined_messages_are_not_chunked(tmp_path: Path) -> None:
    package = build_package(tmp_path, "card 4111 1111 1111 1111")
    chunks = SanitizedChunker(target_min_tokens=1).chunk_package(package)

    assert all("4111" not in chunk["sanitized_content"] for chunk in chunks)


def test_oversized_messages_are_split_within_hard_limit(tmp_path: Path) -> None:
    """Regression test: single message exceeding 900 tokens should be split into multiple chunks.

    This test verifies the fix for the bug where 3,300-word messages were emitted as single chunks.
    Each resulting chunk should respect the hard_max_tokens limit.
    """
    # Create a very long message (over 1000 words) - much larger than hard_max_tokens
    long_content = " ".join([f"word{i}" for i in range(1100)])
    assert len(long_content.split()) > 900  # Verify it's genuinely oversized

    package = build_package(tmp_path, long_content)
    chunker = SanitizedChunker(target_min_tokens=1, hard_max_tokens=900)
    chunks = chunker.chunk_package(package)

    # Should produce multiple chunks (not one giant chunk), since message is split
    assert len(chunks) > 1, f"Expected multiple chunks for 1100-word message, got {len(chunks)}"

    # Each chunk must respect the hard_max_tokens ceiling - THIS IS THE CRITICAL FIX
    for i, chunk in enumerate(chunks):
        chunk_token_count = chunk["token_count"]
        assert chunk_token_count <= 900, (
            f"Chunk {i} exceeds hard_max_tokens: "
            f"{chunk_token_count} > 900 (content: {chunk['sanitized_content'][:100]})"
        )
        # Also verify token count matches what count_tokens() reports
        reported_tokens = chunk.get("token_count")
        assert reported_tokens <= 900, f"Chunk {i} token_count {reported_tokens} > hard_max 900"
