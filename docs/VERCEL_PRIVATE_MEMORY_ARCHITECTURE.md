# Vercel + Private Memory Architecture

## Goal

Deploy the MemoryOS web UI and a shared assistant surface to Vercel while keeping each user's memory isolated.

The rule is:

- Your account can reach your memory.
- Other accounts cannot read your memory.
- Other users can connect their own memory, either from their own local machine/IoT device or from a private per-user cloud store.
- Shared assistant behavior can live on Vercel, but memory retrieval must always be scoped to the authenticated user.

## Recommended Shape

```text
Browser
  -> Vercel hosted UI
  -> Auth session
  -> Jarves/Jerves assistant API
  -> user memory provider
       -> personal cloud namespace, or
       -> user's local MemoryOS API / device connector
```

Vercel should host the UI and the account-aware assistant layer. It should not contain one shared global vector database with everyone's history mixed together.

## Components

### Vercel UI

The React app in `apps/desktop` can be deployed as a static Vite site. It reads the API base URL in this order:

1. `?api=...` URL parameter
2. `VITE_API_URL`
3. previously saved `memoryos_api` local storage value
4. `http://127.0.0.1:8765`

This supports both hosted and local-first use.

### Auth

Use an identity provider before any memory endpoint is called. Good options:

- Vercel Marketplace auth integration
- Clerk
- Auth0
- Supabase Auth
- NextAuth/Auth.js if the hosted app is later moved to Next.js

The backend must derive `user_id` from the session, not from a request body.

### Memory Providers

Each authenticated user should have exactly one active memory provider:

- `local`: the user's browser talks to their own local MemoryOS API, usually `http://127.0.0.1:8765` or a trusted device URL.
- `cloud_private`: encrypted per-user memory and embeddings in a cloud database/vector store.
- `none`: no memory connected yet; the assistant still works without personal history.

For the local provider, run the API with:

```powershell
$env:MEMORYOS_CORS_ORIGINS="https://your-vercel-app.vercel.app,http://127.0.0.1:5173,http://localhost:5173"
.\scripts\run_api.ps1
```

### History Embeddings

The existing history embedding routes are under `/history-rag/*`.

For local mode:

- embeddings are computed locally
- Chroma data stays under `MEMORYOS_DATA_DIR/history_rag_db`
- Vercel stores no conversation text or vectors

For private cloud mode:

- vectors must be partitioned by authenticated `user_id`
- database rows must enforce owner checks
- raw uploads should be encrypted or discarded after indexing
- retrieval queries must always include the user's namespace/filter

### Shared Assistant

Jarves/Jerves should be split from memory:

- Shared assistant logic: prompts, tools, public knowledge, UI state
- Private memory: retrieved only after auth and only from the current user's memory provider

The assistant should receive retrieved snippets, not unrestricted database access.

## Privacy Requirements

- Never keep a default global memory namespace.
- Never allow a client-supplied `user_id` to select memory.
- Never return chunks unless the session owns the memory namespace.
- Keep destructive endpoints like `/data` behind auth and explicit confirmation.
- If local APIs are exposed through a tunnel or IoT device, require a device token in addition to browser auth.

## Deployment Notes

The repo now includes `vercel.json` for the static Vite UI:

```json
{
  "installCommand": "cd apps/desktop && npm ci",
  "buildCommand": "cd apps/desktop && npm run build",
  "outputDirectory": "apps/desktop/dist"
}
```

That deploys the UI only. Hosting the current Python local-first API directly on Vercel is not recommended because it depends on local SQLite files, Chroma/Ollama-style local runtime behavior, and filesystem-based personal memory.

## Next Implementation Steps

1. Add hosted auth to the Vercel app.
2. Add a memory-provider settings screen: local URL, cloud private, or none.
3. Require auth before any hosted Jarves/Jerves memory call.
4. Add a local device token for calls from the Vercel UI to a local MemoryOS API.
5. If cloud memory is needed, add per-user storage and vector namespaces before importing any real data.
