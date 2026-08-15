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

## 3. Connection Pooling in SQLite Context Managers

**Status**: Fixed in v0.2  
**Severity**: Was critical, now resolved  
**Details**: See SQLITE_CONNECTION_LEAK_INVENTORY.md

Connections are properly closed via context managers. No known leaks.

---

## Backlog Review Schedule

- **Next milestone**: After first 10 external users have used the system
  - Measure actual keyword-only mode frustration
  - Collect data on Ollama adoption rate
  - Decide: is Keyword-Only Limitation #1 urgent enough to redesign retrieval, or do users accept the Ollama workaround?

---

**Last Updated**: 2026-08-15  
**Review Date**: After first external user feedback loop
