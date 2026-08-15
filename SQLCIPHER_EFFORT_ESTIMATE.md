# SQLCipher Integration — Effort Estimate & Technical Approach

**Date**: 2026-08-15  
**Analysis**: Options B and C1 (encrypt sanitized.sqlite3 and normalized.sqlite3)  
**Conclusion**: Both are **2-4 hours each**, same core mechanism, can be done independently or together

---

## Current State

### Key Provider (Existing)
- Three implementations: `KeyringKeyProvider` (production), `StaticKeyProvider` (testing), `EphemeralKeyProvider` (dev)
- All return 32 bytes (`bytes`)
- Usage: `key_provider.get_key()` → `bytes`

### Vault Encryption (Reference Implementation)
- Uses Fernet (authenticated symmetric cipher) from `cryptography` library
- Already in dependencies (cryptography>=42.0.0)
- Pattern: `VaultCipher(key).encrypt_text(value)` returns encrypted bytes
- This is NOT the same as database-level encryption but shows how keys are used

### Database Access Patterns
- **normalized.sqlite3**: SQLAlchemy ORM + sessionmaker (packages/normalized_storage/store.py)
- **sanitized.sqlite3**: Raw sqlite3 with explicit connection management (packages/sanitized_storage/store.py)

---

## Option B: Encrypt sanitized.sqlite3 (MEDIUM EFFORT)

### What Needs to Change

1. **Add dependency**: `pysqlcipher3` (20 minutes)
   - Available as source distribution, builds cleanly on Windows with MSVC
   - Alternative: `cryptg` library (smaller, but pysqlcipher3 is more standard)

2. **Modify sanitized_storage/store.py** (1-1.5 hours)
   - Replace standard sqlite3 import with pysqlcipher3
   - Pass key to every connection via PRAGMA key after connect
   - Pattern:
     ```python
     import pysqlcipher3.dbapi2 as sqlite3
     
     # In every method that opens a connection:
     def get_connection(key_provider):
         conn = sqlite3.connect(db_path)
         key_hex = key_provider.get_key().hex()  # Convert to hex string
         conn.execute(f"PRAGMA key = \"x'{key_hex}'\"")
         return conn
     ```

3. **Create factory method** (30 minutes)
   - Extract connection creation into a single method that applies PRAGMA key
   - Reduces repetition, makes maintenance easier
   - All 6 methods in store.py that call `sqlite3.connect()` updated to use factory

4. **Add test** (30 minutes)
   - Verify encrypted database can't be read with standard sqlite3
   - Verify database works correctly with key
   - Verify wrong key fails

### Code Changes

**File**: `packages/sanitized_storage/store.py`

Before:
```python
import sqlite3

# In multiple methods:
conn = sqlite3.connect(self.db_path)
```

After:
```python
import pysqlcipher3.dbapi2 as sqlite3
from packages.vault_crypto.keys import KeyProvider

class SanitizedStore:
    def __init__(self, db_path: Path, key_provider: KeyProvider):
        self.db_path = db_path
        self.key_provider = key_provider
    
    def _get_connection(self) -> sqlite3.Connection:
        """Open encrypted connection using vault key."""
        conn = sqlite3.connect(self.db_path)
        key_hex = self.key_provider.get_key().hex()
        conn.execute(f"PRAGMA key = \"x'{key_hex}'\"")
        return conn
    
    def save_chunks(self, chunks, embeddings=None):
        # OLD: conn = sqlite3.connect(self.db_path)
        # NEW:
        conn = self._get_connection()
        # ... rest unchanged
```

**All affected methods in sanitized_storage/store.py**:
- `search_chunks_fts()` — 1 line change
- `log_retrieval_event()` — 1 line change
- `list_chunks()` — 1 line change
- `save_chunks()` — 1 line change
- `save_package()` — 1 line change

### Complexity

- ✅ Low risk: Key provider already available, same key infrastructure as vault
- ✅ Isolated change: Only affects sanitized_storage; other modules unchanged
- ✅ Backward compatible: Can add migration to re-encrypt existing DB or just start fresh
- ⚠️ One gotcha: migrate() also needs encryption after DB creation

