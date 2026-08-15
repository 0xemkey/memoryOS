from __future__ import annotations

from pathlib import Path

from memoryos_core.importers.base import Importer, ImporterError
from memoryos_core.importers.common import make_bundle


class MarkdownImporter(Importer):
    provider = "markdown"

    def parse(self, path: Path) -> list:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            raise ImporterError(f"{path} is empty")
        title = next((line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("#")), path.stem)
        return [
            make_bundle(
                provider=self.provider,
                title=title,
                source_file=path,
                raw=text,
                raw_messages=[{"role": "user", "content": text}],
                remote_id=str(path.resolve()),
                metadata={"source_format": "markdown"},
            )
        ]
