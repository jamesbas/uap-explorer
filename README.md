# UAP Explorer

A source-grounded research portal for the public release of U.S. government
**Unidentified Anomalous Phenomena (UAP)** records. UAP Explorer indexes the
released metadata and (when available) the original PDFs/images, then offers
multiple ways to browse, search, ask questions about, and report on the archive
— always with citations back to the original documents.

**Live deployment**: https://ca-uapexplorer-frontend.livelyground-02a57294.eastus.azurecontainerapps.io

All four feature phases are complete:

| Phase | Capability | Status |
|---|---|---|
| 1 | Local archive browser (CSV-driven) | ✅ |
| 2 | Azure ingestion + grounded "Ask the archive" | ✅ |
| 3 | Map, timeline, media, topics, analytics | ✅ |
| 4 | Reports, evidence scoring, entity explorer, compare, exports | ✅ |
| — | Containerized deployment on Azure Container Apps (Bicep IaC) | ✅ |

See [docs/architecture.md](docs/architecture.md) for a detailed component map,
[infra/README.md](infra/README.md) for deployment, and
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
  Generation is **admin-gated** (each cache miss is a paid LLM call); reading
  cached reports remains public.
- **Evidence quality score** — eight deterministic dimensions (date,
  location, source, media, witness, redaction, corroboration, resolution)
  shown on every record. Includes an explicit **neutrality disclaimer**: the
  score reflects record completeness, not the likelihood of an extraterrestrial
  explanation.
- **Research pack** — localStorage-backed shortlist on the frontend; jump to
  the **Compare** view for side-by-side metadata, AI summaries, and evidence
  scores.
- **Subtle UFO theme** — animated saucer + radar-ping background.
- **Help center** — inline guide to every feature, the evidence-score
  methodology, and the project's neutrality stance.
- **Donate** — PayPal hosted-button block on the Home and About pages for
  voluntary support of hosting / Azure AI costs.
- **Admin console** — password-gated UI for ingestion runs, AI Search index
  create/recreate, ingestion status, and report generation.

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
| `POST` | `/api/reports/{slug}/generate` | Generate a report (`document_ids?`, `force?`) — **admin-only** |
| `GET` | `/api/reports/{slug}/export.md` | Markdown download |
| `GET` | `/api/compare?ids=&ids=` | Side-by-side records + summaries + evidence |

Full schema is browsable at `/docs` (Swagger UI).

---

## Frontend pages

| Route | Page | Notes |
|---|---|---|
| `/` | Home | Stats, "Ask the archive" hero CTA, donate block |
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
| `/reports` | Reports | View / export reports; generate (admin-only) |
| `/compare` | Compare | Side-by-side from research pack |
| `/records/:id` | Record detail | Metadata + AI summary + evidence panel + research pack toggle |
| `/help` | Help | Feature guide + evidence methodology + neutrality stance |
| `/about` | About | Project story, capabilities, donate, GitHub link |
| `/admin` | Admin | Login, ingestion, index ops |

---

## Deployment (Azure Container Apps)

Production runs on **Azure Container Apps** in `eastus`, provisioned by Bicep
in [infra/main.bicep](infra/main.bicep) and orchestrated by
[infra/deploy.ps1](infra/deploy.ps1). Two apps live in one Environment:

```
[external]  ca-uapexplorer-frontend  nginx:1.27-alpine  port 8080
                  │ /api, /health proxy (BACKEND_URL env)
                  ▼
[internal]  ca-uapexplorer-backend   python:3.12-slim   port 8000
```

Supporting resources (all in resource group `rgJabAI-UAPExplorer`):

- ACR Basic (`acruapexplorer{unique}`) hosts the two images.
- User-assigned Managed Identity with `AcrPull` on the registry.
- Log Analytics workspace (`log-uapexplorer`) for app logs.
- Container Apps Environment (`cae-uapexplorer`) on the Consumption profile.
- All Azure data-plane keys (storage, search, OpenAI, Doc Intel, admin pwd) are
  stored as **Container Apps secrets** and surfaced via `secretRef` env vars
  \u2014 they are never baked into the image.

### Reusable deploy script

```powershell
$env:PATH = "$env:PATH;C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin"
cd C:\Code\uap-explorer
powershell -ExecutionPolicy Bypass -File .\infra\deploy.ps1
```

The script:

1. Sets the subscription (`9c245e09-df78-44f6-9253-a2a176e6f147` by default,
   override with `-SubscriptionId`).
2. Creates/uses resource group `rgJabAI-UAPExplorer`.
3. Reads secrets from `backend/.env`.
4. Runs Bicep to provision ACR + Env + apps (placeholder images first time).
5. `az acr build` for backend (stages the source CSV) and frontend.
6. Re-runs Bicep with the real image tags to roll new revisions.
7. Patches the backend's `FRONTEND_URL` for CORS.

Useful flags:

| Flag | Effect |
|---|---|
| `-SkipBuild` | Skip image builds; redeploy infra against the latest pushed tags. |
| `-SkipInfra` | Skip Bicep; just rebuild and roll the apps. |
| `-NamePrefix x` | Override the resource name prefix (default `uapexplorer`). |

### Scale & cost controls

Both apps default to `minReplicas=0, maxReplicas=2` \u2014 they **scale to zero**
when idle. Tighten or pin with one-off commands:

```powershell
# Cap at one replica each (saves on burst):
az containerapp update -n ca-uapexplorer-backend  -g rgJabAI-UAPExplorer --max-replicas 1
az containerapp update -n ca-uapexplorer-frontend -g rgJabAI-UAPExplorer --max-replicas 1

# Park completely (zero compute charges):
az containerapp update -n ca-uapexplorer-backend  -g rgJabAI-UAPExplorer --max-replicas 0
az containerapp update -n ca-uapexplorer-frontend -g rgJabAI-UAPExplorer --max-replicas 0
```

### Rotating the admin password (no rebuild required)

```powershell
az containerapp secret set `
    --name ca-uapexplorer-backend `
    --resource-group rgJabAI-UAPExplorer `
    --secrets admin-password=YourNewPasswordHere
```

This auto-rolls a new revision. Also update `backend/.env` locally so future
`deploy.ps1` runs don't overwrite the new value.

See [infra/README.md](infra/README.md) for the full deploy/operate runbook.

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
