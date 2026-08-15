# Database Encryption Audit - Critical Findings

**Date**: 2026-08-15  
**Verdict**: PLAINTEXT ON DISK FOR TWO OF THREE DATABASES

---

## Executive Summary

MemoryOS claims "privacy-first" architecture but does **not encrypt conversation content at rest**. Only pseudonym mappings (the vault) are encrypted. Raw user messages and pseudonymized content both persist in plaintext SQLite databases on disk indefinitely.

### Quick Reference

| Database | Content | Encryption | Persistence | Risk |
|----------|---------|-----------|------------|------|
| `normalized.sqlite3` | Raw user messages (pre-sanitization) | ❌ PLAINTEXT | ♾️ Indefinite | **CRITICAL** |
| `sanitized.sqlite3` | Pseudonymized conversation content | ❌ PLAINTEXT | ♾️ Indefinite | **HIGH** |
| `vault.sqlite3` | Entity values (names, emails, etc.) | ✅ Encrypted (Fernet) | ♾️ Indefinite | LOW (encrypted) |

---

## Finding 1: NORMALIZED.SQLITE3 — RAW CONTENT UNENCRYPTED

**Status**: CRITICAL - User's original message text stored in plaintext on disk  
**Location**: `.memoryos_data/normalized.sqlite3` → `normalized_messages` table → `content` column

### Evidence

Direct read from database:
```
Message ID: msg_137339e63188bf5bab9b921d
Role: user
Content: "The MVP must show exact conversations supporting its answer."
Storage: READABLE UTF-8 TEXT (PLAINTEXT)
```

Code writes without encryption:
```python
# packages/normalized_storage/store.py:138
session.add(
    NormalizedMessageRow(
        message_id=message.message_id,
        role=message.role,
        content=message.content,  # ← DIRECT PLAINTEXT WRITE
        ...
    )
)
```

### Lifecycle

1. User imports ChatGPT/Claude export
2. Raw JSON parsed → `NormalizedMessageRow` objects
3. **Entire conversation stored plaintext in normalized.sqlite3**
4. Privacy scan + sanitization → content copied to sanitized.sqlite3
5. **ORIGINAL PLAINTEXT COPY REMAINS IN normalized.sqlite3 INDEFINITELY**
6. Only deleted if user calls `/delete-all-data` endpoint

### Data Exposed

Every raw message, including:
- Personal thoughts/advice never meant for AI
- Embedded code with secrets (API keys, passwords)
- PII that privacy scanning missed
- Drafts, questions, brainstorming before refinement

All readable in plaintext if disk is accessed.

---

## Finding 2: SANITIZED.SQLITE3 — PSEUDONYMIZED BUT STILL PLAINTEXT

**Status**: HIGH - Content is token-masked but stored unencrypted on disk  
**Location**: `.memoryos_data/sanitized.sqlite3` → `sanitized_chunks` table → `sanitized_content` column

### Evidence

Direct read from database:
```
Chunk ID: schunk_46fca4ce0f876a86fdeaff2c
Content preview: "user: Bu projeyi anla ve soracağım sorualra cevap ver [Attached files] Kanks, 
tüm o akademik fırtınalardan, Reviewer 2'nin acımasız eleştirilerinden v..."
Storage: READABLE UTF-8 TEXT (PLAINTEXT)
```

The content is pseudonymized (names replaced with `<PERSON_6CA1D52698>` tokens) but the **entire surrounding conversation text remains in plaintext**.

### What's Exposed

- All conversation context and topics
- Code snippets and technical details
- Research, planning, decision-making
- References to people by token (linkable via vault if key is compromised)

**Pseudonymization ≠ Encryption**: Tokens are deterministic and link back to the vault. If someone accesses both sanitized.sqlite3 and vault.sqlite3, they can reconstruct the original content.

---

## Finding 3: VAULT.SQLITE3 — ENCRYPTED (CORRECT)

**Status**: GOOD - Entity values are encrypted  
**Location**: `.memoryos_data/vault.sqlite3` → `vault_entities` table

### Evidence

```
Token: <PERSON_6CA1D52698>
Entity Type: person
Encrypted Value: gAAAAABqf5Gv_2X1EITWIBrIrbcMm3fFG_ZrJ5NuoY_9DYPALx_8YqYGE_EqYv3EGdlH5jTr-Dyp5_eu2G6l9pqtLPHRRgmJzw==
(Fernet-encrypted base64, requires key to decrypt)
```

Vault properly encrypts the **original values** of detected entities (actual names, emails, phone numbers).

**However**: This only protects the PII itself. The vault_messages table (designed to backup original raw content encrypted) is **EMPTY** — not actually being used.

---

## Finding 4: LIFECYCLE — RAW CONTENT NEVER CLEANED UP

**Status**: CRITICAL - Plaintext persists indefinitely after sanitization is complete

### Current Flow

```
1. Import                  → Raw content → normalized.sqlite3 (PLAINTEXT)
2. Normalize               → Same content remains in normalized.sqlite3
3. Privacy scan            → Vault records entities (ENCRYPTED)
4. Sanitize                → Pseudonymized → sanitized.sqlite3 (PLAINTEXT)
5. Chunk & index           → Same pseudonymized content in sanitized.sqlite3
6. Return to user          → "Success, data imported and privacy-scanned"
7. [NO CLEANUP]            → normalized.sqlite3 still has raw plaintext
8. [User's data lives here]→ Both normalized.sqlite3 AND sanitized.sqlite3 (plaintext)
9. Only deleted on explicit DELETE /data call
```

