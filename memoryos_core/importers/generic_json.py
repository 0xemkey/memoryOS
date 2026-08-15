from __future__ import annotations

from pathlib import Path
from typing import Any

from memoryos_core.importers.base import Importer, ImporterError
from memoryos_core.importers.common import make_bundle, read_json


class GenericJsonImporter(Importer):
    provider = "generic_json"

    def parse(self, path: Path) -> list:
        raw = read_json(path)
        conversations = raw if isinstance(raw, list) else raw.get("conversations") if isinstance(raw, dict) else None
        if conversations is None:
            conversations = [raw]
        if not isinstance(conversations, list):
            raise ImporterError("Generic JSON must be an object, a list, or contain a conversations list")

        bundles = []
        for idx, item in enumerate(conversations, start=1):
            if not isinstance(item, dict):
                raise ImporterError(f"Conversation {idx} is not an object")
            messages: Any = item.get("messages") or item.get("mapping")
            if isinstance(messages, dict):
                messages = [
                    node.get("message")
                    for node in messages.values()
                    if isinstance(node, dict) and node.get("message")
                ]
            if not isinstance(messages, list):
                raise ImporterError(f"Conversation {idx} does not contain a messages list")
            bundles.append(
                make_bundle(
                    provider=str(item.get("provider") or self.provider),
                    title=item.get("title"),
                    source_file=path,
                    raw=item,
                    raw_messages=messages,
                    remote_id=item.get("id") or item.get("conversation_id"),
                    metadata={k: v for k, v in item.items() if k != "messages"},
                )
            )
        return bundles
