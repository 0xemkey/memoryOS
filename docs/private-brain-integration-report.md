# Private-Brain Integration Report

## Completed

- The default API path now routes imports, conversation listing, search, ask, diagnostics, and reveal through the private-brain pipeline.
- The old MVP database path remains available only when `MEMORYOS_USE_LEGACY_MVP=true`.
- Claude exports in the observed real shape are supported by `packages.chat_normalization`.
- Imported data flows through normalization, privacy detection, pseudonymization, encrypted vault storage, sanitized storage, chunking, FTS retrieval, bounded reasoning, citations, and optional reveal.
- The desktop app now shows private-brain diagnostics, import-stage statistics, retrieval/reasoning modes, warnings, sanitized answers, and non-persisted reveal output.

## Current Runtime Abilities

- Import Claude, ChatGPT, generic JSON, Markdown, and plain text files.
- Store normalized trusted-zone import records.
- Detect common private entities including email, phone, IP address, credentials, project names, organizations, usernames, and conservatively cued person names.
- Replace detected sensitive text with deterministic typed tokens.
- Store original token mappings in the encrypted privacy vault.
- Store and browse sanitized conversations and sanitized messages.
- Search sanitized chunks with SQLite FTS keyword fallback.
- Ask questions over sanitized retrieved context.
- Produce citation IDs for retrieved chunks.
- Fall back to deterministic local reasoning when Ollama is unavailable.
- Reveal tokenized answers through the reveal gateway without persisting revealed output.
- Report diagnostics for storage, vault, retrieval mode, reasoning mode, legacy mode, and container isolation status.

## Known Limits

- Gemini import is intentionally not implemented in this integration task.
- Person detection is conservative and cue-based; it is not a full local NER model.
- Embedding retrieval is not active unless an Ollama embedding path is configured and indexed.
- Reasoning falls back when Ollama is unavailable.
- Runtime container isolation is still `UNVERIFIED` because Docker/Podman is unavailable in the current environment.
- The legacy `/data` delete endpoint still clears the MVP store. A private-brain purge endpoint should be added before treating deletion as complete for the new data path.

## Verification

```text
python -m pytest tests/unit tests/security tests/integration --basetemp=.memoryos_test_tmp_private_brain_all -o cache_dir=.memoryos_test_cache_private_brain_all
65 passed
```

```text
npm run build
desktop TypeScript and Vite production build passed
```

## Gemini Roadmap

1. Add a synthetic Gemini export fixture based on the downloaded structure.
2. Implement `GeminiImporter(ChatImporter)` in `packages.chat_normalization.importers`.
3. Register it in `ChatImportPipeline` as `gemini`.
4. Add unit tests for Gemini parsing, malformed records, timestamps, roles, attachments, and duplicate IDs.
5. Add an integration test that imports Gemini through `POST /imports` and verifies sanitized search/ask/reveal.
6. Run the same privacy leak checks used by the Claude path before enabling it in the UI provider selector.
