from __future__ import annotations

from pathlib import Path

from memoryos_core.importers.base import Importer, ImporterError
from memoryos_core.importers.common import make_bundle, read_json


class ClaudeImporter(Importer):
    provider = "claude"

    def parse(self, path: Path) -> list:
        raw = read_json(path)
        conversations = raw if isinstance(raw, list) else raw.get("conversations") if isinstance(raw, dict) else None
        if conversations is None:
            conversations = [raw]
        if not isinstance(conversations, list):
            raise ImporterError("Claude export must be a conversation object or list")
        bundles = []
        for idx, item in enumerate(conversations, start=1):
            if not isinstance(item, dict):
                raise ImporterError(f"Claude conversation {idx} is not an object")
            messages = item["chat_messages"] if "chat_messages" in item else item.get("messages")
            if not isinstance(messages, list):
                raise ImporterError(f"Claude conversation {idx} does not contain messages")
            if not messages:
                continue
            normalized = []
            for message in messages:
                if not isinstance(message, dict):
                    continue
                role = message.get("sender") or message.get("role")
                if role == "human":
                    role = "user"

                # Get content: prefer top-level "text" (Claude real export format)
                # If missing, try structured "content" array and join text fields
                content = message.get("text")
                if not content:
                    content_blocks = message.get("content")
                    if isinstance(content_blocks, list):
                        content = "\n".join(
                            block.get("text", "")
                            for block in content_blocks
                            if isinstance(block, dict) and block.get("text")
                        )

                # Append extracted file content from attachments (real export feature)
                attachments = message.get("attachments") or []
                attachment_content = []
                for attachment in attachments:
                    if isinstance(attachment, dict) and attachment.get("extracted_content"):
                        attachment_content.append(attachment["extracted_content"])

                if attachment_content:
                    content = (content or "") + "\n[Attached files]\n" + "\n".join(attachment_content)

                normalized.append(
                    {
                        "role": role,
                        "content": content,
                        "created_at": message.get("created_at") or message.get("updated_at"),
                        "uuid": message.get("uuid"),
                        "attachments": message.get("attachments"),
                        "files": message.get("files"),
                        "parent_message_uuid": message.get("parent_message_uuid"),
                    }
                )
            bundles.append(
                make_bundle(
                    provider=self.provider,
                    title=item.get("name") or item.get("title"),
                    source_file=path,
                    raw=item,
                    raw_messages=normalized,
                    remote_id=item.get("uuid") or item.get("id"),
                    metadata={"source_format": "claude_export"},
                )
            )
        return bundles
