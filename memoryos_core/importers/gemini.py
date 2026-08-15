from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from memoryos_core.importers.base import Importer, ImporterError


class GeminiImporter(Importer):
    provider = "gemini"

    def __init__(self):
        # Import here to avoid circular dependency
        from packages.chat_normalization.importers import text_from_value, make_source
        self._text_from_value = text_from_value
        self._make_source = make_source

    def parse(self, path: Path) -> list[Any]:

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ImporterError(f"Invalid JSON: {exc}") from exc

        if not isinstance(raw, dict):
            raise ImporterError("Gemini export must be a conversation object")
        turns = raw.get("conversation_turns")
        if not isinstance(turns, list):
            raise ImporterError("Gemini export does not contain conversation_turns")

        raw_messages: list[dict[str, Any]] = []
        for index, turn in enumerate(turns, start=1):
            if not isinstance(turn, dict):
                raise ImporterError(f"Gemini turn {index} is not an object")
            if "user_turn" in turn:
                message = self._parse_user_turn(turn["user_turn"], index)
            elif "system_turn" in turn:
                message = self._parse_system_turn(turn["system_turn"], index)
            else:
                raise ImporterError(f"Gemini turn {index} is neither user_turn nor system_turn")
            if message["content"].strip():
                raw_messages.append(message)

        if not raw_messages:
            raise ImporterError("Gemini conversation contains no non-empty messages")

        return [
            self._make_source(
                provider=self.provider,
                title=raw.get("title") or path.stem,
                source_file=path,
                raw_conversation=raw,
                raw_messages=raw_messages,
                remote_id=raw.get("conversation_id") or path.stem,
                metadata={
                    "source_format": "gemini_takeout_conversation",
                    "creation_time": raw.get("creation_time"),
                    "last_modification_time": raw.get("last_modification_time"),
                },
            )
        ]

    def _parse_user_turn(self, turn: Any, index: int) -> dict[str, Any]:
        if not isinstance(turn, dict):
            raise ImporterError(f"Gemini user turn {index} is not an object")
        return {
            "role": "user",
            "content": self._text_from_value(turn.get("prompt")),
            "created_at": turn.get("turn_last_modified"),
            "turn_index": turn.get("turn_index"),
        }

    def _parse_system_turn(self, turn: Any, index: int) -> dict[str, Any]:
        if not isinstance(turn, dict):
            raise ImporterError(f"Gemini system turn {index} is not an object")
        return {
            "role": "assistant",
            "content": self._text_from_value(turn.get("text")),
            "created_at": turn.get("turn_last_modified"),
            "turn_index": turn.get("turn_index"),
        }
