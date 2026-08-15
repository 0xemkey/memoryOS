# MemoryOS Private Brain Gap Analysis

## Current State

The repository already contains an early local-memory MVP plus the beginning of the private-brain structure.

Implemented before this pass:

- Basic FastAPI memory API.
- Existing React desktop development UI.
- Synthetic import fixtures.
- Private-brain architecture overview.
- Private-brain package placeholders.
- Initial normalized Pydantic models.
- Generic JSON, Markdown, and plain-text normalization pipeline.
- Vault and sanitized migration skeletons.

## Specification Gaps

Milestone 1 gaps at the start of this pass:

- No normalized-zone migration directory.
- No SQLAlchemy models for normalized import persistence.
- No transactional normalized import store.
- No durable duplicate detection or import jobs for the private-brain path.
- No Typer CLI commands.
- Orchestrator exposed only `/health`, not read-only import/conversation APIs.
- No architecture import-boundary test.
- No milestone report.
- Documentation did not yet describe the new CLI or normalized storage commands.

Milestone 2+ gaps:

- Privacy detection is not implemented.
- Pseudonymization and encrypted vault mappings are not implemented.
- Keychain integration is not implemented.
- Sanitized handoff and sanitized-only indexing are not implemented.
- Reveal gateway is not implemented.
- Ollama reasoning and bounded reasoning loop are not implemented.
- Container isolation is not implemented or tested.

## Assumptions

- Milestone 1 normalized storage is trusted-zone unsanitized storage and must not be mounted into the future reasoning service.
- ChatGPT and Claude exact private-brain adapters are deferred because the prompt says not to guess provider schemas.
- The existing MVP can coexist temporarily while the private-brain architecture is built in separate `packages/*` and `apps/*` modules.
