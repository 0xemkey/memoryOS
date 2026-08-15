# First-Run Issues & Observations

## Status: No Critical Blockers Found ✅

The app successfully handles Ollama unavailability and provides graceful fallbacks. A first-time user can get from zero to a working ask/search in under 10 minutes.

---

## Issues Identified (Not Fixed - Flagged for Future)

### 1. **Search vs Ask Distinction Unclear**
**Impact**: Low  
**Description**: The UI has two buttons - "Search" and "Ask" - but their difference isn't obvious to a new user.
- Search: keyword retrieval only
- Ask: retrieval + reasoning (summary with citations)

First-timers might click both without understanding why results differ.

**Current behavior**: Both work correctly, just not labeled clearly  
**Future fix**: Add a tooltip or help text explaining the difference  
**Severity**: Low - users figure it out quickly by trying both

---

### 2. **Import Path Handling is Fragile**
**Impact**: Medium (only affects first import)  
**Description**: The UI import path input doesn't clearly indicate:
- Whether it expects absolute or relative paths
- What the current working directory is
- Examples of valid paths

Current behavior: Works with absolute paths, fails silently with relative paths that reference non-existent files.

**Example of confusion**:
- User enters: `sample_data/chatgpt.json` → fails (relative to user's CWD, not app CWD)
- User enters: `/Users/alice/Desktop/my_export.json` → works

**Future fix**: 
- Show the current working directory in the input field
- Provide an example valid path
- Or add a file picker dialog

---

### 3. **Ollama Timeout Error Message Could Be Clearer**
**Impact**: Low  
**Description**: When Ollama takes >30s to respond (slow start or timeout), the error shows as a generic "Ollama reasoning unavailable" warning in the citations section.

First-time users running Ollama for the first time won't know it's just slow, might think it's broken.

**Current behavior**: Falls back to keyword answer with warning  
**Suggested improvement**: "Ollama is starting up (takes 10-30s on first run)" vs "Ollama not found" (different messages)

---

### 4. **No Indication of Data Privacy During First Import**
**Impact**: Low  
**Description**: When importing sensitive data (emails, names, etc.), the UI doesn't explain:
- "Your data will be pseudonymized before storage"
- "Real names are encrypted in a local vault"
- "Privacy scanning happens automatically"

Most users will just click "Import" without understanding the privacy guarantees.

**Current behavior**: Data is correctly protected, user just doesn't see confirmation  
**Future enhancement**: Show import stats like "Detected X personal identifiers (encrypted in vault)"

---

### 5. **API Health Check Only Shows "Not Checked" Until API Responds**
**Impact**: Low  
**Description**: On app startup, the status bar shows "API not checked" for ~1-2 seconds while it's connecting to the API.

This can confuse users who think the app hasn't started.

**Current behavior**: Changes to "ready" when API responds  
**Future fix**: Show a loading state or "Connecting to API..." during the initial check

---

### 6. **Desktop App Bundle Startup is Slow**
**Impact**: Low (UX friction, not functionality)  
**Description**: `npm run dev` takes 5-10 seconds to start on first run (Vite build, dependency load)

A first-timer might think something is broken if they don't see the app appear immediately.

**Current behavior**: App eventually loads fine  
**Future improvement**: Show a splash screen or startup message with "MemoryOS is starting..."

---

### 7. **No Warning About Duplicate Imports**
**Impact**: Low  
**Description**: Importing the same file twice doesn't warn the user or skip duplicates.

For testing, this is fine (they're filtered downstream). But a user might accidentally import twice and wonder if something went wrong.

**Current behavior**: Silent duplicate handling (works correctly behind the scenes)  
**Future enhancement**: Show "X conversations already indexed, importing Y new ones"

---

### 8. **Settings Tab Shows Model Names Without Descriptions**
**Impact**: Very Low  
**Description**: The Settings tab lists technical values like:
```
embedding_model: nomic-embed-text
reasoning_model: llama3.1
```

A first-timer won't know if these are defaults, what they control, or how to change them.

**Current behavior**: Display only (can't change in UI)  
**Future fix**: Add descriptions: "embedding_model: Used for semantic search (leave as default unless you know what you're doing)"

---

## What's Already Good ✅

- **Ollama Fallback**: Gracefully handles missing Ollama with deterministic fallback + warning
- **API Availability Check**: UI clearly shows when API is unreachable
- **Data Initialization**: App creates empty schema on first run without errors
- **Sample Data**: Provided sample imports are ready to test immediately
- **Error Handling**: No Python tracebacks visible to users; errors appear as messages

---

## Recommendation for Next Iteration

**Priority fixes (User-facing)**:
1. Clearer Search vs Ask labeling (quick win)
2. Import path input with working directory display

**Enhancement fixes (Quality-of-life)**:
3. Better Ollama timeout messaging
4. Privacy summary during import
5. API health check "connecting..." state

**Future (Nice-to-have)**:
6. Splash screen for app startup
7. Duplicate import warning
8. Settings descriptions

All of these can be deferred - the app works correctly now.
