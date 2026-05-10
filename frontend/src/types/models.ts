export interface DocumentRecord {
  document_id: string;
  title: string;
  release_date: string | null;
  incident_date: string | null;
  incident_location: string | null;
  agency: string | null;
  file_type: string | null;
  source_url: string | null;
  local_file_path: string | null;
  thumbnail_url: string | null;
  description: string | null;
  redaction: string | null;
  video_title: string | null;
  dvids_video_id: string | null;
}

export interface DocumentListResponse {
  total: number;
  count: number;
  offset: number;
  limit: number;
  items: DocumentRecord[];
}

export interface FacetValue {
  value: string;
  count: number;
}

export interface FacetsResponse {
  agency: FacetValue[];
  file_type: FacetValue[];
  incident_location: FacetValue[];
  release_date: FacetValue[];
}

export interface StatsResponse {
  total_records: number;
  pdfs: number;
  images: number;
  videos: number;
  other: number;
  agencies: number;
  known_locations: number;
  known_incident_dates: number;
  release_date_min: string | null;
  release_date_max: string | null;
}

// --- Phase 2 ---
export interface Citation {
  index: number;
  chunk_id: string;
  document_id: string;
  title: string;
  page_number: number | null;
  agency: string | null;
  source_url: string | null;
  snippet: string | null;
}

export interface AskResponse {
  answer: string;
  citations: Citation[];
  related_documents: string[];
  followups: string[];
  confidence: string;
  usage: Record<string, number>;
}

export interface DocumentSummary {
  document_id: string;
  summary: string | null;
  key_facts: string[];
  evidence_types: string[];
  notable_locations: string[];
  notable_dates: string[];
  possible_topics: string[];
  uncertainty_notes: string | null;
  cached: boolean;
}

export interface IngestionStatus {
  running: boolean;
  started_at: string | null;
  finished_at: string | null;
  current_document: string | null;
  total_target: number;
  completed: number;
  failed: number;
  skipped: number;
  max_docs: number;
  tokens: { prompt: number; completion: number; embedding: number; total: number };
  errors: { document_id: string; title: string; error: string; ts: string }[];
  log: string[];
  last_run_summary: string | null;
}

export interface IndexStats {
  index_name: string;
  exists: boolean;
  chunk_count: number | null;
}

// --- Phase 3 ---
export interface MapMarker {
  location: string;
  label: string;
  lat: number;
  lon: number;
  confidence: "exact" | "approximate" | "broad" | "off-earth" | "unknown";
  count: number;
  document_ids: string[];
}

export interface MapResponse {
  markers: MapMarker[];
  unmapped: string[];
  unmapped_count: number;
}

export interface TimelineEntry {
  document_id: string;
  title: string;
  agency: string | null;
  date: string;
  file_type: string | null;
  incident_location: string | null;
  thumbnail_url: string | null;
}

export interface TimelineResponse {
  incident_timeline: TimelineEntry[];
  release_timeline: TimelineEntry[];
}

export interface MediaItem {
  media_id: string;
  document_id: string;
  media_type: "image" | "video";
  title: string;
  caption: string | null;
  thumbnail_url: string | null;
  source_url: string | null;
  dvids_video_id: string | null;
  agency: string | null;
  incident_date: string | null;
  incident_location: string | null;
}

export interface MediaResponse {
  total: number;
  items: MediaItem[];
}

export interface TopicSummary {
  slug: string;
  title: string;
  description: string;
  count: number;
}

export interface TopicsResponse {
  topics: TopicSummary[];
}

export interface TopicDetailResponse {
  topic: TopicSummary;
  documents: DocumentRecord[];
}

export interface AnalyticsBucket {
  value: string;
  count: number;
}

export interface AnalyticsResponse {
  total_records: number;
  by_agency: AnalyticsBucket[];
  by_file_type: AnalyticsBucket[];
  by_location: AnalyticsBucket[];
  by_incident_decade: AnalyticsBucket[];
  by_release_year: AnalyticsBucket[];
  by_redaction: AnalyticsBucket[];
  location_confidence: AnalyticsBucket[];
  media_summary: {
    with_image: number;
    with_video: number;
    unknown_dates: number;
    unknown_locations: number;
  };
  topics: TopicSummary[];
}

// --- Phase 4 ---
export interface EvidenceDimension {
  name: string;
  label: string;
  score: number;
  rationale: string;
}

export interface EvidenceScoreResponse {
  document_id: string;
  overall_score: number;
  max_score: number;
  dimensions: EvidenceDimension[];
  disclaimer: string;
}

export interface EntityItem {
  label: string;
  canonical: string;
  count: number;
  document_ids: string[];
}

export interface EntityTypeGroup {
  type: string;
  entities: EntityItem[];
}

export interface EntitiesResponse {
  types: EntityTypeGroup[];
  total_documents: number;
}

export interface ReportTemplate {
  slug: string;
  title: string;
  description: string;
}

export interface ReportTemplatesResponse {
  templates: ReportTemplate[];
}

export interface ReportSource {
  document_id: string;
  title: string;
  agency: string | null;
  incident_date: string | null;
  incident_location: string | null;
}

export interface ReportStats {
  total: number;
  by_agency: AnalyticsBucket[];
  by_file_type: AnalyticsBucket[];
  by_location: AnalyticsBucket[];
}

export interface Report {
  slug: string;
  title: string;
  description: string;
  generated_at: string;
  executive_summary: string;
  findings: string[];
  caveats: string[];
  stats: ReportStats;
  sources: ReportSource[];
  usage: Record<string, number>;
}

export interface CompareResponse {
  documents: DocumentRecord[];
  summaries: (DocumentSummary | null)[];
  evidence_scores: EvidenceScoreResponse[];
}
