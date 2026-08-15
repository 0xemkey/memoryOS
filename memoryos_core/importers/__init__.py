from __future__ import annotations

from pathlib import Path

from memoryos_core.importers.base import Importer, ImporterError
from memoryos_core.importers.chatgpt import ChatGPTImporter
from memoryos_core.importers.claude import ClaudeImporter
from memoryos_core.importers.gemini import GeminiImporter
from memoryos_core.importers.generic_json import GenericJsonImporter
from memoryos_core.importers.markdown import MarkdownImporter
from memoryos_core.importers.plain_text import PlainTextImporter


IMPORTERS: dict[str, type[Importer]] = {
    "chatgpt": ChatGPTImporter,
    "claude": ClaudeImporter,
    "gemini": GeminiImporter,
    "generic_json": GenericJsonImporter,
    "markdown": MarkdownImporter,
    "plain_text": PlainTextImporter,
}


def importer_for(provider: str, path: Path) -> Importer:
    normalized = provider.lower()
    if normalized == "auto":
        suffix = path.suffix.lower()
        if suffix == ".md":
            normalized = "markdown"
        elif suffix == ".txt":
            normalized = "plain_text"
        else:
            normalized = "generic_json"
    try:
        return IMPORTERS[normalized]()
    except KeyError as exc:
        raise ImporterError(f"Unsupported provider/import format: {provider}") from exc
