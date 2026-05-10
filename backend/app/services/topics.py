"""Topic catalog + keyword-based classification for the Phase 3 topic pages.

Topic membership is derived from a record's title + description (and, when an
ingested summary is available on disk, the summary's text and key facts). This
keeps topic pages working without re-indexing.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from ..config import settings
from ..models import DocumentRecord


@dataclass(frozen=True)
class Topic:
    slug: str
    title: str
    description: str
    keywords: tuple[str, ...]


# Word-boundary keyword matching keeps "orb" from matching "orbit", etc.
TOPIC_CATALOG: List[Topic] = [
    Topic(
        slug="radar-cases",
        title="Radar cases",
        description="Records that reference radar tracks, returns, or contacts.",
        keywords=("radar", "radar return", "radar track", "radar contact"),
    ),
    Topic(
        slug="photographic-evidence",
        title="Photographic evidence",
        description="Records that include or reference photographs.",
        keywords=("photo", "photograph", "photographic", "still image", "snapshot"),
    ),
    Topic(
        slug="video-evidence",
        title="Video evidence",
        description="Records that include or reference video footage.",
        keywords=("video", "footage", "recording", "ftc", "flir", "atflir"),
    ),
    Topic(
        slug="disc-shaped",
        title="Disc-shaped objects",
        description="Records describing discs, saucers, or oval-shaped craft.",
        keywords=("disc", "disk", "saucer", "oval", "lenticular"),
    ),
    Topic(
        slug="orb-like",
        title="Orb-like objects",
        description="Records describing spheres, orbs, or ball-shaped objects.",
        keywords=("orb", "sphere", "spherical", "ball of light", "globe"),
    ),
    Topic(
        slug="military-witness",
        title="Military witness reports",
        description="Records authored by or describing military observers.",
        keywords=(
            "pilot",
            "aviator",
            "navy",
            "air force",
            "usaf",
            "marine",
            "army",
            "soldier",
            "service member",
            "range fouler",
            "mission report",
        ),
    ),
    Topic(
        slug="historical-fbi",
        title="Historical FBI files",
        description="Records released by the FBI from earlier decades.",
        keywords=("fbi",),
    ),
    Topic(
        slug="modern-sensor",
        title="Modern sensor cases",
        description="Records mentioning modern sensors such as IR, EO, or radar pods.",
        keywords=("sensor", "infrared", "ir", "eo/ir", "flir", "atflir", "radar pod"),
    ),
    Topic(
        slug="nuclear-sites",
        title="Nuclear site references",
        description="Records mentioning nuclear weapons, reactors, or sites.",
        keywords=("nuclear", "atomic", "reactor", "warhead", "icbm", "missile silo"),
    ),
    Topic(
        slug="unresolved",
        title="Unresolved records",
        description="Records explicitly noted as unresolved, unidentified, or anomalous.",
        keywords=(
            "unresolved",
            "unidentified",
            "anomalous",
            "unexplained",
            "could not be identified",
        ),
    ),
    Topic(
        slug="space-flight",
        title="Space flight observations",
        description="Records from Apollo, Skylab, Gemini, and other space missions.",
        keywords=("apollo", "gemini", "skylab", "lunar", "orbit", "astronaut"),
    ),
]


_SUMMARY_DIR = settings.processed_root / "summaries"


def _summary_text(doc: DocumentRecord) -> str:
    """Best-effort: include text from a cached AI summary if one exists."""
    p = _SUMMARY_DIR / f"{doc.document_id}.json"
    if not p.exists():
        return ""
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return ""
    parts: List[str] = []
    if data.get("summary"):
        parts.append(str(data["summary"]))
    for key in ("key_facts", "evidence_types", "possible_topics", "notable_locations"):
        v = data.get(key)
        if isinstance(v, list):
            parts.extend(str(x) for x in v)
    return " \n ".join(parts)


def _haystack(doc: DocumentRecord) -> str:
    parts = [
        doc.title or "",
        doc.description or "",
        doc.agency or "",
        doc.video_title or "",
        doc.incident_location or "",
        _summary_text(doc),
    ]
    return " ".join(parts).lower()


def _matches(haystack: str, keywords: Iterable[str]) -> bool:
    for kw in keywords:
        if " " in kw:
            # phrase, simple substring
            if kw in haystack:
                return True
        else:
            # word boundary
            if re.search(rf"\b{re.escape(kw)}\b", haystack):
                return True
    return False


def topics_for(doc: DocumentRecord) -> List[str]:
    """Return slugs of topics this document belongs to."""
    h = _haystack(doc)
    return [t.slug for t in TOPIC_CATALOG if _matches(h, t.keywords)]


def documents_for_topic(slug: str, docs: Iterable[DocumentRecord]) -> List[DocumentRecord]:
    topic = next((t for t in TOPIC_CATALOG if t.slug == slug), None)
    if not topic:
        return []
    return [d for d in docs if _matches(_haystack(d), topic.keywords)]


def topic_counts(docs: Iterable[DocumentRecord]) -> Dict[str, int]:
    docs_list = list(docs)
    counts: Dict[str, int] = {}
    for t in TOPIC_CATALOG:
        counts[t.slug] = sum(1 for d in docs_list if _matches(_haystack(d), t.keywords))
    return counts


def get_topic(slug: str) -> Optional[Topic]:
    return next((t for t in TOPIC_CATALOG if t.slug == slug), None)
