"""Phase 3 analytics: counts/groupings used by the dashboard view."""
from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, List

from ..models import DocumentRecord
from . import topics as topics_service
from . import locations as locations_service


_DECADE_RE = re.compile(r"\b(19|20)\d{2}\b")


def _decade_of(date_str: str | None) -> str | None:
    if not date_str:
        return None
    m = _DECADE_RE.search(date_str)
    if not m:
        return None
    year = int(m.group(0))
    decade = (year // 10) * 10
    return f"{decade}s"


def _bucket(counter: Counter) -> List[dict]:
    return [{"value": v, "count": c} for v, c in counter.most_common()]


def compute(docs: Iterable[DocumentRecord]) -> dict:
    docs_list = list(docs)
    by_agency = Counter((d.agency or "Unknown") for d in docs_list)
    by_file_type = Counter((d.file_type or "unknown") for d in docs_list)
    by_location = Counter((d.incident_location or "Unknown") for d in docs_list)
    by_incident_decade = Counter(
        (_decade_of(d.incident_date) or "Unknown") for d in docs_list
    )
    by_release_year = Counter(
        ((d.release_date or "")[:4] if d.release_date else "Unknown")
        for d in docs_list
    )
    by_redaction = Counter((d.redaction or "Unknown") for d in docs_list)

    location_confidence = Counter(
        locations_service.confidence_for(d.incident_location) for d in docs_list
    )

    has_image = sum(
        1 for d in docs_list if d.file_type == "image" or d.thumbnail_url
    )
    has_video = sum(1 for d in docs_list if d.file_type == "video" or d.dvids_video_id)
    unknown_dates = sum(1 for d in docs_list if not d.incident_date)
    unknown_locations = sum(1 for d in docs_list if not d.incident_location)

    topic_counts = topics_service.topic_counts(docs_list)
    topics_breakdown = [
        {
            "slug": t.slug,
            "title": t.title,
            "description": t.description,
            "count": topic_counts.get(t.slug, 0),
        }
        for t in topics_service.TOPIC_CATALOG
    ]

    return {
        "total_records": len(docs_list),
        "by_agency": _bucket(by_agency),
        "by_file_type": _bucket(by_file_type),
        "by_location": _bucket(by_location),
        "by_incident_decade": _bucket(by_incident_decade),
        "by_release_year": _bucket(by_release_year),
        "by_redaction": _bucket(by_redaction),
        "location_confidence": _bucket(location_confidence),
        "media_summary": {
            "with_image": has_image,
            "with_video": has_video,
            "unknown_dates": unknown_dates,
            "unknown_locations": unknown_locations,
        },
        "topics": topics_breakdown,
    }
