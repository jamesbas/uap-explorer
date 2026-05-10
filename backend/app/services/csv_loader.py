"""CSV ingestion for Phase 1.

Loads the government UAP archive CSV, normalizes rows into DocumentRecord
objects, and provides helpers for searching and filtering.
"""
from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path
from typing import Iterable, List, Optional

from ..models import DocumentRecord

# Canonical column names we care about. The source CSV has trailing empty
# columns that we ignore.
COL_REDACTION = "Redaction"
COL_RELEASE_DATE = "Release Date"
COL_TITLE = "Title"
COL_TYPE = "Type"
COL_VIDEO_PAIRING = "Video Pairing"
COL_PDF_PAIRING = "PDF Pairing"
COL_DESCRIPTION = "Description Blurb"
COL_DVIDS_ID = "DVIDS Video ID"
COL_VIDEO_TITLE = "Video Title"
COL_AGENCY = "Agency"
COL_INCIDENT_DATE = "Incident Date"
COL_INCIDENT_LOCATION = "Incident Location"
COL_PDF_IMAGE_LINK = "PDF | Image Link"
COL_MODAL_IMAGE = "Modal Image"

UNKNOWN_TOKENS = {"", "n/a", "na", "none", "unknown", "null", "-"}


def _clean(value: Optional[str]) -> Optional[str]:
    """Trim whitespace/newlines; treat blank/sentinel tokens as None."""
    if value is None:
        return None
    cleaned = value.strip().strip('"').strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if cleaned.lower() in UNKNOWN_TOKENS:
        return None
    return cleaned


def _infer_file_type(raw_type: Optional[str], source_url: Optional[str]) -> Optional[str]:
    if raw_type:
        t = raw_type.strip().lower()
        if t in {"pdf", "image", "video"}:
            return t
    if source_url:
        url = source_url.lower()
        if url.endswith(".pdf"):
            return "pdf"
        if url.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
            return "image"
        if url.endswith((".mp4", ".mov", ".avi", ".mkv")):
            return "video"
    return None


def _local_path_for(source_url: Optional[str], file_root: Path) -> Optional[str]:
    """If a matching local file exists for the given URL, return its absolute path."""
    if not source_url:
        return None
    try:
        filename = source_url.rsplit("/", 1)[-1]
    except Exception:
        return None
    if not filename:
        return None
    candidate = file_root / filename
    if candidate.exists():
        return str(candidate)
    return None


def _document_id(title: Optional[str], source_url: Optional[str]) -> str:
    """Stable, content-derived id."""
    basis = f"{title or ''}|{source_url or ''}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def load_documents(csv_path: Path, file_root: Path) -> List[DocumentRecord]:
    """Load and normalize document records from the source CSV."""
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    records: List[DocumentRecord] = []
    seen_ids: set[str] = set()

    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            title = _clean(row.get(COL_TITLE))
            source_url = _clean(row.get(COL_PDF_IMAGE_LINK))

            # Skip empty rows (no title and no source).
            if not title and not source_url:
                continue

            doc_id = _document_id(title, source_url)
            # If duplicate ids appear, append a counter to keep them unique.
            if doc_id in seen_ids:
                suffix = 2
                while f"{doc_id}-{suffix}" in seen_ids:
                    suffix += 1
                doc_id = f"{doc_id}-{suffix}"
            seen_ids.add(doc_id)

            file_type = _infer_file_type(_clean(row.get(COL_TYPE)), source_url)
            local_path = _local_path_for(source_url, file_root)

            records.append(
                DocumentRecord(
                    document_id=doc_id,
                    title=title or "Untitled record",
                    release_date=_clean(row.get(COL_RELEASE_DATE)),
                    incident_date=_clean(row.get(COL_INCIDENT_DATE)),
                    incident_location=_clean(row.get(COL_INCIDENT_LOCATION)),
                    agency=_clean(row.get(COL_AGENCY)),
                    file_type=file_type,
                    source_url=source_url,
                    local_file_path=local_path,
                    thumbnail_url=_clean(row.get(COL_MODAL_IMAGE)),
                    description=_clean(row.get(COL_DESCRIPTION)),
                    redaction=_clean(row.get(COL_REDACTION)),
                    video_title=_clean(row.get(COL_VIDEO_TITLE)),
                    dvids_video_id=_clean(row.get(COL_DVIDS_ID)),
                )
            )

    return records


def search_documents(
    docs: Iterable[DocumentRecord],
    query: Optional[str] = None,
    agency: Optional[str] = None,
    file_type: Optional[str] = None,
    incident_location: Optional[str] = None,
    release_date: Optional[str] = None,
) -> List[DocumentRecord]:
    """Apply a case-insensitive keyword search and metadata filters."""
    q = query.strip().lower() if query else None

    def _matches(d: DocumentRecord) -> bool:
        if agency and (d.agency or "").lower() != agency.lower():
            return False
        if file_type and (d.file_type or "").lower() != file_type.lower():
            return False
        if incident_location and (d.incident_location or "").lower() != incident_location.lower():
            return False
        if release_date and (d.release_date or "") != release_date:
            return False
        if q:
            haystack = " ".join(
                [
                    d.title or "",
                    d.description or "",
                    d.agency or "",
                    d.incident_location or "",
                    d.incident_date or "",
                    d.release_date or "",
                    d.file_type or "",
                ]
            ).lower()
            if q not in haystack:
                return False
        return True

    return [d for d in docs if _matches(d)]
