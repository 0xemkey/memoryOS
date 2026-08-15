# Known Limitations

## 1. Keyword-Only Search Quality on Diverse Corpora

**Status**: Documented limitation (not a bug)  
**Severity**: Medium - affects search quality when Ollama is unavailable  
**Affects**: `/search` and `/ask` endpoints when Ollama embeddings are not configured

### Description
Without Ollama installed, search uses SQLite FTS5 keyword matching as a fallback. This works well on small, focused datasets but degrades significantly on large or diverse corpora because keyword matching cannot distinguish semantic relevance from syntactic matches.

### Measured Impact
Testing with a realistic noisy corpus (6 conversations: robot decision-making, Python async patterns, Q4 planning, cooking recipe):
- **Search endpoint**: 1 result, 100% relevant (conservative single-query search)
- **Ask endpoint**: 4 results, 50% relevant/50% noise (query reformulation + multi-round accumulation)
  - False positives: Q4 planning matched on "decision" keyword, cooking question matched on generic language patterns
  - Root cause: Multi-round retrieval accumulates results without relevance threshold; diverse corpus surfaces syntactic matches

### When This Occurs
- User runs MemoryOS without installing Ollama
- User imports or has access to conversations spanning multiple unrelated topics
- Examples: personal knowledge base mixing work + hobby + recipes + code snippets

### Recommendation
- **Small, focused imports** (handful of related conversations): Keyword-only mode is acceptable
- **Large or diverse data**: Install Ollama for semantic understanding
  - `ollama pull llama3.1` (one-time ~4GB download)
  - Zero additional configuration needed; app detects automatically

### Possible Future Improvements (Not Implemented)
1. **Add relevance threshold to keyword results**: Only return chunks where keyword match score exceeds a minimum threshold, reducing accumulated noise
2. **Make Ollama part of primary onboarding**: Instead of "optional" step, guide all users toward Ollama setup during first run

### Revisit After
First 10 external users - collect data on:
- How many run without Ollama
- Whether keyword-only search quality actually bothers them in practice
- Whether the remediation (install Ollama) is acceptable to real users

---

## 2. Claude Importer - Attachment Content Handling

**Status**: Fixed and verified  
**Severity**: Low - attachments are now properly extracted  
**Affects**: Claude export imports with attached files

### Description
Real Claude exports include `attachments` with `extracted_content` fields (actual file content users attached). The importer now:
- Extracts content from all attachments
- Appends it to the message body with "[Attached files]" header
- Preserves the original file context in the conversation

### What's included
Real Claude export format now fully supported:
- `"sender": "human"` / `"assistant"` (not "role")
- Top-level `"text"` field for message content
- Nested `"content"` array as fallback (blocks with timestamps/citations)
- `"attachments"` with `"extracted_content"` extraction

---

## 3. Phone Pattern False Positives on US/Written-Month Dates

**Status**: Partially mitigated  
**Severity**: Low - affects privacy scanning only when phone patterns are present  
**Affects**: Privacy scanner when processing dates in non-standard formats

### Description
Phone detection regex matches loose patterns (7+ digits with separators). Added validator to exclude ISO dates and European format dates (DD.MM.YYYY, YYYY-MM-DD with optional HH:MM time), but does NOT yet exclude:
- US format dates: MM/DD/YYYY (e.g., "03/25/2026")
- Written-month dates: "25 Jul 2026", "March 15, 2024"

### Excluded Formats (Working)
- `YYYY-MM-DD` (ISO)
- `DD.MM.YYYY` (European)
- `DD-MM-YY` (European short)
- `YYYY.MM.DD` (ISO alternate)
- All above with optional time HH:MM or HH-MM

### Not Yet Excluded (Known Gap)
- `MM/DD/YYYY` - US format
- `DD/MM/YYYY` - Alternative slash format  
- Written months: "March 15", "15 Jul 2026", etc.

### Recommendation
If processing US-date-heavy data, add validator for `/` separator format. Not urgent - privacy scanning still functions, just with occasional false positives that then get properly handled through pseudonymization.

---

## 6. Connection Pooling in SQLite Context Managers

**Status**: Fixed in v0.2  
**Severity**: Was critical, now resolved  
**Details**: See SQLITE_CONNECTION_LEAK_INVENTORY.md

Connections are properly closed via context managers. No known leaks. (This limitation was addressed during technical debt cleanup pass on 2026-08-15.)

---

## Backlog Review Schedule

- **Next milestone**: After first 10 external users have used the system
  - Measure actual keyword-only mode frustration
  - Collect data on Ollama adoption rate
  - Decide: is Keyword-Only Limitation #1 urgent enough to redesign retrieval, or do users accept the Ollama workaround?

---

## 4. Database Storage Is Plaintext On Disk (NOT Encrypted)

