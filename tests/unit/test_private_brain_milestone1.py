from pathlib import Path

from packages.chat_normalization import ChatImportPipeline
from packages.chat_normalization.hashing import content_hash
from packages.common_models import NormalizedConversation, NormalizedMessage


ROOT = Path(__file__).parents[1]


def test_normalized_models_require_valid_roles() -> None:
    conversation = NormalizedConversation(
        conversation_id="conv_1",
        provider="generic_json",
        title="Synthetic",
        metadata={},
        content_hash="abc",
    )
    message = NormalizedMessage(
        message_id="msg_1",
        conversation_id=conversation.conversation_id,
        role="user",
        content="hello",
        position=1,
        metadata={},
        content_hash="def",
    )
    assert message.role == "user"


def test_generic_pipeline_imports_synthetic_fixture() -> None:
    pipeline = ChatImportPipeline()
    result = pipeline.import_path(ROOT / "fixtures" / "private_brain_generic.json")

    assert result.failures == []
    assert result.imported_conversations == 1
    assert result.imported_messages == 2
    assert result.sources[0].conversation.provider == "generic_json"
    assert result.sources[0].messages[0].metadata["metadata_key"] == "preserved"


def test_claude_pipeline_imports_observed_shape() -> None:
    pipeline = ChatImportPipeline()
    result = pipeline.import_path(ROOT / "fixtures" / "private_brain_claude.json", provider="claude")

    assert result.failures == []
    assert result.imported_conversations == 1
    assert result.imported_messages == 2
    assert result.sources[0].conversation.provider == "claude"
    assert result.sources[0].conversation.remote_id == "claude-conv-1"
    assert [message.role for message in result.sources[0].messages] == ["user", "assistant"]
    assert result.sources[0].messages[0].metadata["uuid"] == "cm-1"


def test_claude_real_export_format_sender_mapping() -> None:
    """Regression test: Claude real export uses 'sender': 'human', not 'role': 'user'."""
    pipeline = ChatImportPipeline()

    # Test with real Claude export format from fixtures
    result = pipeline.import_path(ROOT / "fixtures" / "claude_real_format.json", provider="claude")

    assert result.failures == []
    assert result.imported_conversations == 1
    assert result.imported_messages == 2

    # Verify sender="human" maps to role="user"
    assert result.sources[0].messages[0].role == "user"
    # Verify sender="assistant" stays as role="assistant"
    assert result.sources[0].messages[1].role == "assistant"

    # Verify content comes from top-level "text" field (not nested content blocks)
    assert "reinforcement learning" in result.sources[0].messages[0].content.lower()
    assert "simulator is stable" in result.sources[0].messages[1].content


def test_gemini_pipeline_imports_takeout_conversation_turns() -> None:
    pipeline = ChatImportPipeline()
    result = pipeline.import_path(ROOT / "fixtures" / "private_brain_gemini.txt", provider="gemini")

    assert result.failures == []
    assert result.imported_conversations == 1
    assert result.imported_messages == 3
    assert result.sources[0].conversation.provider == "gemini"
    assert result.sources[0].conversation.title == "klasor kac gb"
    assert [message.role for message in result.sources[0].messages] == ["user", "assistant", "user"]
    assert result.sources[0].messages[0].content == "klasor kac gb"
    assert result.sources[0].messages[1].content == "Depolama kotasi bilgisine erisimim bulunmamaktadir."
    assert result.sources[0].messages[2].metadata["turn_index"] == 2


def test_auto_detects_gemini_text_export() -> None:
    result = ChatImportPipeline().import_path(ROOT / "fixtures" / "private_brain_gemini.txt", provider="auto")

    assert result.failures == []
    assert result.sources[0].conversation.provider == "gemini"


def test_generic_pipeline_detects_duplicates() -> None:
    pipeline = ChatImportPipeline()
    path = ROOT / "fixtures" / "private_brain_generic.json"

    first = pipeline.import_path(path)
    second = pipeline.import_path(path)

    assert first.imported_conversations == 1
    assert second.imported_conversations == 0
    assert second.skipped_duplicates == 1


def test_malformed_input_fails_closed() -> None:
    result = ChatImportPipeline().import_path(ROOT / "fixtures" / "private_brain_malformed.json")

    assert result.imported_conversations == 0
    assert result.failures


def test_content_hash_is_deterministic() -> None:
    left = content_hash({"b": 2, "a": 1})
    right = content_hash({"a": 1, "b": 2})

    assert left == right
