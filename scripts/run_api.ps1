$env:PYTHONPATH = "."
python -m uvicorn apps.api.memoryos_api.main:app --reload --host 127.0.0.1 --port 8765
