"""HTTP API for Phase 1."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse

from ..config import settings
from ..models import (
    DocumentListResponse,
    DocumentRecord,
    FacetValue,
    FacetsResponse,
    StatsResponse,
)
from ..services.csv_loader import search_documents
from ..services.store import store

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "documents_loaded": len(store.documents)}


@router.get("/api/documents", response_model=DocumentListResponse)
def list_documents(
    query: Optional[str] = Query(None, description="Keyword search"),
    agency: Optional[str] = None,
    file_type: Optional[str] = None,
    incident_location: Optional[str] = None,
    release_date: Optional[str] = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
) -> DocumentListResponse:
    results = search_documents(
        store.documents,
        query=query,
        agency=agency,
        file_type=file_type,
        incident_location=incident_location,
        release_date=release_date,
    )
    sliced = results[offset : offset + limit]
    return DocumentListResponse(
        total=len(results),
        count=len(sliced),
        offset=offset,
        limit=limit,
        items=sliced,
    )


@router.get("/api/documents/{document_id}", response_model=DocumentRecord)
def get_document(document_id: str) -> DocumentRecord:
    doc = store.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/api/documents/{document_id}/file")
def get_document_file(document_id: str):
    doc = store.get(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Prefer local file when present
    if doc.local_file_path:
        p = Path(doc.local_file_path)
        if p.exists():
            return FileResponse(str(p), filename=p.name)

    # Fall back to Azure Blob Storage if configured
    blob_name = None
    if doc.local_file_path:
        blob_name = Path(doc.local_file_path).name
    elif doc.source_url:
        blob_name = doc.source_url.rsplit("/", 1)[-1]

    if blob_name:
        try:
            from ..services import blob_storage

            if blob_storage.blob_exists(blob_name):
                chunks, size = blob_storage.download_blob_stream(blob_name)
                # Best-effort content type
                ext = Path(blob_name).suffix.lower()
                ctype = {
                    ".pdf": "application/pdf",
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".gif": "image/gif",
                    ".mp4": "video/mp4",
                }.get(ext, "application/octet-stream")
                headers = {"Content-Disposition": f'inline; filename="{blob_name}"'}
                if size:
                    headers["Content-Length"] = str(size)
                return StreamingResponse(chunks, media_type=ctype, headers=headers)
        except Exception:
            pass

    raise HTTPException(status_code=404, detail="File not available locally or in blob storage")


@router.get("/api/search", response_model=DocumentListResponse)
def search(
    query: str = Query("", description="Keyword search"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
) -> DocumentListResponse:
    results = search_documents(store.documents, query=query or None)
    sliced = results[offset : offset + limit]
    return DocumentListResponse(
        total=len(results),
        count=len(sliced),
        offset=offset,
        limit=limit,
        items=sliced,
    )


def _facet(values, top: int = 50) -> list[FacetValue]:
    counter = Counter(v for v in values if v)
    return [FacetValue(value=v, count=c) for v, c in counter.most_common(top)]


@router.get("/api/facets", response_model=FacetsResponse)
def facets() -> FacetsResponse:
    docs = store.documents
    return FacetsResponse(
        agency=_facet(d.agency for d in docs),
        file_type=_facet(d.file_type for d in docs),
        incident_location=_facet(d.incident_location for d in docs),
        release_date=_facet(d.release_date for d in docs),
    )


@router.get("/api/stats", response_model=StatsResponse)
def stats() -> StatsResponse:
    docs = store.documents
    type_counts = Counter((d.file_type or "other") for d in docs)
    release_dates = sorted({d.release_date for d in docs if d.release_date})
    return StatsResponse(
        total_records=len(docs),
        pdfs=type_counts.get("pdf", 0),
        images=type_counts.get("image", 0),
        videos=type_counts.get("video", 0),
        other=sum(c for t, c in type_counts.items() if t not in {"pdf", "image", "video"}),
        agencies=len({d.agency for d in docs if d.agency}),
        known_locations=sum(1 for d in docs if d.incident_location),
        known_incident_dates=sum(1 for d in docs if d.incident_date),
        release_date_min=release_dates[0] if release_dates else None,
        release_date_max=release_dates[-1] if release_dates else None,
    )