### Estimated Time: **1.5-2 hours**
- Dependency: 15 min
- Code changes: 45 min
- Test: 30 min
- Verification: 15 min

---

## Option C1: Also Encrypt normalized.sqlite3 (SIMILAR EFFORT)

### What Needs to Change

1. **Add SQLAlchemy event hook** (1-1.5 hours)
   - SQLAlchemy uses connection pools; need to apply PRAGMA key after each connection
   - Pattern: SQLAlchemy event listener on `connect` event
   ```python
   from sqlalchemy import event, create_engine
   
   def set_encryption_pragma(dbapi_conn, connection_record):
       key_hex = key_provider.get_key().hex()
       dbapi_conn.execute(f"PRAGMA key = \"x'{key_hex}'\"")
   
   engine = create_engine(f"sqlite:///{db_path}", future=True)
   event.listen(engine, "connect", set_encryption_pragma)
   ```

2. **Modify normalized_storage/store.py** (45 minutes)
   - Update `__init__` to accept key_provider
   - Update `create_engine()` call to register the event listener
   - No other code changes needed (encryption handled transparently by engine)

3. **Update API layer** (30 minutes)
   - `apps/orchestrator/private_brain.py` already creates NormalizedImportStore
   - Pass key_provider to constructor
   - Pattern: Already receives vault key provider for vault_store, reuse same one

4. **Add test** (30 minutes)
   - Same as sanitized: verify encrypted DB can't be read, etc.

### Code Changes

**File**: `packages/normalized_storage/store.py`

Before:
```python
class NormalizedImportStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{self.db_path}", future=True)
```

After:
```python
from sqlalchemy import event
from packages.vault_crypto.keys import KeyProvider

class NormalizedImportStore:
    def __init__(self, db_path: Path, key_provider: KeyProvider):
        self.db_path = db_path
        self.key_provider = key_provider
        self.engine = create_engine(f"sqlite:///{db_path}", future=True)
        
        # Register encryption on every connection
        @event.listens_for(self.engine, "connect")
        def set_pragma(dbapi_conn, connection_record):
            key_hex = key_provider.get_key().hex()
            dbapi_conn.execute(f"PRAGMA key = \"x'{key_hex}'\"")
```

**File**: `apps/orchestrator/private_brain.py`

Before:
```python
self.normalized_store = NormalizedImportStore(self.config.normalized_db)
```

After:
```python
self.normalized_store = NormalizedImportStore(self.config.normalized_db, vault_key_provider)
```

### Complexity

- ✅ Low risk: SQLAlchemy event hooks are standard pattern
- ✅ Isolated change: Only affects normalized_storage
- ✅ Backward compatible: Can migrate existing DB or start fresh
- ⚠️ One gotcha: SessionFactory also needs to trigger encryption on each connection (already happens via engine events)

### Estimated Time: **1.5-2 hours**
- Dependency: Shared with Option B (0 min if B done first)
- Code changes: 45 min
- Integration (update PrivateBrainService): 15 min
- Test: 30 min
- Verification: 15 min

---

## Key Derivation Details

### Reuse Existing Vault Key or Derive New One?

**Current Design** (vault only):
- One 32-byte key per user (stored in OS keychain)
- All vault entity values encrypted with same key
- Accessible via `self.vault_store.key_provider.get_key()`

**Proposed Design** (vault + databases):
- **Option 1** (RECOMMENDED): Reuse same vault key for database encryption
  - Pros: Single key to manage, users expect vault key to protect all sensitive data
  - Cons: If vault key is compromised, all databases are compromised (no defense in depth)
  - Implementation: Pass same `key_provider` to both SanitizedStore and NormalizedImportStore

