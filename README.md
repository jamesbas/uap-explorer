# UAP Explorer

A source-grounded research portal for the public release of U.S. government
**Unidentified Anomalous Phenomena (UAP)** records. UAP Explorer indexes the
released metadata and (when available) the original PDFs/images, then offers
multiple ways to browse, search, ask questions about, and report on the archive
— always with citations back to the original documents.

The project is implemented in four phases. **All four phases are now complete.**

| Phase | Capability | Status |
|---|---|---|
| 1 | Local archive browser (CSV-driven) | ✅ |
| 2 | Azure ingestion + grounded "Ask the archive" | ✅ |
| 3 | Map, timeline, media, topics, analytics | ✅ |
| 4 | Reports, evidence scoring, entity explorer, compare, exports | ✅ |

See [docs/architecture.md](docs/architecture.md) for a detailed component map and
[UAP Explorer - App Specifications.md](docs/UAP%20Explorer%20-%20App%20Specifications.md)
for the original product spec.

---

## Highlights

- **Browse & search** the full archive with faceted filters (agency, file type,
  location, release date) and keyword search.
- **Ask the archive** — citation-backed Q&A grounded in indexed text using Azure
  AI Search hybrid retrieval and Azure OpenAI (GPT-5.2). Every answer includes
  source links and follow-up suggestions.
- **Interactive map** of geocoded incident locations (Leaflet) with confidence
  ratings (exact / approximate / broad / off-earth / unknown).
- **Timeline view** binned by decade, plus a **media gallery** of images and
  DVIDS videos.
- **Topics catalog** — 11 curated lenses (e.g. *Radar cases*, *Modern military
  sensor*, *Historical FBI*) for thematic browsing.
- **Analytics dashboard** with breakdowns by agency, file type, location,
  decade, redaction level, and location-confidence.
- **Entity explorer** — agencies, locations, dates, aircraft, spacecraft,
  sensors, bases, projects, object descriptions, and events extracted from the
  metadata.
- **Reports** — eight LLM-written report templates (e.g. *Best Documented
  Cases*, *Radar-related Reports*) with strict JSON output, `[doc:ID]`
  citations, cached generation, Markdown export, and browser print-to-PDF.
- **Evidence quality score** — eight deterministic dimensions (date,
  location, source, media, witness, redaction, corroboration, resolution)
  shown on every record. Includes an explicit **neutrality disclaimer**: the
  score reflects record completeness, not the likelihood of an extraterrestrial
  explanation.
- **Research pack** — localStorage-backed shortlist on the frontend; jump to
  the **Compare** view for side-by-side metadata, AI summaries, and evidence
  scores.
- **Subtle UFO theme** — animated saucer + radar-ping background.
- **Admin console** — password-gated UI for ingestion runs, AI Search index
  create/recreate, and ingestion status.

---

## Project layout

```text
uap-explorer/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes.py          Phase 1 (browse/search/facets/stats)
│   │   │   ├── admin_routes.py    Phase 2 (ask, summaries, ingestion, admin)
│   │   │   ├── phase3_routes.py   Map, timeline, media, topics, analytics
│   │   │   └── phase4_routes.py   Evidence, entities, reports, compare, export
│   │   ├── ingestion/
│   │   │   ├── pipeline.py        Blob upload → DocIntel/pypdf → chunk →
│   │   │   │                      embed → index → summarize
│   │   │   └── status.py
│   │   ├── services/
│   │   │   ├── csv_loader.py      Source CSV parsing & ID generation
│   │   │   ├── store.py           In-memory document store
│   │   │   ├── pdf_extractor.py   Document Intelligence + pypdf fallback
│   │   │   ├── azure_clients.py   Key + managed-identity factories
│   │   │   ├── blob_storage.py
│   │   │   ├── search_index.py    Azure AI Search index mgmt + hybrid query
│   │   │   ├── openai_service.py  Chat + embeddings (GPT-5.2 quirks handled)
│   │   │   ├── ask_service.py     Grounded Q&A with citations + follow-ups
│   │   │   ├── locations.py       Geocoding lookup + confidence
│   │   │   ├── topics.py          Curated topic catalog
│   │   │   ├── analytics.py
│   │   │   ├── evidence.py        Deterministic 8-dimension scoring
│   │   │   ├── entities.py        Regex/keyword entity extraction
│   │   │   └── reports.py         LLM-written, citation-backed reports
│   │   ├── auth.py                Bearer-token admin auth
│   │   ├── config.py
│   │   ├── main.py
│   │   └── models.py              Pydantic request/response models
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── pages/                 16 pages (Home, Browse, Search, Ask, Map,
│       │                          Timeline, Media, Topics, Analytics,
│       │                          Entities, Reports, Compare, RecordDetail,
│       │                          About, Admin)
│       ├── components/
│       ├── services/
│       │   ├── api.ts             Typed REST client
│       │   └── researchPack.ts    localStorage-backed compare pack
│       ├── styles/global.css      Theme, UFO background, print styles
│       └── types/models.ts
├── data/
│   ├── source/uap-csv.csv         Source metadata
│   └── processed/                 Cached AI artifacts (created at runtime)
│       ├── extracted/             Extracted text per document
│       ├── summaries/             AI summaries per document
│       └── reports/               Cached generated reports
├── ufo_release_01_files/          Optional local PDF/image cache
├── docs/architecture.md
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Running locally

### Two-terminal dev workflow

**Backend** (Python 3.11+):

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

The API will be available at `http://localhost:8001` (interactive docs at
`http://localhost:8001/docs`).

> **Port note.** The Vite proxy is configured for **port 8001**. Port 8000 was
> abandoned during development because of stale Windows sockets occasionally
> wedging the listener.

