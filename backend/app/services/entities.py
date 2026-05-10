"""Deterministic entity extraction over metadata + cached AI summaries.

This avoids new LLM calls — entities are pulled from the structured CSV fields
plus keyword/regex patterns over titles, descriptions, and any cached summary
text. Spec entity types covered:

    Agencies, Locations, People (rare in metadata),
    Aircraft, Bases, Sensor systems, Object descriptions, Projects, Events
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from ..config import settings
from ..models import DocumentRecord


_SUMMARY_DIR = settings.processed_root / "summaries"


@dataclass(frozen=True)
class EntityPattern:
    type: str
    label: str
    pattern: re.Pattern[str]
    canonical: str


def _kw(type_: str, label: str, *aliases: str) -> EntityPattern:
    """Word-boundary OR-match across aliases (case insensitive)."""
    parts = "|".join(re.escape(a) for a in aliases)
    return EntityPattern(
        type=type_,
        label=label,
        pattern=re.compile(rf"\b(?:{parts})\b", re.IGNORECASE),
        canonical=label,
    )


PATTERNS: List[EntityPattern] = [
    # Aircraft / spacecraft
    _kw("aircraft", "F/A-18 Super Hornet", "f/a-18", "fa-18", "super hornet", "f-18"),
    _kw("aircraft", "F-35", "f-35", "lightning ii"),
    _kw("aircraft", "MQ-9 Reaper", "mq-9", "reaper"),
    _kw("aircraft", "P-8 Poseidon", "p-8", "poseidon"),
    _kw("spacecraft", "Apollo Command Module", "apollo command", "command module"),
    _kw("spacecraft", "Apollo (mission)", "apollo 11", "apollo 12", "apollo 17"),
    _kw("spacecraft", "Skylab", "skylab"),
    _kw("spacecraft", "Gemini", "gemini 7", "gemini-7"),
    # Sensor systems
    _kw("sensor", "ATFLIR", "atflir"),
    _kw("sensor", "FLIR", "flir"),
    _kw("sensor", "Radar", "radar"),
    _kw("sensor", "Infrared", "infrared", "ir camera", "ir sensor"),
    _kw("sensor", "EO/IR turret", "eo/ir", "electro-optical"),
    # Bases / sites
    _kw("base", "Naval Air Station Oceana", "nas oceana", "oceana"),
    _kw("base", "Naval Air Station Lemoore", "nas lemoore", "lemoore"),
    _kw("base", "Camp Lemonnier", "camp lemonnier"),
    _kw("base", "Wright-Patterson AFB", "wright-patterson", "wright patterson"),
    _kw("base", "Edwards AFB", "edwards afb", "edwards air force"),
    _kw("base", "Cannon AFB", "cannon afb"),
    # Projects / programs
    _kw("project", "Project Blue Book", "blue book"),
    _kw("project", "AARO", "aaro", "all-domain anomaly resolution office"),
    _kw("project", "AATIP", "aatip"),
    _kw("project", "UAP Task Force", "uap task force", "uaptf"),
    _kw("project", "Project Sign", "project sign"),
    _kw("project", "Project Grudge", "project grudge"),
    # Object descriptions
    _kw("object_shape", "Disc / saucer", "disc", "disk", "saucer"),
    _kw("object_shape", "Sphere / orb", "orb", "sphere", "spherical"),
    _kw("object_shape", "Tic-Tac", "tic tac", "tic-tac"),
    _kw("object_shape", "Cigar-shaped", "cigar"),
    _kw("object_shape", "Triangle", "triangular", "triangle"),
    _kw("object_shape", "Cylinder", "cylindrical", "cylinder"),
    # Event categories
    _kw("event", "Range Fouler", "range fouler"),
    _kw("event", "Mission Report", "mission report"),
    _kw("event", "Radar contact", "radar contact", "radar return"),
]


def _summary_text(doc_id: str) -> str:
    p = _SUMMARY_DIR / f"{doc_id}.json"
    if not p.exists():
        return ""
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return ""
    parts: list[str] = []
    if data.get("summary"):
        parts.append(str(data["summary"]))
    for k in ("key_facts", "evidence_types", "possible_topics", "notable_locations", "notable_dates"):
        v = data.get(k)
        if isinstance(v, list):
            parts.extend(str(x) for x in v)
    return " ".join(parts)


def _haystack(doc: DocumentRecord) -> str:
    return " ".join(
        [
            doc.title or "",
            doc.description or "",
            doc.video_title or "",
            _summary_text(doc.document_id),
        ]
    )


def extract_for(doc: DocumentRecord) -> Dict[str, List[dict]]:
    """Return entities grouped by type for a single document."""
    groups: Dict[str, List[dict]] = defaultdict(list)
    text = _haystack(doc)

    if doc.agency:
        groups["agency"].append({"label": doc.agency, "canonical": doc.agency})
    if doc.incident_location:
        groups["location"].append(
            {"label": doc.incident_location, "canonical": doc.incident_location}
        )
    if doc.incident_date:
        groups["date"].append({"label": doc.incident_date, "canonical": doc.incident_date})

    seen: set[tuple[str, str]] = set()
    for pat in PATTERNS:
        if pat.pattern.search(text):
            key = (pat.type, pat.canonical)
            if key in seen:
                continue
            seen.add(key)
            groups[pat.type].append({"label": pat.label, "canonical": pat.canonical})

    return dict(groups)


def aggregate(docs: Iterable[DocumentRecord]) -> dict:
    """Cross-archive entity index. Returns:
    {
      "types": [ { "type": "...", "entities": [ {label, canonical, count, document_ids[]}, ... ] } ],
      "total_documents": N
    }
    """
    docs_list = list(docs)
    by_type: Dict[str, Dict[str, dict]] = defaultdict(dict)

    for d in docs_list:
        ents = extract_for(d)
        for t, items in ents.items():
            for item in items:
                key = item["canonical"]
                bucket = by_type[t].setdefault(
                    key,
                    {
                        "label": item["label"],
                        "canonical": key,
                        "count": 0,
                        "document_ids": [],
                    },
                )
                bucket["count"] += 1
                bucket["document_ids"].append(d.document_id)

    types_out = []
    for t, bucket in sorted(by_type.items()):
        items = sorted(
            bucket.values(), key=lambda x: (-x["count"], x["label"].lower())
        )
        types_out.append({"type": t, "entities": items})
    return {"types": types_out, "total_documents": len(docs_list)}
