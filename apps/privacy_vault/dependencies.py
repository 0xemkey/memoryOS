from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from packages.vault_crypto import EphemeralKeyProvider, VaultStore


@lru_cache(maxsize=1)
def vault_store() -> VaultStore:
    vault_path = Path(os.getenv("MEMORYOS_VAULT_DB", ".memoryos_data/vault.sqlite3")).expanduser()
    # The local dev API uses explicit unsafe mode only for an unconfigured development vault.
    provider = EphemeralKeyProvider(allow_unsafe_development_mode=True)
    store = VaultStore(vault_path, provider)
    store.migrate()
    return store
