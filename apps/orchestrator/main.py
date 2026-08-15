from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from apps.orchestrator.dependencies import normalized_store

app = FastAPI(title="MemoryOS Orchestrator", version="0.1.0")


class ImportRequest(BaseModel):
    path: str
    provider: str = "auto"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "orchestrator", "milestone": "1"}


@app.post("/imports")
def create_import(request: ImportRequest) -> dict:
    path = Path(request.path).expanduser()
    job = normalized_store.import_path(path, request.provider)
    if job.status == "failed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[failure.model_dump() for failure in job.failures],
        )
    return job.model_dump(mode="json")


@app.get("/imports")
def list_imports() -> list[dict]:
    return [job.model_dump(mode="json") for job in normalized_store.list_imports()]


@app.get("/imports/{job_id}")
def get_import(job_id: str) -> dict:
    for job in normalized_store.list_imports():
        if job.job_id == job_id:
            return job.model_dump(mode="json")
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found")


@app.get("/conversations")
def list_conversations() -> list[dict]:
    return normalized_store.list_conversations()


@app.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str) -> dict:
    conversation = normalized_store.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation
