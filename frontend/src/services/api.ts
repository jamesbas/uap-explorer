import type {
  AnalyticsResponse,
  AskResponse,
  CompareResponse,
  DocumentListResponse,
  DocumentRecord,
  DocumentSummary,
  EntitiesResponse,
  EvidenceScoreResponse,
  FacetsResponse,
  IndexStats,
  IngestionStatus,
  MapResponse,
  MediaResponse,
  Report,
  ReportTemplatesResponse,
  StatsResponse,
  TimelineResponse,
  TopicDetailResponse,
  TopicsResponse,
} from "../types/models";

const BASE = "";
const ADMIN_TOKEN_KEY = "uap_admin_token";

export function getAdminToken(): string | null {
  return localStorage.getItem(ADMIN_TOKEN_KEY);
}
export function setAdminToken(token: string | null): void {
  if (token) localStorage.setItem(ADMIN_TOKEN_KEY, token);
  else localStorage.removeItem(ADMIN_TOKEN_KEY);
}
export function isAdmin(): boolean {
  return !!getAdminToken();
}

async function request<T>(
  path: string,
  opts: RequestInit & { admin?: boolean } = {}
): Promise<T> {
  const headers = new Headers(opts.headers);
  if (opts.admin) {
    const token = getAdminToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  if (opts.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${BASE}${path}`, { ...opts, headers });
  if (!res.ok) {
    // Read the body exactly once — calling both res.json() and res.text() on
    // the same Response throws "body stream already read".
    const raw = await res.text().catch(() => "");
    let detail = raw;
    if (raw) {
      try {
        const j = JSON.parse(raw);
        detail = j.detail || JSON.stringify(j);
      } catch {
        // raw is already plain text
      }
    }
    throw new Error(`Request failed (${res.status}): ${detail || path}`);
  }
  if (res.status === 204) return undefined as unknown as T;
  return (await res.json()) as T;
}

function getJson<T>(path: string): Promise<T> {
  return request<T>(path);
}

export interface DocumentQuery {
  query?: string;
  agency?: string;
  file_type?: string;
  incident_location?: string;
  release_date?: string;
  offset?: number;
  limit?: number;
}

export function fetchDocuments(q: DocumentQuery = {}): Promise<DocumentListResponse> {
  const params = new URLSearchParams();
  Object.entries(q).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
  });
  const qs = params.toString();
  return getJson<DocumentListResponse>(`/api/documents${qs ? `?${qs}` : ""}`);
}

export function fetchDocument(id: string): Promise<DocumentRecord> {
  return getJson<DocumentRecord>(`/api/documents/${encodeURIComponent(id)}`);
}

export function searchDocuments(query: string): Promise<DocumentListResponse> {
  return getJson<DocumentListResponse>(
    `/api/search?query=${encodeURIComponent(query)}`
  );
}

export function fetchFacets(): Promise<FacetsResponse> {
  return getJson<FacetsResponse>("/api/facets");
}

export function fetchStats(): Promise<StatsResponse> {
  return getJson<StatsResponse>("/api/stats");
}

// --- Phase 2 ---------------------------------------------------------------
export function login(password: string): Promise<{ token: string }> {
  return request("/api/admin/login", {
    method: "POST",
    body: JSON.stringify({ password }),
  });
}

export function logout(): void {
  setAdminToken(null);
}

export function adminWhoami(): Promise<{ role: string }> {
  return request("/api/admin/whoami", { admin: true });
}

export function ask(
  question: string,
  options: { top?: number; document_id?: string } = {}
): Promise<AskResponse> {
  return request<AskResponse>("/api/ask", {
    method: "POST",
    body: JSON.stringify({ question, ...options }),
  });
}

export function fetchDocumentSummary(id: string): Promise<DocumentSummary> {
  return getJson<DocumentSummary>(
    `/api/documents/${encodeURIComponent(id)}/summary`
  );
}

export function fetchIngestionStatus(): Promise<IngestionStatus> {
  return getJson<IngestionStatus>("/api/ingestion/status");
}

export function startIngestion(opts: {
  document_ids?: string[];
  max_docs?: number;
  ensure_index?: boolean;
  summaries_only?: boolean;
  regenerate_summaries?: boolean;
}): Promise<{ started: boolean; reason?: string; summary?: string }> {
  return request("/api/ingestion/run", {
    method: "POST",
    admin: true,
    body: JSON.stringify(opts),
  });
}

export function resetIngestionStatus(): Promise<IngestionStatus> {
  return request<IngestionStatus>("/api/ingestion/reset", {
    method: "POST",
    admin: true,
  });
}

export function fetchIndexInfo(): Promise<IndexStats> {
  return request<IndexStats>("/api/admin/index", { admin: true });
}

export function createIndex(): Promise<unknown> {
  return request("/api/admin/index/create", { method: "POST", admin: true });
}

export function recreateIndex(): Promise<unknown> {
  return request("/api/admin/index/recreate", { method: "POST", admin: true });
}

// --- Phase 3 ---
export function fetchMap(): Promise<MapResponse> {
  return getJson<MapResponse>("/api/map");
}

export function fetchTimeline(filters: {
  agency?: string;
  file_type?: string;
  topic?: string;
} = {}): Promise<TimelineResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v) params.set(k, v);
  });
  const qs = params.toString();
  return getJson<TimelineResponse>(`/api/timeline${qs ? `?${qs}` : ""}`);
}

export function fetchMedia(filters: {
  media_type?: "image" | "video";
  agency?: string;
  limit?: number;
} = {}): Promise<MediaResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
  });
  const qs = params.toString();
  return getJson<MediaResponse>(`/api/media${qs ? `?${qs}` : ""}`);
}

export function fetchTopics(): Promise<TopicsResponse> {
  return getJson<TopicsResponse>("/api/topics");
}

export function fetchTopicDetail(slug: string): Promise<TopicDetailResponse> {
  return getJson<TopicDetailResponse>(`/api/topics/${encodeURIComponent(slug)}`);
}

export function fetchAnalytics(): Promise<AnalyticsResponse> {
  return getJson<AnalyticsResponse>("/api/analytics");
}

// --- Phase 4 ---
export function fetchEvidence(id: string): Promise<EvidenceScoreResponse> {
  return getJson<EvidenceScoreResponse>(
    `/api/documents/${encodeURIComponent(id)}/evidence`
  );
}

export function fetchEntities(): Promise<EntitiesResponse> {
  return getJson<EntitiesResponse>("/api/entities");
}

export function fetchReportTemplates(): Promise<ReportTemplatesResponse> {
  return getJson<ReportTemplatesResponse>("/api/reports");
}

export function fetchCachedReport(slug: string): Promise<Report> {
  return getJson<Report>(`/api/reports/${encodeURIComponent(slug)}`);
}

export function generateReport(
  slug: string,
  body: { document_ids?: string[]; force?: boolean } = {}
): Promise<Report> {
  return request<Report>(`/api/reports/${encodeURIComponent(slug)}/generate`, {
    method: "POST",
    body: JSON.stringify(body),
    admin: true,
  });
}

export function reportMarkdownUrl(slug: string): string {
  return `/api/reports/${encodeURIComponent(slug)}/export.md`;
}

export function fetchCompare(ids: string[]): Promise<CompareResponse> {
  const params = ids.map((i) => `ids=${encodeURIComponent(i)}`).join("&");
  return getJson<CompareResponse>(`/api/compare?${params}`);
}
