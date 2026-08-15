# MemoryOS Private-Brain Architecture

## 1. Threat Model

Assets:

- Raw imported conversations and documents.
- Vault token mappings from pseudonyms to original private values.
- Vault encryption keys.
- Sanitized conversations, chunks, citations, and audit events.
- User-approved revealed answers.

Adversaries and failure modes:

- A compromised reasoning model trying to infer or request private mappings.
- Prompt injection inside retrieved conversations.
- Accidental raw-data writes into the sanitized database.
- A service misconfiguration that mounts vault files into the reasoning environment.
- A developer accidentally logging credentials, keys, raw content, or revealed answers.
- A malformed provider export that bypasses validation.

Milestone 1 status:

- This milestone defines boundaries, schemas, models, imports, and migrations.
- It does not yet enforce cryptographic protection, scanner policy, reveal approval, or container isolation.

## 2. Trust-Boundary Diagram

```text
-------------------+       sanitized package       +-------------------------+
|  Privacy Vault   | ----------------------------> | Memory Reasoning System |
| raw imports      |                               | sanitized DB/index only |
| vault mappings   | <----- reveal request only --- | no vault access         |
| vault keys       |                               | no decrypt tools        |
+-------------------+                               +-------------------------+
          ^
          |
          | user-approved reveal
          |
+-------------------+
| Local UI          |
+-------------------+
```

## 3. Data-Flow Diagram

```text
Raw provider export
  -> normalized conversation models
  -> Privacy Vault scanner and pseudonymizer
  -> encrypted mapping storage
  -> sanitized import package
  -> sanitized database
  -> retrieval over sanitized chunks
  -> sanitized answer with citations
  -> optional reveal inside Privacy Vault after explicit approval
```

## 4. Repository Structure

```text
apps/
  orchestrator/
  privacy_vault/
  reasoning_service/
  local_ui/
packages/
  common_models/
  chat_normalization/
  privacy_detection/
  pseudonymization/
  vault_crypto/
  sanitized_storage/
  retrieval/
  reasoning/
  citations/
  audit/
migrations/
  vault/
  sanitized/
tests/
  unit/
  integration/
  security/
  fixtures/
docker/
```

The reasoning packages must not import from `packages.vault_crypto`, `packages.privacy_detection`, or `apps.privacy_vault`.

## 5. Database Schemas

Vault database, future milestone:

- `vault_entities`: token, entity type, encrypted original value, normalized fingerprint, timestamps.
- `vault_messages`: opaque message references and encrypted raw content.
- `vault_audit_events`: append-only events without raw values or keys.
- `vault_review_items`: user-reviewable findings and proposed actions.

Sanitized database:

- `sanitized_conversations`: provider metadata and sanitized titles only.
- `sanitized_messages`: sanitized content, privacy level, detected categories, token references.
- `sanitized_chunks`: sanitized searchable chunks, message IDs, citations, hashes.
- `sanitized_entities`: token metadata without original values.
- `privacy_audit_events`: append-only privacy events without raw private values.
- `import_jobs`: orchestration status and statistics.
- `retrieval_events`: sanitized query metadata.

## 6. API Contracts

Privacy Vault API:

- `POST /sanitize-import`
- `POST /sanitize-text`
- `POST /reveal`
- `GET /review-items`
- `POST /review-items/{id}/approve`
- `POST /review-items/{id}/change-action`
- `POST /review-items/{id}/reject`
- `GET /health`

Reasoning API:

- `POST /index`
- `POST /search`
- `POST /ask`
- `GET /sources/{source_id}`
- `GET /health`

Orchestrator API:

- `POST /imports`
- `GET /imports/{job_id}`
- `POST /ask`
- `POST /answers/{answer_id}/reveal`
- `GET /conversations`
- `GET /conversations/{conversation_id}`
- `DELETE /data`
- `GET /health`

## 7. Encryption-Key Lifecycle

- Production keys must be created and retrieved through the OS keychain.
- Keys must never be written to `.env`, SQLite, source files, Docker images, logs, or fixtures.
- The Privacy Vault is the only component that may hold a decrypted vault key.
- Key rotation will create a new key version and re-encrypt vault records in a controlled migration.
- Development-only ephemeral keys are allowed only behind an explicit unsafe flag in a future milestone.

## 8. Container Isolation Plan

Privacy container:

- `--network none`
- read-only root filesystem
- non-root user
- dropped Linux capabilities
- mount only vault data and raw import handoff paths
- no Ollama access
- no external credentials

Reasoning container:

- no vault directory mounts
- no raw import mounts
- no keychain access
- access only to sanitized storage
- optional local Ollama access by explicit configuration

Orchestrator:

- coordinates imports and asks
- does not hold decryption keys
- passes schema-validated sanitized packages only

## 9. Testing Strategy

Milestone 1:

- normalized model validation tests
- generic JSON import tests
- malformed input tests
- deterministic hash tests
- migration smoke tests

Future milestones:

- privacy scanner regression tests
- crypto/key-isolation tests
- reveal approval tests
- reasoning prompt-injection tests
- container filesystem and network isolation tests

## 10. Milestone Implementation Plan

Milestone 1 implemented in this pass:

- Add repository structure for private-brain services and packages.
- Add normalized chat models.
- Add provider importer interfaces and generic import pipeline.
- Add vault and sanitized database migrations.
- Add synthetic fixtures and tests.

Milestones 2-10 are intentionally not implemented in this pass.
