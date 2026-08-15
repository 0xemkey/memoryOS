from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, Field

from memoryos_core.models import ConversationBundle


class ImporterError(ValueError):
    pass


class ImportReport(BaseModel):
    imported: int = 0
    skipped: int = 0
    duplicated: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)
    conversation_ids: list[str] = Field(default_factory=list)


class Importer(ABC):
    provider: str

    @abstractmethod
    def parse(self, path: Path) -> list[ConversationBundle]:
        raise NotImplementedError
