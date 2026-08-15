# MemoryOS Individual MVP

Local-first personal AI memory for imported AI conversations and documents.

> Your conversations and documents remain on this device.

## First Runnable Slice

This repository currently includes:

- FastAPI backend with `/imports`, `/conversations`, `/search`, `/ask`, `/settings`, `/export`, `/data`, and `/health`.
- SQLite schema with FTS5 keyword search.
- Deterministic keyword-fallback search (lower quality without Ollama embeddings - ~50% noise on diverse corpora).
- ChatGPT, Claude, generic JSON, Markdown, and plain-text importers.
- Conversation-aware chunking with source-rich citations.
- Synthetic sample data and pytest coverage.
- React/Tauri desktop UI scaffold.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
.\scripts\reset_data.ps1
.\scripts\run_api.ps1
```

Open the API docs at `http://127.0.0.1:8765/docs`.

## Import Sample Data

```powershell
$body = @{ path = "$PWD\sample_data\chatgpt_sample.json"; provider = "chatgpt" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/imports -Body $body -ContentType "application/json"
```

Then search:

```powershell
$body = @{ query = "reinforcement learning robot decision"; limit = 5 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/search -Body $body -ContentType "application/json"
```

## Tests

```powershell
python -m pytest
```

Pytest is configured to use `.memoryos_test_cache` so Windows permission issues in `.pytest_cache` do not block collection. You can also override it explicitly:

```powershell
python -m pytest -o cache_dir=.memoryos_test_cache
```

To verify dependencies from a clean environment:

```powershell
python -m venv .venv-clean
.\.venv-clean\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv-clean\Scripts\python.exe -m pytest --collect-only -q
.\.venv-clean\Scripts\python.exe -m pytest
```

## Private-Brain Milestone 1 CLI

The trusted normalized import foundation is available through:

```powershell
memoryos import .\tests\fixtures\private_brain_generic.json --provider generic_json
memoryos imports list
memoryos conversations list
memoryos conversations show <conversation-id>
```

By default it stores normalized trusted-zone data in:

```text
.memoryos_data/normalized.sqlite3
```

This database contains unsanitized normalized content and must not be mounted into the future reasoning service.

## Private-Brain Milestone 2 Privacy Detection

The deterministic local scanner can be used from Python:

```python
from packages.privacy_detection import PrivacyScanner

findings = PrivacyScanner().scan_messages(messages)
```

The scanner detects common personal identifiers and credentials locally. Credentials default to `remove`; sensitive personal identifiers default to `quarantine`; personal and company-confidential entities default to `pseudonymize`.

## Private-Brain Milestone 3 Vault Crypto

Pseudonyms are stable HMAC-SHA256 typed tokens:

```text
<PERSON_...>
<EMAIL_...>
<PROJECT_...>
```

Vault mappings are encrypted with authenticated encryption. Production key access is implemented through the OS keychain provider; tests use explicit test keys and verify that plaintext mappings are not written to SQLite.

## Private-Brain Milestone 4 Sanitized Handoff

Sanitization applies privacy findings to trusted normalized messages:

- `remove` replaces credential spans with removed markers.
- `pseudonymize` writes encrypted mappings to the vault and replaces values with stable tokens.
- `quarantine` and `review` keep messages out of sanitized packages.

Sanitized package hashes are validated before storage.

## Private-Brain Milestone 5 Reveal

Reveal is handled by the Privacy Vault only. It supports:

- `sanitized`
- `partial`
- `full`

Explicit approval is required for `partial` and `full`. Revealed answers are not persisted by default, and audit events store counts only.

## Private-Brain Milestone 6 Retrieval

Sanitized messages can be chunked and indexed with SQLite FTS5. Retrieval is sanitized-only. If Ollama embeddings are unavailable or not configured, the private-brain retriever uses keyword-only FTS5 search. This has known limitations:

- Works well on small, focused corpora (handful of related conversations)
- Degrades on large/diverse corpora: keyword matching returns syntactically matching but semantically irrelevant results (~50% noise measured in mixed-topic test)
- Recommendation: Install Ollama for semantic search on diverse data

The retriever reports `keyword_only` mode so users understand the quality tradeoff.

## Private-Brain Milestone 7 Reasoning

The private-brain reasoner accepts sanitized questions and sanitized evidence only. It can call a local Ollama chat model when configured, validates citations, and falls back to a deterministic cited evidence formatter when Ollama is unavailable.

## Private-Brain Milestone 8 Bounded Workflow

The bounded workflow performs at most two retrieval rounds and four tool calls. It stores explicit reasoning state and safe audit entries with query lengths rather than full query text.

## Private-Brain Milestone 9 Containers

Container configuration lives in:

```text
docker/compose.yaml
docker/privacy.Dockerfile
docker/reasoning.Dockerfile
docker/orchestrator.Dockerfile
```

Runtime container validation requires Docker or Podman. In the current environment neither command is available, so only static container configuration tests were run.

## Desktop UI

```powershell
cd apps/desktop
npm install
npm run dev
```

The desktop shell expects the API at `http://127.0.0.1:8765`.
