# MemoryOS: First-Run Setup (5-10 Minutes)

Your conversations and documents remain on this device. Complete setup, import your first ChatGPT export, and ask a question.

## Prerequisites

- **Python 3.11+** — Check: `python --version`
- **Git** — To clone the repository
- **Node.js 18+** — For the desktop UI (check: `node --version`, `npm --version`)
- **Ollama (optional)** — For local AI reasoning. If not installed, the app uses keyword-based answers with no quality loss.

If Ollama is not installed, the app will still work but will show deterministic answers based on keyword matching and evidence snippets.

## Step 1: Clone and Install (2 minutes)

```bash
# Clone the repository
git clone https://github.com/anthropics/MemoryOS.git
cd MemoryOS

# Create a Python virtual environment
python -m venv .venv

# Activate it
# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# On Linux/Mac (bash):
source .venv/bin/activate

# Install MemoryOS
pip install -e ".[dev]"

# Copy the example environment config
cp .env.example .env
# (on Windows PowerShell: Copy-Item .env.example .env)
```

**Expected output**: `Successfully installed memoryos...` (no errors)

## Step 2: Start the API Server (1 minute)

The API runs locally on port 8765.

**Option A: PowerShell (Windows)**
```powershell
.\scripts\run_api.ps1
```

**Option B: bash (Linux/Mac)**
```bash
PYTHONPATH=. python -m uvicorn apps.api.memoryos_api.main:app --reload --host 127.0.0.1 --port 8765
```

**Expected output**:
```
Uvicorn running on http://127.0.0.1:8765
Application startup complete
```

**Keep this terminal open.** Open a NEW terminal/tab for the next step.

## Step 3: Start the Desktop UI (2 minutes)

In a NEW terminal/tab (keep API server running in the first one):

```bash
cd apps/desktop

# Install dependencies (one-time)
npm install

# Start development server
npm run dev
```

**Expected output**:
```
VITE v... dev server running at:

➜  Local:   http://127.0.0.1:5173/
```

Open http://127.0.0.1:5173 in your browser.

**Check the status bar** (bottom-left of the app): It should show `http://127.0.0.1:8765: ready` (not red).
- If it says "Start the local API", the API server didn't start. Go back to Step 2.

## Step 4: Import Sample Data (2 minutes)

**Option A: Via the UI (Easiest)**

1. Click **Imports** in the sidebar
2. In "Absolute path to export file", enter: `./sample_data/chatgpt_sample.json`
3. Provider: Choose **ChatGPT** (pre-selected)
4. Click **Import**

Wait for "Imported X, sanitized Y, chunks Z" message.

**Option B: Via command line (if UI import fails)**

In a NEW terminal (API must still be running):

```powershell
# PowerShell
$body = @{ path = "$PWD/sample_data/chatgpt_sample.json"; provider = "chatgpt" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/imports `
  -Body $body -ContentType "application/json" | ConvertTo-Json
```

## Step 5: Ask Your First Question (1 minute)

1. In the app, type a question in the search bar: `What topics does the sample data discuss?`
2. Click **Ask**
3. You'll see:
   - **Answer**: A summary of topics from the imported conversations
   - **Sources**: The snippets it used (with source IDs)
   - **Reasoning mode**: "deterministic_fallback" (if Ollama isn't running) or "ollama" (if it is)

**No evidence available?** This means either:
- The import didn't complete (check the status in the Imports tab)
- The sample file is empty (unlikely - try the provided sample files)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Start the local API on http://127.0.0.1:8765" in the UI | API server didn't start. Re-run Step 2. |
| Import fails with file not found | Use absolute path: `/Users/yourname/MemoryOS/sample_data/chatgpt_sample.json` (not relative `./`) |
| "No evidence available" answer | Check Imports tab — confirm data was imported. |
| Slow first search/ask | Ollama starting up for the first time. Wait 10-30 seconds. |
| Ollama timeout | Ollama not installed/running. App will use keyword-based answers (slower but still works). |

## Next Steps

- **Import your own data**: Use the Imports tab with a ChatGPT, Claude, or generic JSON export.
- **Settings**: Configure Ollama URL or chat model in the Settings tab (default: `http://localhost:11434`, model: `llama3.1`).
- **Privacy**: Your data never leaves this device. Conversations are encrypted in the vault after import.
- **Delete data**: Click "Delete Local Data" in Settings (irreversible).

## Important: Search Quality Without Ollama

Without Ollama installed, the app uses **keyword-only search** as a fallback. This works fine for small, focused imports (a handful of related conversations), but has limitations:

- **Quality degradation with diverse data**: In a mixed-topic corpus (e.g., robot discussions + Python code + cooking tips), keyword matching can surface unrelated results. Testing showed ~50% noise rate when searching a diverse 6-conversation corpus.
- **Why**: Keyword matching finds any chunk containing query words (e.g., "decision" in both "robot control decision" and "Q4 planning decision") without understanding semantic relevance.
- **Recommendation**: If you're importing large or varied conversation histories, install Ollama. If you have just a few focused conversations, keyword-only mode is fine.

## Optional: Install Ollama for Semantic Search & Better Reasoning

If you want semantic understanding + smarter answers (not just keyword summaries):

1. Download Ollama from https://ollama.ai
2. Install and run it (it starts on http://localhost:11434 by default)
3. Pull a model: `ollama pull llama3.1` (one-time, ~4GB download)
4. Restart the MemoryOS app (no config changes needed)

The app detects Ollama automatically on the next `/ask` or `/search` call. With Ollama active:
- Search quality improves dramatically (semantic understanding, not just keywords)
- Answers become smarter and more accurate

---

**You now have MemoryOS running locally.** Your first import and question should take ~5-10 minutes total.
