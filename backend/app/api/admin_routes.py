"""Phase 2 endpoints: admin auth, ingestion, index management, ask, summaries."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_admin, verify_password
from ..config import settings
from ..ingestion import pipeline as ingestion_pipeline
from ..ingestion import status as ingestion_status
from ..models import (
    AskRequest,
    AskResponse,
    DocumentSummary,
    IngestionRequest,
    LoginRequest,
    LoginResponse,
)
from ..services import search_index
from ..services.ask_service import ask as run_ask
from ..services.store import store

log = logging.getLogger(__name__)

router = APIRouter()


# ----------------------------------------------------------------- Admin auth
@router.post("/api/admin/login", response_model=LoginResponse)
def admin_login(req: LoginRequest) -> LoginResponse:
    if not settings.admin_password:
        raise HTTPException(status_code=503, detail="Admin password not configured.")
    if not verify_password(req.password):
        raise HTTPException(status_code=401, detail="Invalid password.")
    # Token is the password itself; admin endpoints validate via constant-time compare.
    return LoginResponse(token=req.password)


@router.get("/api/admin/whoami")
def whoami(_: None = Depends(require_admin)) -> dict:
    return {"role": "admin"}


# ---------------------------------------------------------------- Ingestion
@router.get("/api/ingestion/status")
def ingestion_status_route() -> dict:
    return ingestion_status.get_status()


@router.post("/api/ingestion/run")
def ingestion_run(
    req: IngestionRequest, _: None = Depends(require_admin)
) -> dict:
    return ingestion_pipeline.run_ingestion_async(
        document_ids=req.document_ids,
        max_docs=req.max_docs,
        ensure_index=req.ensure_index,
        summaries_only=req.summaries_only,
        regenerate_summaries=req.regenerate_summaries,
    )


# ----------------------------------------------------------------- Index mgmt
@router.get("/api/admin/index")
def index_info(_: None = Depends(require_admin)) -> dict:
    return search_index.index_stats()


@router.post("/api/admin/index/create")
def index_create(_: None = Depends(require_admin)) -> dict:
    return search_index.create_or_update_index()


@router.post("/api/admin/index/recreate")
def index_recreate(_: None = Depends(require_admin)) -> dict:
    return search_index.recreate_index()


# ---------------------------------------------------------------------- Ask
@router.post("/api/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    return run_ask(req)


# -------------------------------------------------------- Document summary/chunks
@router.get("/api/documents/{document_id}/summary", response_model=DocumentSummary)
def document_summary(document_id: str) -> DocumentSummary:
    if not store.get(document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    cached = ingestion_pipeline.get_cached_summary(document_id)
    if not cached:
        raise HTTPException(
            status_code=404,
            detail="Summary not yet generated. Run ingestion for this document first.",
        )
    return DocumentSummary(
        document_id=document_id,
        summary=cached.get("summary"),
        key_facts=cached.get("key_facts", []) or [],
        evidence_types=cached.get("evidence_types", []) or [],
        notable_locations=cached.get("notable_locations", []) or [],
        notable_dates=cached.get("notable_dates", []) or [],
        possible_topics=cached.get("possible_topics", []) or [],
        uncertainty_notes=cached.get("uncertainty_notes"),
        cached=True,
    )


@router.get("/api/documents/{document_id}/chunks")
def document_chunks(document_id: str, max_chunks: int = 50) -> dict[str, Any]:
    if not store.get(document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        chunks = search_index.get_document_chunks(document_id, max_chunks=max_chunks)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Search unavailable: {e}")
    return {"document_id": document_id, "count": len(chunks), "chunks": chunks}
