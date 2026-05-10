"""Pydantic models for UAP Explorer."""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel


class DocumentRecord(BaseModel):
    document_id: str
    title: str
    release_date: Optional[str] = None
    incident_date: Optional[str] = None
    incident_location: Optional[str] = None
    agency: Optional[str] = None
    file_type: Optional[str] = None
    source_url: Optional[str] = None
    local_file_path: Optional[str] = None
    thumbnail_url: Optional[str] = None
    description: Optional[str] = None
    redaction: Optional[str] = None
    video_title: Optional[str] = None
    dvids_video_id: Optional[str] = None


class DocumentListResponse(BaseModel):
    total: int
    count: int
    offset: int
    limit: int
    items: List[DocumentRecord]


class FacetValue(BaseModel):
    value: str
    count: int


class FacetsResponse(BaseModel):
    agency: List[FacetValue]
    file_type: List[FacetValue]
    incident_location: List[FacetValue]
    release_date: List[FacetValue]


class StatsResponse(BaseModel):
    total_records: int
    pdfs: int
    images: int
    videos: int
    other: int
    agencies: int
    known_locations: int
    known_incident_dates: int
    release_date_min: Optional[str] = None
    release_date_max: Optional[str] = None


# --- Phase 2 ---------------------------------------------------------------
class AskRequest(BaseModel):
    question: str
    top: Optional[int] = 8
    document_id: Optional[str] = None  # restrict to one document if provided


class Citation(BaseModel):
    index: int
    chunk_id: str
    document_id: str
    title: str
    page_number: Optional[int] = None
    agency: Optional[str] = None
    source_url: Optional[str] = None
    snippet: Optional[str] = None


class AskResponse(BaseModel):
    answer: str
    citations: List[Citation] = []
    related_documents: List[str] = []
    followups: List[str] = []
    confidence: str = "medium"
    usage: dict = {}


class DocumentSummary(BaseModel):
    document_id: str
    summary: Optional[str] = None
    key_facts: List[str] = []
    evidence_types: List[str] = []
    notable_locations: List[str] = []
    notable_dates: List[str] = []
    possible_topics: List[str] = []
    uncertainty_notes: Optional[str] = None
    cached: bool = True


class IngestionRequest(BaseModel):
    document_ids: Optional[List[str]] = None
    max_docs: Optional[int] = None
    ensure_index: bool = True


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    token: str


# --- Phase 3 ---------------------------------------------------------------
class MapMarker(BaseModel):
    location: str
    label: str
    lat: float
    lon: float
    confidence: str
    count: int
    document_ids: List[str]


class MapResponse(BaseModel):
    markers: List[MapMarker]
    unmapped: List[str] = []
    unmapped_count: int = 0


class TimelineEntry(BaseModel):
    document_id: str
    title: str
    agency: Optional[str] = None
    date: str
    file_type: Optional[str] = None
    incident_location: Optional[str] = None
    thumbnail_url: Optional[str] = None


class TimelineResponse(BaseModel):
    incident_timeline: List[TimelineEntry]
    release_timeline: List[TimelineEntry]


class MediaItem(BaseModel):
    media_id: str
    document_id: str
    media_type: str  # image | video
    title: str
    caption: Optional[str] = None
    thumbnail_url: Optional[str] = None
    source_url: Optional[str] = None
    dvids_video_id: Optional[str] = None
    agency: Optional[str] = None
    incident_date: Optional[str] = None
    incident_location: Optional[str] = None


class MediaResponse(BaseModel):
    total: int
    items: List[MediaItem]


class TopicSummary(BaseModel):
    slug: str
    title: str
    description: str
    count: int


class TopicsResponse(BaseModel):
    topics: List[TopicSummary]


class TopicDetailResponse(BaseModel):
    topic: TopicSummary
    documents: List[DocumentRecord]


class AnalyticsBucket(BaseModel):
    value: str
    count: int


class AnalyticsResponse(BaseModel):
    total_records: int
    by_agency: List[AnalyticsBucket]
    by_file_type: List[AnalyticsBucket]
    by_location: List[AnalyticsBucket]
    by_incident_decade: List[AnalyticsBucket]
    by_release_year: List[AnalyticsBucket]
    by_redaction: List[AnalyticsBucket]
    location_confidence: List[AnalyticsBucket]
    media_summary: dict
    topics: List[TopicSummary]


# --- Phase 4 ---------------------------------------------------------------
class EvidenceDimension(BaseModel):
    name: str
    label: str
    score: int
    rationale: str


class EvidenceScoreResponse(BaseModel):
    document_id: str
    overall_score: float
    max_score: float
    dimensions: List[EvidenceDimension]
    disclaimer: str


class EntityItem(BaseModel):
    label: str
    canonical: str
    count: int
    document_ids: List[str]


class EntityTypeGroup(BaseModel):
    type: str
    entities: List[EntityItem]


class EntitiesResponse(BaseModel):
    types: List[EntityTypeGroup]
    total_documents: int


class ReportTemplate(BaseModel):
    slug: str
    title: str
    description: str


class ReportTemplatesResponse(BaseModel):
    templates: List[ReportTemplate]


class ReportSource(BaseModel):
    document_id: str
    title: str
    agency: Optional[str] = None
    incident_date: Optional[str] = None
    incident_location: Optional[str] = None


class ReportStats(BaseModel):
    total: int
    by_agency: List[AnalyticsBucket]
    by_file_type: List[AnalyticsBucket]
    by_location: List[AnalyticsBucket]


class Report(BaseModel):
    slug: str
    title: str
    description: str
    generated_at: str
    executive_summary: str
    findings: List[str]
    caveats: List[str]
    stats: ReportStats
    sources: List[ReportSource]
    usage: dict = {}


class ReportRequest(BaseModel):
    document_ids: Optional[List[str]] = None
    force: bool = False


class CompareResponse(BaseModel):
    documents: List[DocumentRecord]
    summaries: List[Optional[DocumentSummary]]
    evidence_scores: List[EvidenceScoreResponse]
