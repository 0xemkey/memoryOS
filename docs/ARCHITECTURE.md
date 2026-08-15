# MemoryOS Individual MVP Architecture

## Assumptions

- The MVP is local-first and stores application data in `MEMORYOS_DATA_DIR`, defaulting to `.memoryos_data`.
- Provider exports are manually imported files. The adapters are intentionally isolated because real export shapes can drift.
- Ollama remains configurable, but the first runnable slice uses a deterministic local embedding fallback so tests and first-run search work offline.
- Telemetry is disabled by default, and imported content is never uploaded.

## Overview

MemoryOS is split into a core domain package, a thin FastAPI API, and a desktop frontend shell.

- `memoryos_core/importers`: provider adapters that normalize source files into conversations and messages.
- `memoryos_core/storage`: SQLite persistence, migrations, FTS5 indexing, export, and deletion.
- `memoryos_core/chunking`: conversation-aware chunks that preserve message IDs and metadata.
- `memoryos_core/embeddings`: replaceable embedding providers.
- `memoryos_core/retrieval`: hybrid keyword plus semantic retrieval.
- `memoryos_core/reasoning`: local evidence-only answer generation and prompt-injection policy.
- `apps/api`: typed FastAPI routes.
- `apps/desktop`: React UI shell for the Tauri desktop app.

## Technology Decisions

- FastAPI provides typed local HTTP APIs and clear generated docs.
- SQLite is the canonical local store. SQLite FTS5 powers keyword search.
- The vector layer is currently stored as JSON embeddings in SQLite for portability. Qdrant local mode or FAISS can replace this behind the same retriever boundary.
- React and TypeScript provide the desktop UI. Tauri config is prepared for the app shell.
- Python uses plain modules and Pydantic models rather than a heavy framework stack.

## Database Schema

The initial migration creates:

- `conversations`: normalized conversation metadata and lightweight summary.
- `messages`: raw chronological messages.
- `sources`: imported local source file records.
- `chunks`: conversation-aware retrievable units with source metadata.
- `chunks_fts`: SQLite FTS5 virtual table.
- `import_jobs`: import logs and counts.
- `user_settings`: explicit editable preferences only.
- `retrieval_events`: query audit metadata without telemetry.

## Normalized Data Models

Core Pydantic models live in `memoryos_core/models.py`:

- `NormalizedConversation`
- `NormalizedMessage`
- `ConversationBundle`
- `Chunk`
- `SearchResult`
- `Citation`

## Implementation Plan

1. Keep this vertical slice runnable with sample imports, search, ask, export, and delete.
2. Add Ollama embedding and chat providers behind the existing interfaces.
3. Add a true local vector backend using FAISS or Qdrant local mode.
4. Expand provider parser tests with user-supplied real export samples.
5. Connect Tauri commands to API lifecycle management.
6. Package Windows and Linux private-beta builds.

## Risks And Mitigations

- Provider export formats change: adapters are isolated and tests use synthetic fixtures.
- Citation trust is critical: chunks preserve message IDs and the reasoner only cites retrieved results.
- Prompt injection in old conversations: retrieved text is treated as untrusted evidence by policy.
- Local model availability varies: deterministic local fallback keeps core workflows testable.
