"""Phase 4 HTTP routes: evidence scoring, entities, reports, compare."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from ..auth import require_admin
from ..config import settings
from ..models import (
    CompareResponse,
    DocumentSummary,
    EntitiesResponse,
    EvidenceScoreResponse,
    Report,
    ReportRequest,
    ReportTemplatesResponse,
)
from ..services import entities as entities_service
from ..services import evidence as evidence_service
from ..services import reports as reports_service
from ..services.store import store


log = logging.getLogger(__name__)
router = APIRouter()


# --------------------------- Evidence ------------------------------------
@router.get("/api/documents/{document_id}/evidence", response_model=EvidenceScoreResponse)
def evidence_score(document_id: str) -> EvidenceScoreResponse:
    doc = store.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return EvidenceScoreResponse(**evidence_service.score_document(doc, store.documents))


# --------------------------- Entities ------------------------------------
@router.get("/api/entities", response_model=EntitiesResponse)
def entities() -> EntitiesResponse:
    return EntitiesResponse(**entities_service.aggregate(store.documents))


# --------------------------- Reports -------------------------------------
@router.get("/api/reports", response_model=ReportTemplatesResponse)
def list_report_templates() -> ReportTemplatesResponse:
    return ReportTemplatesResponse(templates=reports_service.list_templates())


@router.get("/api/reports/{slug}", response_model=Report)
def get_cached_report(slug: str) -> Report:
    cached = reports_service.get_cached(slug)
    if not cached:
        raise HTTPException(status_code=404, detail="No cached report for that slug")
    return Report(**cached)


@router.post("/api/reports/{slug}/generate", response_model=Report)
def generate_report(
    slug: str,
    req: Optional[ReportRequest] = None,
    _: None = Depends(require_admin),
) -> Report:
    """Generate (or force-regenerate) a report. Admin-only because each
    cache miss triggers a paid LLM call. Cached reports remain readable
    by anyone via GET /api/reports/{slug}.
    """
    req = req or ReportRequest()
    try:
        result = reports_service.generate(
            slug, document_ids=req.document_ids, force=req.force
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return Report(**result)


@router.get("/api/reports/{slug}/export.md", response_class=PlainTextResponse)
def export_report_markdown(slug: str) -> str:
    cached = reports_service.get_cached(slug)
    if not cached:
        raise HTTPException(status_code=404, detail="Report not generated yet")
    return reports_service.to_markdown(cached)


# --------------------------- Compare -------------------------------------
def _read_summary(doc_id: str) -> Optional[DocumentSummary]:
    p = settings.processed_root / "summaries" / f"{doc_id}.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return DocumentSummary(
            document_id=doc_id,
            summary=data.get("summary"),
            key_facts=data.get("key_facts", []) or [],
            evidence_types=data.get("evidence_types", []) or [],
            notable_locations=data.get("notable_locations", []) or [],
            notable_dates=data.get("notable_dates", []) or [],
            possible_topics=data.get("possible_topics", []) or [],
            uncertainty_notes=data.get("uncertainty_notes"),
            cached=True,
        )
    except Exception:
        return None


@router.get("/api/compare", response_model=CompareResponse)
def compare(
    ids: List[str] = Query(..., description="Two or more document IDs"),
) -> CompareResponse:
    if len(ids) < 2:
        raise HTTPException(status_code=400, detail="Provide at least two ids")
    docs = []
    for did in ids:
        d = store.get(did)
        if not d:
            raise HTTPException(status_code=404, detail=f"Document not found: {did}")
        docs.append(d)
    summaries = [_read_summary(d.document_id) for d in docs]
    scores = [
        EvidenceScoreResponse(**evidence_service.score_document(d, store.documents))
        for d in docs
    ]
    return CompareResponse(documents=docs, summaries=summaries, evidence_scores=scores)