**Status**: CRITICAL - Requires user awareness before deployment  
**Severity**: Critical for confidentiality, not for functionality  
**Affects**: All deployments that handle sensitive conversations

### Description

**MemoryOS does NOT encrypt conversation content at rest.** Raw user messages and pseudonymized content are stored in plaintext SQLite databases:

- **normalized.sqlite3**: Raw user conversation content (pre-privacy-scan), stored plaintext
- **sanitized.sqlite3**: Pseudonymized conversation content, stored plaintext (PII replaced with tokens, but surrounding text unencrypted)
- **vault.sqlite3**: Entity mappings (actual names/emails) are encrypted with Fernet, but represents only the token-to-value map, not the bulk content

### What This Means

1. **Full-disk access**: If someone accesses the `.memoryos_data/` directory, they can read every conversation
2. **Plaintext persists indefinitely**: The original raw content in normalized.sqlite3 is never automatically deleted after sanitization (only deleted via explicit `/delete-all-data` API call)
3. **Pseudonymization ≠ Encryption**: The sanitized database tokens are deterministic and can be linked back to actual values if vault.sqlite3 is also compromised
4. **No at-rest encryption layer**: MemoryOS does not use SQLCipher, BitLocker, FileVault, or any encryption-at-rest mechanism

### Implications

- Users storing MemoryOS on unencrypted disks expose their conversation history in plaintext
- A disk forensics attack (e.g., stolen SSD, backup access) would reveal all unencrypted content
- File permissions (Linux/Windows ACLs) are insufficient protection against determined attackers

### Honest Assessment

This contradicts the "privacy-first" framing for at-rest security:
- ✅ **Privacy-first PII redaction**: Correct (names, emails tokenized)
- ✅ **Privacy-first in-transit**: Correct (no network exposure, localhost Ollama only)
- ❌ **Privacy-first at-rest**: INCORRECT (plaintext on disk)

### Recommendation

**Before deploying MemoryOS to production:**
1. Enable full-disk encryption (BitLocker on Windows, FileVault on macOS, dm-crypt on Linux)
2. Or: Accept that conversation content is plaintext and restrict physical access to the device
3. Explicitly document this trade-off with your users/stakeholders

### Mitigation (Already Implemented)
- vault.sqlite3 (PII mappings) is properly encrypted
- Secure deletion (overwrite with zeros) is used when `/delete-all-data` is called
- Only the **surrounding conversation context** is unencrypted, not the PII itself

### Future Improvement
See `DATABASE_ENCRYPTION_AUDIT.md` for detailed findings and recommended encryption strategy (adding SQLCipher support or transparent encryption layer).

---

## 5. Dual Model Hierarchy in Import Pipeline

**Status**: Documented, not code-fixed (lower priority)  
**Severity**: Low - operational, not data-impacting  
**Affects**: Future refactoring of `memoryos_core` and `packages/common_models` interaction (was Item 6 in technical debt cleanup)

### Description
The codebase maintains two separate model hierarchies for `NormalizedConversation` and `NormalizedMessage`:

**Location 1**: `memoryos_core/models.py`
- `NormalizedConversation`: `created_at`/`updated_at` with required defaults (via `Field(default_factory=now_utc)`)
- `NormalizedMessage`: field name `ordinal: int = 0`, `role` literal includes `"unknown"`
- Used by: `PrivateBrainService` import pipeline (`memoryos_core.importers`), all hot-path operations

**Location 2**: `packages/common_models/chat.py`
- `NormalizedConversation`: `created_at`/`updated_at` nullable with no default
- `NormalizedMessage`: field name `position: int` (required, no default), `role` literal excludes `"unknown"`
- Used by: legacy code paths and external-facing schemas

### Current Workaround
`packages/chat_normalization/pipeline.py:52-57` manually translates between the two hierarchies:
```python
msg_data = msg.model_dump()
if "ordinal" in msg_data:
    msg_data["position"] = msg_data.pop("ordinal")  # Field rename
converted_messages.append(NormalizedMessage(**msg_data))
```

This translation shim:
- Works correctly, no data loss
- Is non-obvious to contributors touching the import pipeline
- Creates a hidden coupling between two model definitions

### Why It Exists
Historical artifact: `packages/common_models` was created before full pipeline consolidation. Both hierarchies remain because:
1. `common_models` is vendored/exported as semi-stable contracts for external use
2. `memoryos_core/models.py` is the authoritative internal model set
3. Consolidating would require careful versioning of external APIs

### Recommendation
Not urgent. When the codebase stabilizes after first external users:
1. Document this in contributor guidelines
2. Consider whether `common_models` should be retained for backward compatibility or unified with `memoryos_core`
3. If unifying: need migration strategy for any external consumers relying on `packages.common_models` exports

---

**Last Updated**: 2026-08-15  
**Review Date**: After first external user feedback loop
