from pathlib import Path

from memoryos_core.importers.chatgpt import ChatGPTImporter
from memoryos_core.importers.claude import ClaudeImporter
from memoryos_core.importers.generic_json import GenericJsonImporter


ROOT = Path(__file__).parents[1]


def test_chatgpt_importer_normalizes_export() -> None:
    bundle = ChatGPTImporter().parse(ROOT / "sample_data" / "chatgpt_sample.json")[0]
    assert bundle.conversation.provider == "chatgpt"
    assert bundle.conversation.title == "Robot control project"
    assert [message.role for message in bundle.messages] == ["user", "assistant"]


def test_claude_importer_preserves_metadata() -> None:
    bundle = ClaudeImporter().parse(ROOT / "sample_data" / "claude_sample.json")[0]
    assert bundle.conversation.provider == "claude"
    assert bundle.conversation.remote_id == "claude-rl-1"
    assert bundle.messages[0].metadata["uuid"] == "m1"


def test_generic_json_importer_handles_simple_schema() -> None:
    bundle = GenericJsonImporter().parse(ROOT / "sample_data" / "generic_sample.json")[0]
    assert bundle.conversation.title == "MemoryOS MVP planning"
    assert bundle.messages[0].metadata["tags"] == ["citations"]
