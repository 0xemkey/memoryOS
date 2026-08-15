from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    ollama_base_url: str
    chat_model: str
    embedding_model: str
    context_size: int
    retrieved_chunks: int
    telemetry_enabled: bool = False


def get_settings() -> Settings:
    data_dir = Path(os.getenv("MEMORYOS_DATA_DIR", ".memoryos_data")).expanduser()
    return Settings(
        data_dir=data_dir,
        ollama_base_url=os.getenv("MEMORYOS_OLLAMA_BASE_URL", "http://localhost:11434"),
        chat_model=os.getenv("MEMORYOS_CHAT_MODEL", "llama3.1"),
        embedding_model=os.getenv("MEMORYOS_EMBEDDING_MODEL", "nomic-embed-text"),
        context_size=int(os.getenv("MEMORYOS_CONTEXT_SIZE", "4096")),
        retrieved_chunks=int(os.getenv("MEMORYOS_RETRIEVED_CHUNKS", "6")),
        telemetry_enabled=os.getenv("MEMORYOS_TELEMETRY_ENABLED", "false").lower() == "true",
    )


def ensure_data_dir(settings: Settings) -> Path:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings.data_dir
