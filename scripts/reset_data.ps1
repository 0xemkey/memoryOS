if (Test-Path ".memoryos_data") {
  Remove-Item -LiteralPath ".memoryos_data" -Recurse -Force
}
python -c "from memoryos_core.config import get_settings, ensure_data_dir; from memoryos_core.storage import SQLiteStore; s=get_settings(); SQLiteStore(ensure_data_dir(s)).migrate(); print('MemoryOS local data reset')"
