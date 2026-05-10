"""Phase 3 HTTP routes: map, timeline, media gallery, topics, analytics."""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..models import (
    AnalyticsResponse,
    MapMarker,
    MapResponse,
    MediaItem,
    MediaResponse,
    TimelineEntry,
    TimelineResponse,
    TopicDetailResponse,
    TopicSummary,
    TopicsResponse,
)
from ..services import analytics as analytics_service
from ..services import locations as locations_service
from ..services import topics as topics_service
from ..services.store import store


router = APIRouter()


# --------------------------- Map -----------------------------------------
@router.get("/api/map", response_model=MapResponse)
def map_view() -> MapResponse:
    docs = store.documents
    grouped: dict[str, list[str]] = defaultdict(list)
    unmapped: dict[str, int] = defaultdict(int)

    for d in docs:
        if not d.incident_location:
            unmapped["__none__"] += 1
            continue
        coord = locations_service.lookup(d.incident_location)
        if coord is None:
            unmapped[d.incident_location] += 1
            continue
        grouped[d.incident_location].append(d.document_id)

    markers: list[MapMarker] = []
    for raw_loc, ids in grouped.items():
        coord = locations_service.lookup(raw_loc)
        if not coord:
            continue
        markers.append(
            MapMarker(
                location=raw_loc,
                label=coord.label,
                lat=coord.lat,
                lon=coord.lon,
                confidence=coord.confidence,
                count=len(ids),
                document_ids=ids,
            )
        )

    markers.sort(key=lambda m: m.count, reverse=True)
    unmapped_list = sorted(k for k in unmapped.keys() if k != "__none__")
    return MapResponse(
        markers=markers,
        unmapped=unmapped_list,
        unmapped_count=sum(unmapped.values()),
    )


# --------------------------- Timeline ------------------------------------
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def _date_sort_key(s: str | None) -> str:
    """Best-effort sortable key. Year-only strings sort by year; explicit
    YYYY-MM-DD strings keep natural order."""
    if not s:
        return ""
    m = _YEAR_RE.search(s)
    if m:
        return m.group(0) + s  # year first
    return s


def _entry(doc, date: str) -> TimelineEntry:
    return TimelineEntry(
        document_id=doc.document_id,
        title=doc.title,
        agency=doc.agency,
        date=date,
        file_type=doc.file_type,
        incident_location=doc.incident_location,
        thumbnail_url=doc.thumbnail_url,
    )


@router.get("/api/timeline", response_model=TimelineResponse)
def timeline(
    agency: Optional[str] = None,
    file_type: Optional[str] = None,
    topic: Optional[str] = Query(None, description="Topic slug filter"),
) -> TimelineResponse:
    docs = list(store.documents)
    if agency:
        docs = [d for d in docs if (d.agency or "").lower() == agency.lower()]
    if file_type:
        docs = [d for d in docs if (d.file_type or "").lower() == file_type.lower()]
    if topic:
        ids = {
            d.document_id
            for d in topics_service.documents_for_topic(topic, store.documents)
        }
        docs = [d for d in docs if d.document_id in ids]

    incidents = [_entry(d, d.incident_date) for d in docs if d.incident_date]
    incidents.sort(key=lambda e: _date_sort_key(e.date))

    releases = [_entry(d, d.release_date) for d in docs if d.release_date]
    releases.sort(key=lambda e: _date_sort_key(e.date))

    return TimelineResponse(incident_timeline=incidents, release_timeline=releases)


# --------------------------- Media gallery -------------------------------
@router.get("/api/media", response_model=MediaResponse)
def media(
    media_type: Optional[str] = Query(None, pattern="^(image|video)$"),
    agency: Optional[str] = None,
    limit: int = Query(200, ge=1, le=1000),
) -> MediaResponse:
    items: list[MediaItem] = []
    for d in store.documents:
        if agency and (d.agency or "").lower() != agency.lower():
            continue

        is_video = bool(d.dvids_video_id) or d.file_type == "video"
        is_image = d.file_type == "image" or (
            bool(d.thumbnail_url) and not is_video and d.file_type != "pdf"
        )

        if media_type == "image" and not is_image:
            continue
        if media_type == "video" and not is_video:
            continue
        if media_type is None and not (is_image or is_video):
            continue

        if is_video:
            items.append(
                MediaItem(
                    media_id=f"v-{d.document_id}",
                    document_id=d.document_id,
                    media_type="video",
                    title=d.video_title or d.title,
                    caption=d.description,
                    thumbnail_url=d.thumbnail_url,
                    source_url=d.source_url,
                    dvids_video_id=d.dvids_video_id,
                    agency=d.agency,
                    incident_date=d.incident_date,
                    incident_location=d.incident_location,
                )
            )
        elif is_image:
            items.append(
                MediaItem(
                    media_id=f"i-{d.document_id}",
                    document_id=d.document_id,
                    media_type="image",
                    title=d.title,
                    caption=d.description,
                    thumbnail_url=d.thumbnail_url or d.source_url,
                    source_url=d.source_url,
                    agency=d.agency,
                    incident_date=d.incident_date,
                    incident_location=d.incident_location,
                )
            )

    return MediaResponse(total=len(items), items=items[:limit])


# --------------------------- Topics --------------------------------------
@router.get("/api/topics", response_model=TopicsResponse)
def list_topics() -> TopicsResponse:
    counts = topics_service.topic_counts(store.documents)
    return TopicsResponse(
        topics=[
            TopicSummary(
                slug=t.slug,
                title=t.title,
                description=t.description,
                count=counts.get(t.slug, 0),
            )
            for t in topics_service.TOPIC_CATALOG
        ]
    )


@router.get("/api/topics/{slug}", response_model=TopicDetailResponse)
def topic_detail(slug: str) -> TopicDetailResponse:
    topic = topics_service.get_topic(slug)
    if not topic:
        raise HTTPException(status_code=404, detail="Unknown topic")
    docs = topics_service.documents_for_topic(slug, store.documents)
    return TopicDetailResponse(
        topic=TopicSummary(
            slug=topic.slug,
            title=topic.title,
            description=topic.description,
            count=len(docs),
        ),
        documents=docs,
    )


# --------------------------- Analytics -----------------------------------
@router.get("/api/analytics", response_model=AnalyticsResponse)
def analytics() -> AnalyticsResponse:
    return AnalyticsResponse(**analytics_service.compute(store.documents))
