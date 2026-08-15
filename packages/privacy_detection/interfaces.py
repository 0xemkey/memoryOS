from __future__ import annotations

from abc import ABC, abstractmethod

from packages.privacy_detection.models import PrivacyFinding


class LocalNERProvider(ABC):
    @abstractmethod
    def find_entities(self, message_id: str, text: str) -> list[PrivacyFinding]:
        raise NotImplementedError


class ContextClassifier(ABC):
    @abstractmethod
    def classify(self, text: str) -> str:
        raise NotImplementedError
