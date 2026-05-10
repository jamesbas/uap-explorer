# UAP Explorer — Architecture

This document describes the runtime components, data flows, and key design
decisions of UAP Explorer. For product capabilities, see the
[README](../README.md). For the original product spec, see
[UAP Explorer - App Specifications.md](../UAP%20Explorer%20-%20App%20Specifications.md).

---

## 1. System overview

```
┌──────────────────┐    HTTP/JSON    ┌───────────────────────────────┐
│  React + Vite    │◄───────────────►│  FastAPI backend (port 8001)  │
│  (port 5173)     │   /api  /health │  • Phase 1–4 routers          │
│                  │                 │  • In-memory document store   │
│  Leaflet maps    │                 │  • Cached AI artifacts on disk│
│  localStorage    │                 └───────────┬───────────────────┘
│  research pack   │                             │
└──────────────────┘                             │ Azure SDK
                                                 ▼
                          ┌──────────────────────────────────────────┐
                          │  Azure                                    │
                          │  • Blob Storage (source PDFs/images)      │
                          │  • Document Intelligence (layout)         │
                          │  • AI Search (hybrid retrieval, 3072-dim) │
                          │  • OpenAI: GPT-5.2-chat + embeddings      │
                          └──────────────────────────────────────────┘
```

- The **frontend** is a single-page React app served by Vite in dev. It talks
  exclusively to the backend over `/api` and `/health` (proxied to
  `localhost:8001` in dev, same-origin in containers).
- The **backend** is a FastAPI app. It loads the source CSV at startup into an
  in-memory document store and registers four routers (one per phase).
- All Azure clients are constructed lazily and support either **API keys** or
  **managed identity** based on `AZURE_AUTH_MODE`.

---

## 2. Backend module map

```
backend/app/
├── main.py                 FastAPI app + router registration + CORS
├── config.py               Settings loaded from .env (key/MI auth, paths, etc.)
├── auth.py                 Admin password → bearer token, FastAPI dependency
├── models.py               All Pydantic request/response schemas
│
├── api/
│   ├── routes.py           Phase 1: documents, search, facets, stats
│   ├── admin_routes.py     Phase 2: login, index ops, ingestion, ask, summary
│   ├── phase3_routes.py    Phase 3: map, timeline, media, topics, analytics
│   └── phase4_routes.py    Phase 4: evidence, entities, reports, compare
│
├── ingestion/
│   ├── pipeline.py         End-to-end ingestion orchestrator
│   └── status.py           Job state (queued / running / done / error)
│
└── services/
    ├── csv_loader.py       CSV → DocumentRecord (stable hashed IDs)
    ├── store.py            In-memory store (read-mostly)
    ├── azure_clients.py    Factories for Blob, Search, DocIntel, OpenAI
    ├── blob_storage.py     Upload + presigned URL helpers
    ├── pdf_extractor.py    DocIntel layout → text; pypdf fallback
    ├── search_index.py     Index schema, create/recreate, hybrid query
    ├── openai_service.py   Chat + embeddings (handles GPT-5.2 quirks)
    ├── ask_service.py      Retrieval + grounded answer + follow-ups
    ├── locations.py        Geocode lookup + confidence tier
    ├── topics.py           11 curated topic definitions + matchers
    ├── analytics.py        Facet aggregations
    ├── evidence.py         Deterministic 8-dimension quality score
    ├── entities.py         Regex/keyword entity extraction across 10 types
    └── reports.py          LLM-written reports with strict JSON contract
```

### Key design choices

- **In-memory document store.** ~150 records easily fit in memory. Filtering is
  linear over a Python list. There is no relational DB.
- **Stable IDs.** `csv_loader.py` derives a 16-char hex ID from
  `sha1(title + source_url)` so re-running ingestion preserves identity.
- **Layered Azure auth.** `azure_clients.py` exposes `get_blob_client()`,
  `get_search_*()`, `get_openai_client()`, `get_docintel_client()`, each
  switching on `settings.use_managed_identity`. The codebase tolerates
  Document Intelligence being disabled (DocIntel auth is finicky in some
  subscriptions); ingestion silently falls back to pypdf.
- **GPT-5.2-chat quirks.** The deployment requires `max_completion_tokens` (not
  `max_tokens`) and accepts only `temperature=1`. `openai_service.chat_completion`
  uses a try/fallback pattern to call the right argument names.
- **Strict JSON for reports.** `reports.py` instructs the model to return only
  JSON with `executive_summary`, `findings`, `caveats`. `_parse_json_block`
  strips markdown fences and tolerates partial output. Each finding must cite
  with `[doc:DOCID]`, which the frontend turns into record links.

---

