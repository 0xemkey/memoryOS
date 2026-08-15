from __future__ import annotations

from packages.normalized_storage import NormalizedImportStore
from packages.normalized_storage.config import normalized_db_path

normalized_store = NormalizedImportStore(normalized_db_path())
normalized_store.migrate()
