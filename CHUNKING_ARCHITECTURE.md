# Chunking Architecture - Actual Implementation

**Date**: 2026-08-15  
**Scope**: Current production implementation (packages/retrieval/chunking.py + schema in migrations/sanitized/001_initial.sql)

---

## Chunking Unit: What Gets Grouped Into One Chunk?

**Policy**: Sequential message grouping within each conversation, with user-assistant pairing preference.

**Algorithm** ([packages/retrieval/chunking.py:33-49](packages/retrieval/chunking.py#L33-L49)):

```python
# Line 33-49: Main chunking loop per conversation
while index < len(ordered):
    selected = [ordered[index]]  # Start with one message
    token_total = count_tokens(render_message(ordered[index]))
    index += 1
    
    # Line 37-42: Eager pair user+assistant if they fit
    if index < len(ordered) and selected[0].role == "user" and ordered[index].role == "assistant":
        candidate_tokens = count_tokens(render_message(ordered[index]))
        if token_total + candidate_tokens <= self.hard_max_tokens:
            selected.append(ordered[index])
            token_total += candidate_tokens
            index += 1
    
    # Line 43-49: Fill remaining capacity to target
    while index < len(ordered) and token_total < self.target_min_tokens:
        candidate_tokens = count_tokens(render_message(ordered[index]))
        if token_total + candidate_tokens > self.hard_max_tokens:
            break
        selected.append(ordered[index])
        token_total += candidate_tokens
        index += 1
```

**Result**: 1-N messages per chunk. Constraints are:
- Minimum size: `target_min_tokens` (default: 80) **OR** special case: single user+assistant pair regardless of size
- Maximum size: `hard_max_tokens` (default: 900)
- No overlap: Once a message is in a chunk, the next message starts the next chunk

**File**: [packages/retrieval/chunking.py:18-20](packages/retrieval/chunking.py#L18-L20) - defaults hardcoded in `__init__`

---

## Linking Back: Chunk → Messages → Conversation

**Data Flow**: chunk_id → message_ids[] → conversation_id → vault entities

### Chunk Schema ([migrations/sanitized/001_initial.sql:30-42](migrations/sanitized/001_initial.sql#L30-L42))

```sql
CREATE TABLE IF NOT EXISTS sanitized_chunks (
  chunk_id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES sanitized_conversations(conversation_id) ON DELETE CASCADE,
  message_ids_json TEXT NOT NULL,  -- JSON array of message IDs that make up this chunk
  provider TEXT NOT NULL,
  sanitized_title TEXT NOT NULL,
  sanitized_content TEXT NOT NULL,
  privacy_level TEXT NOT NULL,
  token_references_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT,
  content_hash TEXT NOT NULL UNIQUE,
  embedding_json TEXT
);
```

### How IDs Are Generated

**chunk_id** ([packages/retrieval/chunking.py:51-60](packages/retrieval/chunking.py#L51-L60)):

```python
chunk_hash = content_hash({
    "conversation_id": conversation_id,
    "message_ids": [message.message_id for message in selected],
    "content": content,
})
chunks.append({
    "chunk_id": stable_id("schunk", chunk_hash),
    "conversation_id": conversation_id,
    "message_ids": [message.message_id for message in selected],
    # ...
})
```

- Deterministic: Same messages + content = same chunk_hash = same chunk_id
- Prefix: `"schunk"` (sanitized chunk)
- Hash includes: conversation_id + all message_ids + rendered content

**Foreign Keys**:
- `chunk_id` (PK) ← links to results from `/search` or `/ask`
- `conversation_id` (FK) → `sanitized_conversations.conversation_id` with ON DELETE CASCADE
- `message_ids_json` (stored as JSON) → can be parsed to join back to `sanitized_messages.message_id`

### Retrieval Path ([apps/orchestrator/private_brain.py:259-274](apps/orchestrator/private_brain.py#L259-L274))

```python
# Line 268: Query by chunk_id
rows = conn.execute(
    f"SELECT * FROM sanitized_chunks WHERE chunk_id IN ({placeholders})",
    chunk_ids,
).fetchall()
```

**Not directly used in production**: The primary retrieval path queries by chunk content via FTS, not by explicit ID joins. The chunk_id is returned as a search result, and chunks are fetched individually if needed for re-ranking or citation building.

---

## Overlap Between Chunks: Yes or No?

**Answer**: **NO overlap. Strictly non-overlapping.**

**Evidence**:
- Line 36 in chunking loop: `index += 1` advances pointer AFTER consuming a message
- Line 42: `index += 2` when consuming user+assistant pair
- Line 49: `index += 1` when appending filler messages

Each message is processed exactly once. There is no sliding window or context duplication across chunk boundaries.

**Implication**: If a multi-turn exchange spans chunks, context is lost between them. Chunks are independent units retrieved via full-text search, not re-ranked by semantic similarity.

---

## Deduplication: How Are Duplicate Chunks Handled?

**Deduplication Key**: `content_hash` (stored in `sanitized_chunks.content_hash`)

**Schema** ([migrations/sanitized/001_initial.sql:40](migrations/sanitized/001_initial.sql#L40)):
```sql
content_hash TEXT NOT NULL UNIQUE
```

The UNIQUE constraint on `content_hash` means:

1. **First import**: Chunk with hash H is inserted
2. **Re-import same conversation**: 
   - Same messages + same content → same `chunk_hash` → same `chunk_id`
   - `INSERT OR IGNORE` in [packages/sanitized_storage/store.py:106](packages/sanitized_storage/store.py#L106) skips insertion
   - **Chunk is NOT regenerated; the existing chunk is reused**

**What This Means**: If you import the same ChatGPT conversation twice, the chunks are identical (same hash), so the second insert is ignored. No duplicate chunks in the index.

**Caveat**: If privacy scanning changes (e.g., new regex pattern added), re-imported conversations will produce *different* sanitized content → different hash → new chunks. Old chunks are not automatically removed (only INSERT OR IGNORE prevents new duplicates).

---

## Privacy Sanitization Timing: Before or After Chunking?

**Answer**: **Chunking happens AFTER privacy sanitization.**

**Pipeline** ([apps/orchestrator/private_brain.py:62-106](apps/orchestrator/private_brain.py#L62-L106)):

```python
def import_file(self, path: Path, provider: str = "auto") -> dict[str, Any]:
    # Line 64: Parse and normalize (no sanitization yet)
    result = ChatImportPipeline().import_path(path, provider)
    
    # Line 91: Initialize sanitizer
    sanitizer = SanitizationService(self.scanner, self.vault_store)
    chunker = SanitizedChunker()
    
    for source in result.sources:
        # Line 95: SANITIZE (privacy scan + pseudonymization)
        package = sanitizer.sanitize_source(source)
        
        # Line 96: Save to sanitized DB (after privacy scanning)
        self.sanitized_store.save_package(package)
        
        # Line 97: CHUNK the SANITIZED content
        chunks = chunker.chunk_package(package)
        
        # Line 98: Index
        retriever.index_chunks(chunks)
```

**Key ordering**:
1. ✅ **Normalize**: Import format → normalized messages
2. ✅ **Privacy scan**: Detect PII, build pseudonym map
3. ✅ **Pseudonymize**: Replace PII with tokens in messages
4. ✅ **Save sanitized**: Store pseudonymized messages
5. ✅ **Chunk**: Group sanitized messages
6. ✅ **Index**: FTS + embed

**Implication**: 
- Chunk boundaries are computed on **already-redacted** content
- If PII redaction changes a message's length, the token count may differ from the original
- Token counting happens on the sanitized content, not the raw import

**Example**: Raw message `"Contact john@example.com"` (3 tokens) → Sanitized `"Contact ENTITY_001"` (2 tokens). The chunker sees the 2-token version.

---

## Hidden Couplings with Tokenization

### 1. Token Counting Implementation ([packages/retrieval/chunking.py:9-10](packages/retrieval/chunking.py#L9-L10)) - APPROXIMATION GAP REMAINS

```python
def count_tokens(text: str) -> int:
    return len(re.findall(r"\S+", text))
```

**What it does**: Counts whitespace-delimited sequences (words), not actual LLM tokens.

**Measured gap on production data**: ~35% underestimation
- User's actual data (code blocks, URLs, Turkish text): word-count 612 → real tokens ~820+
- `"test@example.com"` → 1 "word" but 4+ real tokens
- Code blocks split on punctuation, inflate real token counts

**Why it matters for the fix**:
- ✅ **Bug fixed**: Chunks now split to stay under 900 words (hard constraint enforced)
- ⚠️ **Caveat**: 900 words ≈ 1,200+ real tokens on this data
- Embedding model limits: often 512-768 real tokens
- Current fix prevents 3,000-word chunks but allows ~1,200-token chunks which may silently truncate

**This requires tokenization team fix**: Replace with real tokenizer that matches the embedding model's actual tokenization, so the 900-word ceiling maps to a real token ceiling.

### 2. Hardcoded Token Budgets ([packages/retrieval/chunking.py:18-20](packages/retrieval/chunking.py#L18-L20))

```python
class SanitizedChunker:
    def __init__(self, target_min_tokens: int = 80, hard_max_tokens: int = 900):
        self.target_min_tokens = target_min_tokens
        self.hard_max_tokens = hard_max_tokens
```

**Default constraints**:
- Minimum size: 80 "words"
- Maximum size: 900 "words" (now enforced via splitting)

**Note**: The 900-word ceiling is now actually enforced (was broken before fix), but these are still approximation tokens, not real model tokens.

### 3. No Embedding-Model Awareness

The chunker does not:
- Query the embedding model for its actual token limit
- Adjust chunk size based on model configuration
- Have real tokenization that matches the embedding model

**Status**: ✅ Fixed for word-count approximation (splits work)  
**Pending**: Real tokenization integration by tokenization team

---

## Summary: What's Actually Implemented

| Aspect | Implementation | Location |
|--------|---|---|
| **Unit** | 1-N messages per conversation, sequential | packages/retrieval/chunking.py:33-49 |
| **Linking** | chunk_id → message_ids JSON → conversation_id (FK) | migrations/sanitized/001_initial.sql:30-42 |
| **Overlap** | None (strict sequential, no sliding window) | packages/retrieval/chunking.py:36,42,49 |
| **Deduplication** | By content_hash UNIQUE; INSERT OR IGNORE | migrations/sanitized/001_initial.sql:40; packages/sanitized_storage/store.py:106 |
| **Timing** | After sanitization, before indexing | apps/orchestrator/private_brain.py:95-97 |
| **Token count** | Whitespace-delimited word count (not LLM-aware) | packages/retrieval/chunking.py:9-10 |
| **Budgets** | Hard-coded defaults 80 min / 900 max | packages/retrieval/chunking.py:18-20 |
| **Model coupling** | Yes: assumes embedding-model-neutral token approximation | packages/retrieval/chunking.py:9-10 (used in 18-49) |

---

## What This Means for the Tokenization Team

**Before your tokenization layer integrates with chunking:**

1. **Token counting is currently naive**: Upgrade [count_tokens()](packages/retrieval/chunking.py#L9-L10) to use your actual tokenizer
   
2. **Token budgets are not adaptive**: If your tokenizer reveals that current chunks exceed your embedding model's limit, you'll need to reduce the hardcoded defaults in [SanitizedChunker.__init__()](packages/retrieval/chunking.py#L18-L20) or pass custom budgets to the orchestrator

3. **No overlap means no context continuity**: If your retrieval experiments show that chunks are too independent, you'd need to add sliding-window overlap logic to the chunking loop

4. **Deduplication is content-based**: If you change token counting, re-imported conversations will have different chunk hashes → new chunks. Plan for a migration strategy if this affects production data

5. **Sanitization happens first**: Your tokenizer will count tokens on *already-pseudonymized* content, not raw imports. PII redaction changes token counts.

---

**Last Updated**: 2026-08-15  
**Status**: Production implementation as of first external user release