## 3. Ingestion pipeline (Phase 2)

```
CSV record
   │
   ▼
[1] Locate source PDF / image (UAP_FILE_ROOT or download from source_url)
   │
   ▼
[2] Upload to Blob Storage (idempotent by document_id)
   │
   ▼
[3] Extract text:
     ├─ Document Intelligence layout (preferred)
     └─ pypdf fallback (always available)
   │
   ▼
[4] Chunk text (default 1500 chars, 200 overlap)
   │
   ▼
[5] Embed each chunk (text-embedding-3-large, 3072 dims)
   │
   ▼
[6] Upload chunks to AI Search index `uap-explorer-chunks`
     (BM25 + vector; semantic ranking enabled)
   │
   ▼
[7] Generate per-document AI summary (GPT-5.2)
     → cache to data/processed/summaries/{document_id}.json
```

State is held in `ingestion/status.py` (single in-process dict) and surfaced
via `GET /api/ingestion/status`. The pipeline is launched by
`POST /api/ingestion/run` (admin-only) on a background task.

The job is **resilient**: each step catches per-document errors and continues
with the next, so one bad PDF does not abort the run.

---

## 4. Ask pipeline (Phase 2)

`POST /api/ask` runs:

1. **Embed** the question with `text-embedding-3-large`.
2. **Hybrid search** against `uap-explorer-chunks` (vector + keyword + semantic
   ranker), top-K chunks.
3. **Build prompt** with chunked context, document metadata, and a strict
   citation requirement (`[doc:ID]` markers must accompany every claim).
4. **Call GPT-5.2-chat** to produce `answer`, `citations[]`, and 3 follow-up
   suggestions.
5. **Return** the structured response. The frontend `AskPage` renders the
   answer, hyperlinks `[doc:ID]` markers to record pages, and shows clickable
   follow-ups.

---

## 5. Phase 3 — Visualization services

- `services/locations.py` — `LOCATION_LOOKUP` is a hand-curated dict of
  `{normalized_name: (lat, lon, confidence_tier)}`. Tiers are `exact`,
  `approximate`, `broad`, `off-earth`, `unknown`.
- `services/topics.py` — `TOPIC_CATALOG` defines 11 topics with selector
  predicates over CSV fields and (where available) cached summaries.
- `services/analytics.py` — single `compute(docs)` that returns the dashboard
  payload: counts by agency, file type, location, decade, release year,
  redaction, location-confidence; a media summary; and the topic catalog.

All three services are pure functions over the in-memory store, so the
endpoints are O(N) over ~150 records and respond in single-digit ms.

---

## 6. Phase 4 — Evidence, entities, reports, compare

### Evidence scoring (`services/evidence.py`)

Deterministic. **No LLM.** 8 dimensions × 0–10:

| Dimension | Signal |
|---|---|
| Date quality | Year resolution / "Unknown" |
| Location quality | `locations.confidence_for(name)` |
| Source quality | Agency reputation table (FBI=8, NASA=9, etc.) |
| Media support | Image / video presence |
| Witness support | Description heuristics |
| Redaction level | Inverse of redaction string |
| Corroboration | Other records sharing the same location |
| Resolution | "Unresolved" / "Identified" markers |

Output includes a mandatory **disclaimer**:

> "This score reflects record completeness only — it does NOT represent the
> likelihood that an event was extraterrestrial."

### Entity extraction (`services/entities.py`)

Deterministic. **No LLM.** Word-boundary regexes with alias lists, applied
against title + description + video_title + cached summary text. 10 types:
`agency`, `location`, `date`, `aircraft`, `spacecraft`, `sensor`, `base`,
`project`, `object_shape`, `event`. Agency, location, and date entities also
flow directly from CSV columns.

### Report generation (`services/reports.py`)

LLM-driven. 8 templates registered in `TEMPLATES`:
`sightings-by-location`, `records-by-decade`, `best-documented`,
`visual-evidence`, `radar-related`, `fbi-historical`,
`modern-military-sensor`, `object-descriptions`.

`generate(slug, document_ids?, force?)`:

1. Resolve the document set (template selector or caller-supplied IDs).
2. Cache hit? Return unless `force=True`. Cache key includes a hash of the
   document set so different scopes don't collide.
3. Build context (max 40 docs to fit token budget) including cached summaries.
4. Call GPT-5.2-chat with the strict-JSON system prompt.
5. Parse, validate, attach computed `stats` and `sources`, save to
   `data/processed/reports/{slug}[-hash].json`.

`to_markdown(report)` produces the export delivered by
`GET /api/reports/{slug}/export.md`.

### Compare

`GET /api/compare?ids=&ids=` is a thin orchestrator that fetches each record,
its cached summary (if any), and its evidence score, and returns them as
parallel arrays.

