from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import os
import re
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from apps.api.memoryos_api.dependencies import embedder, reasoner, retriever, settings, store
from apps.api.memoryos_api.history_rag_router import router as history_rag_router
from apps.api.memoryos_api.schemas import (
    AskRequest,
    AskResponse,
    ImportRequest,
    ImportUploadRequest,
    ImportResponse,
    SearchRequest,
    SearchResponse,
    SettingsResponse,
)
from apps.api.memoryos_api.services import import_file
from apps.orchestrator.private_brain import PrivateBrainService, get_private_brain_config

app = FastAPI(title="MemoryOS Individual API", version="0.1.0")
cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "MEMORYOS_CORS_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(history_rag_router)
private_brain = PrivateBrainService()


def use_legacy() -> bool:
    return get_private_brain_config().use_legacy_mvp


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "local_first": True,
        "privacy": "Your conversations and documents remain on this device.",
        "memory_path": "legacy_mvp" if use_legacy() else "private_brain",
    }


@app.post("/imports", response_model=ImportResponse)
def create_import(request: ImportRequest) -> ImportResponse:
    if not use_legacy():
        path = Path(request.path).expanduser()
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import file not found")
        result = private_brain.import_file(path, request.provider)
        if result["status"] == "failed":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=result["failures"])
        return ImportResponse(
            job_id=result["job_id"],
            imported=result["imported_conversations"],
            skipped=0,
            duplicated=result["skipped_duplicates"],
            failed=0,
            errors=[],
            conversation_ids=[],
            stages=result["stages"],
            privacy_findings=result["privacy_findings"],
            sanitized_messages=result["sanitized_messages"],
            quarantined_messages=result["quarantined_messages"],
            chunks_indexed=result["chunks_indexed"],
        )
    path = Path(request.path).expanduser()
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import file not found")
    job_id = store.create_import_job(request.provider, str(path))
    report = import_file(path, request.provider, store, embedder)
    store.finish_import_job(job_id, report, status="failed" if report.failed and not report.imported else "completed")
    return ImportResponse(job_id=job_id, **report.model_dump())


@app.post("/imports/upload", response_model=ImportResponse)
def create_upload_import(request: ImportUploadRequest) -> ImportResponse:
    """Import a user-exported chat file without exposing a server filesystem path."""
    if len(request.content_base64) > 35 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="upload is limited to 25 MiB")
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(request.filename).name)[:120] or "chat-export.json"
    try:
        content = base64.b64decode(request.content_base64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="content_base64 is invalid") from exc
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="upload is limited to 25 MiB")
    suffix = Path(safe_name).suffix or ".json"
    with tempfile.NamedTemporaryFile(prefix="memoryos-import-", suffix=suffix, delete=False) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    try:
        if not use_legacy():
            result = private_brain.import_file(temp_path, request.provider)
            if result["status"] == "failed":
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=result["failures"])
            return ImportResponse(
                job_id=result["job_id"], imported=result["imported_conversations"], skipped=0,
                duplicated=result["skipped_duplicates"], failed=0, errors=[], conversation_ids=[],
                stages=result["stages"], privacy_findings=result["privacy_findings"],
                sanitized_messages=result["sanitized_messages"], quarantined_messages=result["quarantined_messages"],
                chunks_indexed=result["chunks_indexed"],
            )
        job_id = store.create_import_job(request.provider, safe_name)
        report = import_file(temp_path, request.provider, store, embedder)
        store.finish_import_job(job_id, report, status="failed" if report.failed and not report.imported else "completed")
        return ImportResponse(job_id=job_id, **report.model_dump())
    finally:
        temp_path.unlink(missing_ok=True)


@app.get("/imports/{job_id}")
def get_import(job_id: str) -> dict:
    job = store.get_import_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found")
    return job


@app.get("/conversations")
def conversations() -> list[dict]:
    if not use_legacy():
        return private_brain.list_conversations()
    return store.list_conversations()