Code evidence:
```python
# apps/orchestrator/private_brain.py:62-106
def import_file(self, path: Path, provider: str = "auto"):
    job = self.normalized_store.import_path(path, provider)  # Stores plaintext
    # ... sanitization, chunking, indexing ...
    return stats  # No cleanup of normalized.sqlite3
```

---

## Finding 5: OS-LEVEL ENCRYPTION CHECK

**Status**: NONE - No SQLCipher, BitLocker, or FileVault integration

### Search Results

Grep for encryption keywords across codebase:
- ❌ `sqlcipher` — 0 results (SQLite not compiled with encryption)
- ❌ `pragma key` — 0 results (no encryption-at-rest in normalized/sanitized packages)
- ✅ `encrypt` — Found only in `vault_crypto/` package (isolated to vault only)

No reliance on OS-level encryption (BitLocker, FileVault, dm-crypt). User is responsible for full-disk encryption if deploying MemoryOS.

---

## What This Means

### For the User

1. **Their raw messages are readable in plaintext** on the disk running MemoryOS
2. **Even after privacy scanning**, the original stays on disk indefinitely
3. **No encryption-at-rest** unless they manually enable BitLocker/FileVault on the entire system
4. **Data deletion requires explicit endpoint call** — simply uninstalling or clearing cache does NOT securely delete

### For the "Privacy-First" Claim

The statement that MemoryOS is "privacy-first" is **accurate for identity redaction** (PII mapped to tokens, tokens encrypted) but **misleading for data confidentiality** (conversation content itself unencrypted on disk).

A more honest framing:
- "Privacy-first PII handling" ✓ (correct)
- "End-to-end encrypted communication" ✓ (conversations with Ollama over localhost)
- "At-rest encryption" ✗ (NOT implemented)
- "Secure zero-knowledge storage" ✗ (NOT implemented)

---

## Recommendations (Prioritized)

### IMMEDIATE (Before External Users)

1. **Document the plaintext-on-disk reality** in README and privacy docs
   - Users must understand their data is in plaintext unless they enable full-disk encryption
   - Explain how to enable BitLocker/FileVault if full-disk encryption is needed

2. **Add security advisory** to KNOWN_LIMITATIONS.md stating:
   - "Conversation content is stored in plaintext SQLite databases"
   - "Pseudonymization is NOT encryption"
   - "Vault (PII mappings) is encrypted, but surrounding text is not"

3. **Add explicit warning** to onboarding:
   - "Deploy on an encrypted disk if handling sensitive conversations"

### SHORT-TERM (First Release Iteration)

4. **Delete normalized.sqlite3 after sanitization** (not indefinitely persist)
   - After successful sanitization/chunking/indexing, clear normalized_messages
   - Keep normalized_conversations as audit log only (stores no sensitive text)
   - Reduces plaintext surface area by ~50%

5. **Add optional at-rest encryption** for sanitized.sqlite3
   - Use SQLCipher or similar if user enables via env var
   - Default to plaintext (don't break backwards compatibility)
   - Document the performance trade-off

### LONGER-TERM (Future Enhancement)

6. **Implement transparent encryption layer**
   - Auto-encrypt both normalized and sanitized at write time
   - Decrypt on query (minimal performance impact)
   - Protect against accidental plaintext export

---

## What NOT To Do

❌ **Don't claim "end-to-end encryption"** — Only vault.sqlite3 is encrypted  
❌ **Don't say "zero-knowledge"** — You have full access to plaintext databases  
❌ **Don't hide this in docs** — Users deploying MemoryOS need to know  
❌ **Don't rely on file permissions alone** — Linux/Windows file ACLs are not tamper-proof  

---

## Action Items for Compliance

### Before Shipping to External Users

- [ ] Update README: "At-rest encryption is NOT implemented. Deploy on encrypted disk if handling sensitive data."
- [ ] Add to KNOWN_LIMITATIONS.md: "Database Plaintext Storage (see DATABASE_ENCRYPTION_AUDIT.md)"
- [ ] Add security warning to first-run UI: "Your data is stored in plaintext SQLite. Use full-disk encryption if required."

### After First External User Feedback

- [ ] Decide: Is plaintext storage acceptable for your user base?
- [ ] If yes: Document it clearly and add to privacy policy
- [ ] If no: Implement cleanup of normalized.sqlite3 after sanitization (quick win)

---

## References

- `packages/normalized_storage/store.py:138` — Direct plaintext write
- `apps/orchestrator/private_brain.py:62-106` — No cleanup after sanitization
- `.memoryos_data/normalized.sqlite3` — Evidence: raw message content readable
- `.memoryos_data/sanitized.sqlite3` — Evidence: pseudonymized content readable
- `.memoryos_data/vault.sqlite3` — vault_entities table: properly encrypted

---

**Last Updated**: 2026-08-15  
**Status**: UNRESOLVED - Awaiting decision on encryption strategy