---

## 7. Frontend architecture

- **React 18 + Vite 5 + TypeScript 5.** No global state library; pages own
  their data with `useEffect`.
- **`services/api.ts`** is the only place that talks HTTP. It's a thin typed
  wrapper around `fetch` with an admin-Bearer-token interceptor.
- **`services/researchPack.ts`** holds a simple list of document IDs in
  `localStorage` under `uap_research_pack`. It exposes `addToPack`,
  `removeFromPack`, `togglePack`, `getPack`, `clearPack`, and an
  `onPackChange(cb)` event helper that fires on cross-tab `storage` events
  and same-tab `uap:pack-change` custom events.
- **`Leaflet`** is pinned to `react-leaflet` v4 because v5 requires React 19.
- **`styles/global.css`** carries the dark theme, the SVG saucer + radar-ping
  background (subtle, opacity ~0.18), and an `@media print` block that hides
  navigation/toolbars and forces white-on-black inversion so "Print / Save
  PDF" produces a clean report.

### Routing

`App.tsx` defines the nav bar and routes for the 16 pages listed in the
[README](../README.md#frontend-pages). Admin nav appears only when an admin
token is present in `localStorage` (`uap_admin_token`).

### Citation rendering

`ReportsPage` linkifies `[doc:ID]` markers to `/records/:id`. `AskPage` does
the same for chat answers. Together with the source list at the bottom of every
report, this preserves the project's "always cite the source" guarantee.

---

## 8. Storage & caching

| Path | Contents | Lifetime |
|---|---|---|
| `data/source/uap-csv.csv` | Source metadata | Permanent (versioned) |
| `data/processed/extracted/{id}.txt` | Extracted text per document | Regenerated by ingestion |
| `data/processed/summaries/{id}.json` | AI per-document summaries | Regenerated by ingestion |
| `data/processed/reports/{slug}[-hash].json` | Cached generated reports | Created on demand; `force=true` to bust |
| `ufo_release_01_files/` | Optional local PDF/image copies | User-managed |
| Browser `localStorage` | Admin token, research pack | Per-browser |

Azure-side state lives in:

- **Blob Storage** container — uploaded source files
- **AI Search** index `uap-explorer-chunks` — vectorized chunks (BM25 +
  3072-dim HNSW, semantic config enabled)

---

## 9. Security & operations

- The frontend admin surface is gated by `ADMIN_PASSWORD` exchanged via
  `POST /api/admin/login` for a bearer token. Token verification uses
  `auth.require_admin` as a FastAPI dependency.
- All write operations (ingestion run, index create/recreate) require the
  admin token.
- CORS is configured for `FRONTEND_URL`; production deployment should
  same-origin host both services behind a single reverse proxy.
- Azure clients respect `AZURE_AUTH_MODE=managed_identity`, allowing key-less
  operation when running on Azure compute with appropriate role assignments.

---

## 10. Smoke testing

A fast end-to-end check of every Phase 4 route with the FastAPI TestClient:

```powershell
cd backend
.\.venv\Scripts\python.exe -c @"
from app.main import app
from fastapi.testclient import TestClient
with TestClient(app) as c:
    print(c.get('/health').json())
    print('templates:', [t['slug'] for t in c.get('/api/reports').json()['templates']])
    docs = c.get('/api/documents?limit=2').json()['items']
    a, b = docs[0]['document_id'], docs[1]['document_id']
    print('evidence:', c.get(f'/api/documents/{a}/evidence').json()['overall_score'])
    print('entities types:', [g['type'] for g in c.get('/api/entities').json()['types']])
    print('compare:', len(c.get(f'/api/compare?ids={a}&ids={b}').json()['documents']))
"@
```

To run live HTTP smoke tests against a running backend:

```powershell
$ids = (Invoke-RestMethod 'http://127.0.0.1:8001/api/documents?limit=2').items.document_id
Invoke-RestMethod "http://127.0.0.1:8001/api/documents/$($ids[0])/evidence"
Invoke-RestMethod "http://127.0.0.1:8001/api/compare?ids=$($ids[0])&ids=$($ids[1])"
```

---

## 11. Known limitations

- The document store is fully in-memory. The architecture assumes O(low
  thousands) of records.
- Geocoding is a hand-curated lookup (`services/locations.py`); unfamiliar
  place names fall through to confidence `unknown`.
- Report generation is bounded at 40 documents per call to fit the chat
  context window.
- Print-to-PDF relies on the browser's native dialog (no headless PDF
  service).
- Ingestion runs in-process via `BackgroundTasks`; a multi-worker deployment
  would need an external job queue to serialize jobs.