@app.get("/conversations/{conversation_id}")
def conversation(conversation_id: str) -> dict:
    if not use_legacy():
        item = private_brain.get_conversation(conversation_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
        return item
    item = store.get_conversation(conversation_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return item


@app.post("/search", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    if not use_legacy():
        data = private_brain.search(
            request.query,
            filters=request.filters.model_dump(exclude_none=True) if request.filters else None,
            limit=request.limit,
        )
        return SearchResponse(results=data["results"], retrieval_mode=data["retrieval_mode"], warnings=data["warnings"])
    return SearchResponse(results=retriever.search(request.query, request.filters, request.limit))


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    if not use_legacy():
        data = private_brain.ask(
            request.query,
            filters=request.filters.model_dump(exclude_none=True) if request.filters else None,
            limit=request.limit or settings.retrieved_chunks,
        )
        return AskResponse(
            answer=data["answer"],
            citations=data["citations"],
            retrieved_context=data["retrieved_context"],
            sanitized_answer=data["sanitized_answer"],
            evidence_sufficient=data["evidence_sufficient"],
            retrieval_mode=data["retrieval_mode"],
            reasoning_mode=data["reasoning_mode"],
            warnings=data["warnings"],
        )
    results = retriever.search(request.query, request.filters, request.limit or settings.retrieved_chunks)
    answer = reasoner.answer(request.query, results)
    return AskResponse(**answer.model_dump())


@app.get("/settings", response_model=SettingsResponse)
def get_user_settings() -> SettingsResponse:
    return SettingsResponse(settings=store.get_settings())


@app.put("/settings", response_model=SettingsResponse)
def put_user_settings(values: dict) -> SettingsResponse:
    return SettingsResponse(settings=store.put_settings(values))


@app.post("/reindex")
def reindex() -> dict[str, str]:
    return {"status": "noop", "detail": "Imported chunks are indexed during import in this MVP slice."}


@app.post("/export")
def export() -> dict[str, str]:
    target = settings.data_dir / f"memoryos-export-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.zip"
    return {"archive_path": str(store.export_archive(target))}


@app.delete("/data")
def delete_data() -> dict:
    """Delete all MemoryOS data across all storage tiers.

    This operation deletes:
    - Legacy MVP database (if in use)
    - Normalized imports (raw imports before sanitization)
    - Sanitized conversations (pseudonymized content)
    - Vault mappings (encrypted entity values)
    - Vault keychain entry (encryption key)

    This is IRREVERSIBLE. Ensure the user has confirmed deletion before calling this.
    """
    results = {}

    # Delete legacy MVP data if in use
    if use_legacy():
        try:
            store.delete_all_data()
            results["legacy_mvp_deleted"] = True
        except Exception as exc:
            results["legacy_mvp_error"] = str(exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete legacy MVP data: {exc}",
            )
    else:
        results["legacy_mvp_deleted"] = False

    # Delete private-brain data (cascade across all 3 databases)
    private_brain_results = private_brain.delete_all_data()
    results.update(private_brain_results)

    # Check for failures
    if results.get("status") == "partial_failure":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Deletion partially failed. Errors: {results.get('errors', [])}",
        )

    # Recreate empty schema for all storage tiers
    # (delete_all_data removed schemas, so rebuild them for next operation)
    if results.get("normalized_deleted"):
        private_brain.normalized_store.migrate()
    if results.get("sanitized_deleted"):
        private_brain.sanitized_store.migrate()
    if results.get("vault_deleted"):
        private_brain.vault_store.migrate()

    if not all([
        results.get("legacy_mvp_deleted", False) or not use_legacy(),
        results.get("normalized_deleted", False),
        results.get("sanitized_deleted", False),
        results.get("vault_deleted", False),
        results.get("keychain_cleared", False),
    ]):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Some data stores failed to delete",
        )

    return {
        "status": "deleted",
        "detail": "All MemoryOS data has been securely deleted.",
        "results": results,
    }


@app.get("/diagnostics")
def diagnostics() -> dict:
    return private_brain.diagnostics()


@app.get("/graph")
def get_graph(min_edge_weight: int = 2, limit: int = 150, min_connections: int = 3) -> dict:
    """Get the conversation-level knowledge graph.

    Nodes are your chats; edges connect chats that share distinctive
    vocabulary, computed locally via tokenization and TF-IDF-style statistics
    (no LLM or external service involved).

    Query params:
    - min_edge_weight, limit, min_connections: accepted for API compatibility,
      currently unused by the conversation-level builder (which caps edges
      per node instead).

    Returns: {nodes, edges, generated_at, node_count, edge_count}
    """
    if not use_legacy():
        return private_brain.get_knowledge_graph(max_nodes=limit, min_edge_weight=min_edge_weight, min_node_connections=min_connections)
    # Legacy MVP does not have graph support
    return {"nodes": [], "edges": [], "generated_at": "", "node_count": 0, "edge_count": 0}


@app.post("/answers/reveal")
def reveal_answer(payload: dict) -> dict:
    answer = payload.get("sanitized_answer") or payload.get("answer")
    if not isinstance(answer, str):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="sanitized_answer is required")
    mode = payload.get("mode", "full")
    reveal_types = payload.get("reveal_types") or []
    return private_brain.reveal_answer(answer, mode=mode, reveal_types=reveal_types)
