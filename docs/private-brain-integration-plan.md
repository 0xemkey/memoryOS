# Private-Brain Integration Plan

## Old Data Flow

```text
React UI
  -> apps/api/memoryos_api
  -> .memoryos_data/memoryos.sqlite3
  -> raw MVP chunks
  -> hash fallback retrieval
  -> deterministic MVP answer formatter
```

The old path is useful as a rollback source but is not privacy-safe enough to remain the default reasoning path.

## New Data Flow

```text
React UI
  -> compatibility API at apps/api/memoryos_api
  -> private-brain orchestrator pipeline
  -> trusted normalization
  -> privacy scanner
  -> pseudonymization + encrypted vault mappings
  -> sanitized storage
  -> sanitized chunking
  -> sanitized retrieval
  -> bounded reasoning
  -> cited sanitized answer
  -> optional reveal through Privacy Vault gateway
```

## Reused Components

- `packages.chat_normalization`: generic/Markdown/plain-text import foundation.
- `memoryos_core.importers.claude`: existing Claude parser shape knowledge from the real export.
- `packages.privacy_detection`: deterministic scanner.
- `packages.pseudonymization`: HMAC typed tokens.
- `packages.vault_crypto`: encrypted mappings and reveal gateway.
- `packages.sanitized_storage`: sanitizer and sanitized database.
- `packages.retrieval`: sanitized chunking, FTS, retrieval fallback.
- `packages.reasoning`: Ollama client, citation validation, bounded workflow, fallback answerer.

## Required Adapters

- Add a private-brain Claude importer using the observed Claude export structure:
  - top-level list of conversation objects
  - `uuid`, `name`, `created_at`, `updated_at`, `chat_messages`
  - messages with `uuid`, `text`, `content`, `sender`, timestamps, attachments, files
- Add a private-brain pipeline service that coordinates import, scanning, vault, sanitized storage, chunking, retrieval, reasoning, diagnostics, and reveal.
- Adapt existing `/imports`, `/conversations`, `/search`, `/ask`, and `/data` endpoints to use the private-brain pipeline by default.
- Keep the old MVP database as legacy rollback storage only.
- Update UI types and status display for sanitized answers, citations, modes, warnings, and reveal.

## Obsolete MVP Components

- `memoryos_core.embeddings.HashEmbeddingProvider` should no longer be described as semantic retrieval.
- MVP `chunks` in `.memoryos_data/memoryos.sqlite3` must not be the default Ask/Search source.
- MVP raw conversation viewer should be replaced with sanitized viewer by default.

## Database Strategy

- Preserve `.memoryos_data/memoryos.sqlite3` as legacy MVP storage.
- Use:
  - `.memoryos_data/normalized.sqlite3`
  - `.memoryos_data/vault.sqlite3`
  - `.memoryos_data/sanitized.sqlite3`
- Do not copy MVP chunks into sanitized storage.
- Re-import from original Claude export path when migrating existing Claude data.
- Do not delete legacy storage automatically.

## Frontend Changes

- Preserve existing layout.
- Add diagnostics panel values.
- Add import stage/statistics display.
- Show sanitized answer by default.
- Add reveal controls in Ask Memory.
- Show retrieval/reasoning modes and warnings.
- Conversation browsing should display sanitized messages.

## API Changes

Compatibility API stays at `http://127.0.0.1:8765` so the frontend does not need a new base URL.

Default endpoints become private-brain backed:

- `POST /imports`
- `GET /conversations`
- `GET /conversations/{conversation_id}`
- `POST /search`
- `POST /ask`
- `POST /answers/reveal`
- `GET /diagnostics`

Rollback config:

```text
MEMORYOS_USE_LEGACY_MVP=false
```

## Security Implications

- Raw and normalized unsanitized content remain trusted-zone data.
- Reasoning receives sanitized chunks only.
- Revealed answers are not persisted and never sent to reasoning.
- Diagnostics must report fallback status honestly.
- Container runtime isolation remains unverified until Docker/Podman exists.

## Rollback Strategy

- Set `MEMORYOS_USE_LEGACY_MVP=true` to temporarily route compatibility API calls to the old MVP store.
- Keep `.memoryos_data/memoryos.sqlite3` untouched.
- Private-brain migration/import should be idempotent and non-destructive.