**Frontend** (Node 18+):

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` and `/health` to the backend.

### Docker Compose

```powershell
docker compose up --build
```

---

## Configuration

All settings come from environment variables (with sensible defaults for the
no-Azure local mode). See [.env.example](.env.example) for the full list. The
notable ones:

| Variable | Purpose |
|---|---|
| `UAP_CSV_PATH` | Source metadata CSV (default `data/source/uap-csv.csv`) |
| `UAP_FILE_ROOT` | Optional local PDF/image cache |
| `UAP_PROCESSED_ROOT` | Where cached AI artifacts are written (`data/processed`) |
| `ADMIN_PASSWORD` | Password for the Admin UI bearer token |
| `AZURE_AUTH_MODE` | `key` or `managed_identity` |
| `AZURE_STORAGE_*` | Blob upload of source PDFs/images |
| `AZURE_SEARCH_*` | AI Search endpoint, index name, admin key |
| `AZURE_OPENAI_*` | Chat (`GPT-5.2-chat`) + embeddings (`text-embedding-3-large`, 3072 dims) |
| `AZURE_DOCUMENT_INTELLIGENCE_*` | Layout extraction (falls back to pypdf if disabled) |
| `INGESTION_MAX_DOCS` / `INGESTION_CHUNK_CHARS` / `INGESTION_CHUNK_OVERLAP` | Pipeline tuning |

Phase 1 (local browser only) does not require any Azure credentials. Phases 2–4
require Azure AI Search, Azure OpenAI, Blob Storage, and (optionally)
Document Intelligence.

---

## REST API summary

### Phase 1 — Archive browse

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness + document count |
| `GET` | `/api/documents` | List/filter (`query`, `agency`, `file_type`, `incident_location`, `release_date`, `offset`, `limit`) |
| `GET` | `/api/documents/{id}` | Single record |
| `GET` | `/api/documents/{id}/file` | Stream a locally cached source file |
| `GET` | `/api/search?query=` | Keyword search |
| `GET` | `/api/facets` | Top values for agency, file type, location, release date |
| `GET` | `/api/stats` | Archive summary counts |

### Phase 2 — Ingestion + Ask

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/admin/login` | Exchange password for bearer token |
| `GET` | `/api/admin/whoami` | Verify admin token |
| `GET` | `/api/admin/index` | AI Search index info |
| `POST` | `/api/admin/index/create` | Create the AI Search index |
| `POST` | `/api/admin/index/recreate` | Drop + recreate the index |
| `GET` | `/api/ingestion/status` | Most recent / running ingestion job |
| `POST` | `/api/ingestion/run` | Kick off ingestion (admin) |
| `POST` | `/api/ask` | Grounded Q&A → answer + citations + follow-ups |
| `GET` | `/api/documents/{id}/summary` | Cached AI summary |
| `GET` | `/api/documents/{id}/chunks` | Indexed chunks for a document |

### Phase 3 — Visualization

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/map` | Geocoded markers with confidence |
| `GET` | `/api/timeline` | Decade buckets + missing-date count |
| `GET` | `/api/media` | Image and DVIDS video records (filterable) |
| `GET` | `/api/topics` | Curated topic catalog |
| `GET` | `/api/topics/{slug}` | Records for a topic |
| `GET` | `/api/analytics` | Dashboard data |

### Phase 4 — Reports, evidence, entities, compare

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/documents/{id}/evidence` | 8-dimension evidence quality score |
| `GET` | `/api/entities` | Entity buckets (agency, location, date, aircraft, spacecraft, sensor, base, project, object_shape, event) |
| `GET` | `/api/reports` | List the 8 report templates |
| `GET` | `/api/reports/{slug}` | Cached report (404 if not generated) |
| `POST` | `/api/reports/{slug}/generate` | Generate a report (`document_ids?`, `force?`) |
| `GET` | `/api/reports/{slug}/export.md` | Markdown download |
| `GET` | `/api/compare?ids=&ids=` | Side-by-side records + summaries + evidence |

Full schema is browsable at `/docs` (Swagger UI).

---

## Frontend pages

| Route | Page | Notes |
|---|---|---|
| `/` | Home | Stats overview |
| `/browse` | Browse | Faceted browse with filters + paging |
| `/search` | Search | Keyword search across metadata |
| `/ask` | Ask the archive | Grounded Q&A with citations |
| `/map` | Map | Leaflet markers with confidence styling |
| `/timeline` | Timeline | Decade histogram |
| `/media` | Media | Image + video gallery |
| `/topics` | Topics | Catalog index |
| `/topics/:slug` | Topic detail | Records for a curated topic |
| `/analytics` | Analytics | Multi-facet dashboard |
| `/entities` | Entity explorer | Filterable entity buckets |
| `/reports` | Reports | Generate / view / export reports |
| `/compare` | Compare | Side-by-side from research pack |
| `/records/:id` | Record detail | Metadata + AI summary + evidence panel + research pack toggle |
| `/about` | About | Project background |
| `/admin` | Admin | Login, ingestion, index ops |

---

## Tests

```powershell
cd backend
.venv\Scripts\Activate.ps1
pytest
```

A quick end-to-end smoke test of all Phase 4 routes can be run with the FastAPI
TestClient — see [docs/architecture.md](docs/architecture.md#10-smoke-testing)
for recipes.

---

## Data source & neutrality

The base CSV `uap-csv.csv` lives at the repo root and is mirrored to
`data/source/uap-csv.csv`. Sentinels like `N/A`, `NA`, `none`, `unknown`, `null`,
and `-` are treated as missing.

UAP Explorer makes no claims about the nature or origin of the events in the
archive. Reports and evidence scores describe **record completeness** only — not
the likelihood of any particular explanation. Every AI-generated artifact
includes its source citations so users can verify against the originals.
