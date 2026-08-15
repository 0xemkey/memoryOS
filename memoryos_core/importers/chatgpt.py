from __future__ import annotations

from pathlib import Path

from memoryos_core.importers.base import Importer, ImporterError
from memoryos_core.importers.common import make_bundle, read_json, text_from_parts


class ChatGPTImporter(Importer):
    provider = "chatgpt"

    def parse(self, path: Path) -> list:
        raw = read_json(path)
        conversations = raw if isinstance(raw, list) else [raw]
        bundles = []
        for idx, item in enumerate(conversations, start=1):
            if not isinstance(item, dict):
                raise ImporterError(f"ChatGPT conversation {idx} is not an object")
            raw_messages = []
            mapping = item.get("mapping")
            if isinstance(mapping, dict):
                nodes = [node for node in mapping.values() if isinstance(node, dict)]
                nodes.sort(key=lambda n: ((n.get("message") or {}).get("create_time") or 0))
                for node in nodes:
                    message = node.get("message")
                    if not isinstance(message, dict):
                        continue
                    content = message.get("content") or {}
                    raw_messages.append(
                        {
                            "role": (message.get("author") or {}).get("role"),
                            "content": text_from_parts(content.get("parts") or content),
                            "created_at": message.get("create_time"),
                            "metadata": {"node_id": node.get("id"), "content_type": content.get("content_type")},
                        }
                    )
            elif isinstance(item.get("messages"), list):
                raw_messages = item["messages"]
            else:
                raise ImporterError("ChatGPT export must contain mapping or messages")
            bundles.append(
                make_bundle(
                    provider=self.provider,
                    title=item.get("title"),
                    source_file=path,
                    raw=item,
                    raw_messages=raw_messages,
                    remote_id=item.get("id"),
                    metadata={"source_format": "chatgpt_export"},
                )
            )
        return bundles
