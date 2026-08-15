from __future__ import annotations

from pathlib import Path

from memoryos_core.importers.base import Importer, ImporterError
from memoryos_core.importers.common import make_bundle


class PlainTextImporter(Importer):
    provider = "plain_text"

    def parse(self, path: Path) -> list:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            raise ImporterError(f"{path} is empty")
        return [
            make_bundle(
                provider=self.provider,
                title=path.stem,
                source_file=path,
                raw=text,
                raw_messages=[{"role": "user", "content": text}],
                remote_id=str(path.resolve()),
                metadata={"source_format": "plain_text"},
            )
        ]
