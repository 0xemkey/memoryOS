from __future__ import annotations

from memoryos_core.config import ensure_data_dir, get_settings
from memoryos_core.embeddings import HashEmbeddingProvider
from memoryos_core.reasoning import LocalReasoner
from memoryos_core.retrieval import HybridRetriever
from memoryos_core.storage import SQLiteStore


settings = get_settings()
store = SQLiteStore(ensure_data_dir(settings))
store.migrate()
embedder = HashEmbeddingProvider()
retriever = HybridRetriever(store, embedder)
reasoner = LocalReasoner()
