# Milestone Checklist

## Milestone 1: Normalized Import Foundation

- [x] repository structure
- [x] architecture documents
- [x] normalized Pydantic models
- [x] provider-independent importer protocol
- [x] generic JSON importer
- [x] Markdown importer
- [x] plain-text importer
- [x] deterministic source fingerprints
- [x] deterministic conversation and message IDs
- [x] deterministic content hashes
- [x] SQLite persistence
- [x] SQLAlchemy models
- [x] Alembic migration scaffold
- [x] transactional imports
- [x] duplicate detection
- [x] import jobs
- [x] import errors
- [x] CLI import command
- [x] read-only import and conversation API
- [x] synthetic fixtures
- [x] unit and integration tests

## Milestone 2: Deterministic Privacy Detection

- [x] pattern detectors
- [x] local NER interface
- [x] context-classification interface
- [x] `PrivacyFinding` model
- [x] policy action decisions
- [x] unit tests

## Milestone 3: Pseudonymization and Encrypted Vault

- [x] HMAC-SHA256 typed tokens
- [x] keychain-backed key lifecycle
- [x] development-only unsafe ephemeral key mode
- [x] authenticated encryption
- [x] encrypted vault mapping store
- [x] corruption and leakage tests

## Milestone 4: Sanitized Storage and Package Handoff

- [x] sanitization policy application
- [x] right-to-left span replacement
- [x] second-pass scanning
- [x] sanitized storage models
- [x] sanitized handoff package
- [x] quarantine exclusion
- [x] leakage and tampering tests

## Milestone 5: Privacy Review and Reveal Gateway

- [x] review item models/store
- [x] approval/change/reject workflow
- [x] reveal modes
- [x] token allowlist enforcement
- [x] partial reveal by type
- [x] privacy-safe reveal audit
- [x] non-persistence tests

## Milestone 6: Sanitized Chunking and Retrieval

- [x] sanitized chunking
- [x] token counting fallback
- [x] FTS5 search
- [x] Ollama embedding client with explicit fallback
- [x] hybrid retrieval
- [x] metadata filters
- [x] no-raw-index tests

## Milestone 7: Local Ollama Reasoning

- [x] Ollama chat client
- [x] grounded prompt
- [x] typed reasoning answer
- [x] citation validation
- [x] deterministic fallback answerer
- [x] prompt-injection tests

## Milestone 8: Bounded Reasoning Loop

- [x] explicit reasoning state
- [x] retrieval plan
- [x] hard retrieval/tool limits
- [x] optional second retrieval round
- [x] deterministic termination
- [x] safe audit trail

## Milestone 9: Process and Container Isolation

- [x] privacy container
- [x] reasoning container
- [x] orchestrator container
- [x] compose configuration
- [x] static container isolation tests
- [ ] runtime container isolation tests
