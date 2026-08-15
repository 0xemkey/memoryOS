from __future__ import annotations

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from apps.privacy_vault.dependencies import vault_store
from packages.vault_crypto.reveal import RevealDeniedError, RevealGateway, RevealRequest

app = FastAPI(title="MemoryOS Privacy Vault", version="0.1.0")


class ReviewCreateRequest(BaseModel):
    message_ref: str
    entity_type: str
    recommended_action: str
    confidence: float
    token: str | None = None


class ReviewActionRequest(BaseModel):
    action: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "privacy_vault", "milestone": "5"}


@app.post("/reveal")
def reveal(request: RevealRequest) -> dict:
    try:
        response = RevealGateway(vault_store()).reveal(request)
    except RevealDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return response.model_dump()


@app.get("/review-items")
def review_items() -> list[dict]:
    return [item.__dict__ for item in vault_store().list_review_items()]


@app.post("/review-items")
def create_review_item(request: ReviewCreateRequest) -> dict:
    return vault_store().create_review_item(**request.model_dump()).__dict__


@app.post("/review-items/{review_item_id}/approve")
def approve_review_item(review_item_id: str) -> dict:
    item = vault_store().update_review_item(review_item_id, status="approved")
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review item not found")
    return item.__dict__


@app.post("/review-items/{review_item_id}/change-action")
def change_review_item_action(review_item_id: str, request: ReviewActionRequest) -> dict:
    if not request.action:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="action is required")
    item = vault_store().update_review_item(review_item_id, status="changed", action=request.action)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review item not found")
    return item.__dict__


@app.post("/review-items/{review_item_id}/reject")
def reject_review_item(review_item_id: str) -> dict:
    item = vault_store().update_review_item(review_item_id, status="rejected")
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review item not found")
    return item.__dict__
