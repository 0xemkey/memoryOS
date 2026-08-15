# MemoryOS Private Brain Threat Model

This document tracks security assumptions and validations as the implementation progresses.

## Assets

- Raw imported exports.
- Normalized unsanitized conversations.
- Vault mappings and encrypted raw content.
- Vault encryption keys.
- Sanitized conversations, chunks, and embeddings.
- Citations and audit events.
- User-approved revealed answers.

## Primary Invariants

- Raw and normalized unsanitized content stay inside trusted boundaries.
- Reasoning services receive sanitized content only.
- Vault keys are never available to orchestrator or reasoning services.
- Revealed answers are never sent to reasoning or embedding systems.
- Prompt-injected imported content cannot override system instructions.

## Milestone 1 Validation

Milestone 1 validates import normalization, deterministic IDs/hashes, trusted-zone persistence, duplicate detection, and read-only access APIs.

Milestone 1 does not validate scanner accuracy, encrypted vault storage, reveal safety, or container isolation.

## Milestone 2 Validation

Milestone 2 adds deterministic local privacy detection for common credentials and personal identifiers.

Validated categories include:

- email addresses
- phone numbers
- IP addresses
- access-token URLs
- API keys
- JWT-shaped values
- private-key blocks
- recovery-code and password-like values
- account/national-ID-like values
- credit-card-like values with Luhn validation
- placeholder local NER for projects, organizations, and usernames

Limitations:

- Placeholder NER is conservative and pattern-based, not a learned model.
- Context classification is deterministic and intentionally returns `unknown` for ambiguous content.
- Findings are not yet pseudonymized, encrypted, or persisted to the vault.

## Milestone 3 Validation

Milestone 3 adds stable HMAC pseudonyms and encrypted vault entity storage.

Validated:

- same entity and vault key produce the same typed token
- different vault keys produce different tokens
- authenticated encryption rejects corrupted ciphertext
- unsafe ephemeral key mode is disabled by default
- plaintext original values do not appear in the vault SQLite file in tests

Limitations:

- The OS keychain provider is implemented but not exercised in automated tests to avoid mutating the user's real keychain.
- Review/reveal authorization is not implemented until Milestone 5.

## Milestone 4 Validation

Milestone 4 adds sanitized package generation and sanitized SQLite storage.

Validated:

- pseudonymized values do not appear in the sanitized database
- credentials are removed rather than pseudonymized
- sensitive messages can be quarantined and excluded from packages
- sanitized package hashes detect tampering
- a second scanner pass blocks remaining high-risk findings

Limitations:

- Review and reveal workflows are not implemented until Milestone 5.
- Sanitized chunking/retrieval is not implemented until Milestone 6.

## Milestone 5 Validation

Milestone 5 adds trusted review item workflow and reveal gateway behavior.

Validated:

- reveal requires explicit approval
- full reveal resolves only tokens present in the approved answer
- partial reveal can be limited by entity type
- unknown tokens remain unresolved
- revealed answers are not persisted by default
- reveal audit events contain only safe counts and metadata

Limitations:

- The local UI has not yet been upgraded for review/reveal controls.
- Container isolation is not implemented yet.

## Milestone 6 Validation

Milestone 6 adds sanitized-only chunking and retrieval.

Validated:

- chunks are generated only from sanitized messages
- FTS5 search works over sanitized chunks
- no raw pseudonymized values appear in chunks or sanitized DB in tests
- metadata filters work for provider, privacy level, and entity token
- retrieval explicitly reports `keyword_only` degraded mode when Ollama embeddings are unavailable

Limitations:

- Ollama embedding integration is implemented as a client but not exercised against a live model in tests.
- Local reasoning begins in Milestone 7.

## Milestone 7 Validation

Milestone 7 adds local sanitized reasoning.

Validated:

- deterministic fallback produces cited sanitized answers
- Ollama client output citations are validated
- invalid citations are removed
- missing citations fail safely
- prompt-injection text in evidence does not create reveal capability
- model payload contains sanitized evidence only in tests

Limitations:

- Live Ollama chat is not exercised in automated tests.
- Iterative retrieval is added in Milestone 8.

## Milestone 8 Validation

Milestone 8 adds a bounded reasoning controller.

Validated:

- maximum two retrieval rounds
- maximum evidence chunk selection
- duplicate query skipping
- deterministic termination with empty evidence
- safe audit events do not store full query text

Limitations:

- Tool set is currently limited to `search_memory`.
- Container isolation is still not implemented.

## Milestone 9 Partial Validation

Milestone 9 adds container configuration and static isolation checks.

Validated statically:

- Privacy Vault uses `network_mode: none`.
- Reasoning service has no vault or raw-import mounts.
- Orchestrator environment does not include vault key settings.
- Dockerfiles use non-root users.
- Services drop Linux capabilities and use read-only roots where configured.

Blocked:

- Runtime build and network/filesystem isolation tests cannot run because neither Docker nor Podman is installed in this environment.
