from __future__ import annotations

import os
from pathlib import Path


def normalized_db_path() -> Path:
    return Path(os.getenv("MEMORYOS_NORMALIZED_DB", ".memoryos_data/normalized.sqlite3")).expanduser()