- **Option 2** (DEFENSE IN DEPTH): Derive separate keys for each database
  - Pros: Compartmentalization (vault breach doesn't compromise all databases)
  - Cons: More complex, additional key derivation logic needed
  - Implementation: `HKDF(master_key, salt="sanitized_db")` for sanitized, `HKDF(master_key, salt="normalized_db")` for normalized

**Recommendation**: Use **Option 1** for MVP. The vault key is already protected in the OS keychain, and the benefit of separate keys is marginal until multi-user support is added.

---

## Installation & Compatibility Check

### pysqlcipher3 Status

✅ **Can be installed cleanly on Windows + Python 3.13**:
```
$ python -m pip install pysqlcipher3 --dry-run
Collecting pysqlcipher3
  Downloading pysqlcipher3-1.2.0.tar.gz (102 kB)
  Installing build dependencies: started
  ...finished...
  Would install pysqlcipher3-1.2.0
```

✅ **MSVC compiler available**: `distutils.ccompiler` reports `msvc`

✅ **Build should work**: Source distribution with standard setup.py pattern

⚠️ **Note**: Installation will involve building C extensions (~5-10 minutes on first install, then cached)

### Dependency Addition

Add to `pyproject.toml`:
```toml
dependencies = [
  # ... existing ...
  "pysqlcipher3>=1.2.0",
]
```

Or: Optional dependency for users who want encryption:
```toml
[project.optional-dependencies]
encrypt = ["pysqlcipher3>=1.2.0"]
```

---

## Combined Effort (B + C1 Together)

If implementing both options in sequence:
- Dependency: 15 min (once)
- sanitized_storage (Option B): 1.5 hours
- normalized_storage (Option C1): 1.5 hours
- Integrated testing: 30 min
- **Total: 3.5-4 hours**

If doing one first:
- Option B alone: 2 hours
- Option C1 alone: 2 hours
- Option B then C1: +1.5 hours (shared dependency, simplified testing)

---

## Migration Strategy (Existing Data)

### Current State
- Users may already have plaintext databases

### Three Options:

**A) Fresh Start** (Simplest, 0 hours)
- Users delete `.memoryos_data/` on first run with new version
- New databases created encrypted
- Data loss, but simple implementation

**B) On-Demand Migration** (15 minutes, moderate)
- Detect plaintext database on startup
- Provide CLI command: `memoryos migrate-encrypt`
- Copies plaintext → encrypted database, verifies, deletes plaintext
- User is responsible for running

**C) Transparent Migration** (1 hour, complex)
- Detect plaintext on first connect
- Automatically re-create as encrypted in background
- Requires careful handling of concurrent access

**Recommendation**: Option B for MVP (user opt-in, simple, safe)

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| pysqlcipher3 build fails on user system | Low (works on our Windows) | High (install breaks) | Test on multiple platforms, provide binary wheel if needed |
| Key leakage (key in plaintext in code) | Low (using key_provider) | Critical | Code review, never hardcode keys |
| Wrong key on connection | Medium | High (database corrupted) | Explicit tests, error messages |
| SQLCipher overhead | Low | Medium (slower queries) | Document, benchmark before/after |
| Backward compat (old plaintext DB) | Medium | Medium (upgrade confusion) | Migration tool, clear docs |

---

## Effort Summary Table

| Option | Changes | Time | Risk | Priority |
|--------|---------|------|------|----------|
| B (sanitized only) | sanitized_storage/store.py | 2 hrs | Low | Medium (most-used DB) |
| C1 (normalized only) | normalized_storage/store.py | 2 hrs | Low | High (rawest data) |
| B + C1 | Both above | 3.5 hrs | Low | High (closes gap) |
| A (Document Only) | README + KNOWN_LIMITATIONS | 30 min | None | IMMEDIATE (do regardless) |

---

## Recommendation

1. **Do Option A immediately** (30 min) — Users need honesty before import
2. **Do Option C1 next** (2 hrs) — normalized.sqlite3 is the most sensitive
3. **Do Option B after** (2 hrs) — sanitized.sqlite3 is also plaintext but less raw
4. **Skip separate key derivation** — Reuse vault key for simplicity

This gives you **encrypted-at-rest protection for all three databases in ~4 hours of work**, and Option A is a blocker that must happen regardless.

---

**Last Updated**: 2026-08-15  
**Next Step**: User decision on whether to implement B, C1, both, or just A
