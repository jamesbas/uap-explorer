"""Evidence quality scoring per the Phase 4 spec.

This score represents *record completeness* only. It MUST NOT be interpreted as
"alien likelihood" or as a measure of whether a UAP is real. Each dimension is
graded 0–10 from the metadata available on the record (and any cached AI
summary if one exists).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from ..config import settings
from ..models import DocumentRecord


_SUMMARY_DIR = settings.processed_root / "summaries"

_FULL_DATE_RE = re.compile(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b")
_YEAR_ONLY_RE = re.compile(r"^\s*\d{4}\s*$")


@dataclass
class Dimension:
    name: str
    label: str
    score: int  # 0..10
    rationale: str


def _load_summary(doc_id: str) -> Optional[dict]:
    p = _SUMMARY_DIR / f"{doc_id}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _date_quality(date_str: Optional[str]) -> Dimension:
    if not date_str:
        return Dimension("date_quality", "Date quality", 0, "No incident date provided.")
    if _FULL_DATE_RE.search(date_str):
        return Dimension("date_quality", "Date quality", 10, "Specific date recorded.")
    if "-" in date_str or "/" in date_str:
        return Dimension("date_quality", "Date quality", 7, "Partial date (month/year).")
    if _YEAR_ONLY_RE.match(date_str):
        return Dimension("date_quality", "Date quality", 4, "Year only.")
    return Dimension("date_quality", "Date quality", 3, f"Unstructured date: '{date_str}'.")


# Lifted from locations.py confidence labels
_LOC_SCORE = {
    "exact": 10,
    "approximate": 6,
    "broad": 4,
    "off-earth": 6,
    "unknown": 0,
}


def _location_quality(doc: DocumentRecord) -> Dimension:
    from . import locations as locations_service

    conf = locations_service.confidence_for(doc.incident_location)
    score = _LOC_SCORE.get(conf, 0)
    if not doc.incident_location:
        return Dimension("location_quality", "Location quality", 0, "No location provided.")
    return Dimension(
        "location_quality",
        "Location quality",
        score,
        f"Location '{doc.incident_location}' classified as {conf}.",
    )


# Higher trust-of-process for primary government sources.
_AGENCY_SCORE = {
    "department of war": 9,
    "department of defense": 9,
    "fbi": 8,
    "nasa": 9,
    "department of state": 7,
}


def _source_quality(doc: DocumentRecord) -> Dimension:
    if not doc.agency:
        return Dimension("source_quality", "Source quality", 3, "Agency unknown.")
    score = _AGENCY_SCORE.get(doc.agency.lower(), 6)
    return Dimension(
        "source_quality",
        "Source quality",
        score,
        f"Released by {doc.agency}.",
    )


def _media_support(doc: DocumentRecord, summary: Optional[dict]) -> Dimension:
    has_video = bool(doc.dvids_video_id) or doc.file_type == "video"
    has_image = doc.file_type == "image" or bool(doc.thumbnail_url)
    et: List[str] = (summary or {}).get("evidence_types", []) or []
    et_lower = " ".join(et).lower()
    has_sensor = any(k in et_lower for k in ("radar", "sensor", "ir", "infrared", "flir", "atflir"))

    score = 0
    bits: List[str] = []
    if has_video:
        score += 5
        bits.append("video")
    if has_image:
        score += 3
        bits.append("image")
    if has_sensor:
        score += 4
        bits.append("sensor reference")
    score = min(10, score)
    if not bits:
        return Dimension("media_support", "Media support", 1, "No media or sensor evidence found.")
    return Dimension(
        "media_support",
        "Media support",
        score,
        "Includes: " + ", ".join(bits) + ".",
    )


def _witness_support(doc: DocumentRecord, summary: Optional[dict]) -> Dimension:
    text = " ".join(
        [
            doc.title or "",
            doc.description or "",
            (summary or {}).get("summary", "") or "",
            " ".join((summary or {}).get("key_facts", []) or []),
        ]
    ).lower()
    multi_terms = [
        "witnesses",
        "multiple",
        "crew",
        "several",
        "passengers",
        "officers",
        "personnel",
    ]
    single_terms = ["witness", "pilot", "observer", "operator", "reporter"]
    if any(t in text for t in multi_terms):
        return Dimension("witness_support", "Witness support", 8, "Multiple witnesses suggested.")
    if any(t in text for t in single_terms):
        return Dimension("witness_support", "Witness support", 5, "Single witness suggested.")
    return Dimension("witness_support", "Witness support", 2, "No explicit witness reference.")


_REDACTION_SCORE = {
    "none": 10,
    "low": 8,
    "medium": 5,
    "moderate": 5,
    "high": 2,
    "heavy": 2,
}


def _redaction_level(doc: DocumentRecord) -> Dimension:
    if not doc.redaction:
        return Dimension("redaction_level", "Redaction level", 6, "Redaction not specified.")
    score = _REDACTION_SCORE.get(doc.redaction.lower(), 6)
    return Dimension(
        "redaction_level",
        "Redaction level",
        score,
        f"Redaction noted as '{doc.redaction}'.",
    )


def _corroboration(doc: DocumentRecord, all_docs: List[DocumentRecord]) -> Dimension:
    """Counts other records sharing the same incident location and a near date."""
    if not doc.incident_location:
        return Dimension(
            "corroboration", "Corroboration", 2, "No location to correlate against."
        )
    same_loc = [
        d
        for d in all_docs
        if d.document_id != doc.document_id
        and (d.incident_location or "").lower() == doc.incident_location.lower()
    ]
    n = len(same_loc)
    if n >= 5:
        score = 10
    elif n >= 2:
        score = 7
    elif n == 1:
        score = 5
    else:
        score = 2
    return Dimension(
        "corroboration",
        "Corroboration",
        score,
        f"{n} other record(s) share the location '{doc.incident_location}'.",
    )


def _resolution(doc: DocumentRecord, summary: Optional[dict]) -> Dimension:
    text = " ".join(
        [
            doc.title or "",
            doc.description or "",
            (summary or {}).get("summary", "") or "",
            (summary or {}).get("uncertainty_notes", "") or "",
        ]
    ).lower()
    if any(t in text for t in ("identified as", "confirmed", "explained as", "resolved")):
        return Dimension("resolution", "Resolution", 9, "Source indicates resolution.")
    if any(
        t in text
        for t in (
            "unresolved",
            "unidentified",
            "unexplained",
            "could not be identified",
            "anomalous",
        )
    ):
        return Dimension("resolution", "Resolution", 3, "Source notes unresolved status.")
    return Dimension("resolution", "Resolution", 5, "Resolution status not stated.")


def score_document(doc: DocumentRecord, all_docs: List[DocumentRecord]) -> dict:
    summary = _load_summary(doc.document_id)
    dims = [
        _date_quality(doc.incident_date),
        _location_quality(doc),
        _source_quality(doc),
        _media_support(doc, summary),
        _witness_support(doc, summary),
        _redaction_level(doc),
        _corroboration(doc, all_docs),
        _resolution(doc, summary),
    ]
    overall = round(sum(d.score for d in dims) / len(dims), 1)
    return {
        "document_id": doc.document_id,
        "overall_score": overall,
        "max_score": 10.0,
        "dimensions": [
            {
                "name": d.name,
                "label": d.label,
                "score": d.score,
                "rationale": d.rationale,
            }
            for d in dims
        ],
        "disclaimer": (
            "This score reflects record completeness only — it does NOT represent "
            "the likelihood that an event was extraterrestrial."
        ),
    }
