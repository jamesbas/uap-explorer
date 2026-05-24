# Video Ingestion Planning

> Status: **Planning only — not implemented.**
> Owner: UAP Explorer backend
> Last updated: 2026-05-24

## 1. Goal

Extend the existing PDF ingestion pipeline so that videos placed in the
`uap-files` blob container (e.g. DVIDS clips, sensor footage, briefing
recordings) become first-class searchable artifacts. A user asking
*"What does the Iran 2022 formation video say?"* should receive a cited
answer drawn from the **spoken-word transcript** of that video, with the
video itself viewable inline in the frontend.

Out-of-scope for v1 (can be added later):
- Face / object / scene detection
- Visual-similarity search across keyframes
- Real-time / streaming transcription

## 2. Current pipeline (recap)

```
blob: foo.pdf
   │
   ├─ (oversized?) → scripts/split_oversized_pdfs.py → foo_partNN.pdf
   │
   ▼
Azure AI Search blob indexer
   ├─ OcrSkill on normalized images
   ├─ MergeSkill (text + ocrText → mergedContent)
   ├─ SplitSkill (mergedContent → pages)
   └─ AzureOpenAIEmbeddingSkill → uap-explorer-chunks-v2
        │
        └─ enrich_v2_metadata() ← CSV store (agency, dates, location, document_id)
```

The blob indexer **does not natively parse audio or video.** Anything
upstream of "indexer reads a blob" must be done by us.

## 3. Proposed architecture

```
blob: foo.mp4                                    blob: foo.mp4.transcript.txt
   │                                                ▲
   ▼                                                │
scripts/transcribe_videos.py                        │
   ├─ enumerate uap-files for *.mp4 / *.mov / ...   │
   ├─ skip if sibling .transcript.txt already exists│
   ├─ submit Azure AI Speech batch transcription job│
   ├─ poll until done                               │
   └─ write transcript .txt + .json (timestamps) ───┘
                                                    │
                                                    ▼
                                  Azure AI Search blob indexer
                                  (same skillset; .txt parses cleanly)
                                                    │
                                                    ▼
                                  uap-explorer-chunks-v2 chunks tagged
                                  with the original video's metadata
                                                    │
                                                    ▼
                                  /api/ask citations reference foo.mp4
                                  → frontend renders inline <video> player
```

Key design decision: **the transcript becomes a sibling blob.** This keeps
all existing infrastructure (indexer, chunker, embedder, enrichment, hybrid
search) unchanged, and lets a human inspect/correct the transcript if
needed.

## 4. Technology choice

### Recommendation: Azure AI Speech — Batch Transcription (REST v3.2)

| Criterion | Azure AI Speech (batch) | Azure Video Indexer | AOAI Whisper |
|---|---|---|---|
| Cost per minute (audio) | $$ | $$$$ | $$ |
| Async / many-file friendly | ✅ batch jobs | ✅ but heavier | ❌ sync only |
| File size limit | none (uses blob URLs) | none | 25 MB per request |
| Spoken word accuracy | Excellent | Excellent | Excellent |
| Speaker diarization | ✅ optional | ✅ | ❌ |
| Word-level timestamps | ✅ | ✅ | ✅ |
| On-screen text (OCR) | ❌ | ✅ | ❌ |
| Face / object detection | ❌ | ✅ | ❌ |
| Auth model | Container-app secret (key) or MDI | API key | Existing AOAI |
| Fits existing pipeline | Best (output is text) | Output is JSON insight tree | Best |

Pick **Azure AI Speech batch** for v1. We already have an
`ai-services-key` secret on the Container App (AI Services multi-service
account) which includes Speech — no new resource needed.

If we later want on-screen text and visual analysis, layer **Video Indexer**
on top in a v2 follow-up.

## 5. Components to build

### 5.1 `scripts/transcribe_videos.py` (new)

CLI script, runnable locally and from the backend container.

Inputs:
- `--container uap-files` (default)
- `--prefix ''` (optional blob prefix filter)
- `--locale en-US` (default; allow `auto` for language ID)
- `--dry-run`

Per-blob behavior:
1. List blobs in `uap-files` with extension in
   `{.mp4,.mov,.mkv,.webm,.avi,.wav,.mp3,.m4a,.flac,.ogg}`.
2. Skip if sibling `<name>.transcript.txt` already exists **and** is newer
   than the source (idempotent like the PDF splitter).
3. Mint a short-lived **user-delegation SAS** for the source blob.
4. POST to Speech batch:
   `https://{region}.api.cognitive.microsoft.com/speechtotext/v3.2/transcriptions`
   ```json
   {
     "displayName": "uap-video-{blob_basename}",
     "locale": "en-US",
     "contentUrls": ["<sas-url>"],
     "properties": {
       "diarizationEnabled": true,
       "wordLevelTimestampsEnabled": true,
       "punctuationMode": "DictatedAndAutomatic",
       "profanityFilterMode": "None"
     }
   }
   ```
5. Poll the job URI every 30 s until `status == "Succeeded"` or `Failed`.
6. Fetch the result JSON; build two outputs:
   - `<basename>.transcript.txt` — plain text, one paragraph per
     diarized speaker turn, suitable for the indexer.
   - `<basename>.transcript.json` — `{ segments: [{ start, end, speaker, text }] }`
     for future "jump to moment" UI.
7. Upload both back to `uap-files` (so the indexer sees them).
8. Append/upsert a CSV row keyed by `document_id = sha1(blob_url)[:16]`
   with `local_file_path = <basename>.mp4` and best-effort metadata
   (filename parsing) so `enrich_v2_metadata` can fill agency / dates.

Concurrency:
- Submit up to N (e.g. 8) batch jobs in parallel; poll all in a single
  loop. Batch service is the cost bottleneck, not local CPU.

Error handling:
- Persist a `<basename>.transcript.error.json` on failure so reruns skip
  the broken file and the admin can inspect.

### 5.2 Indexer / skillset changes

The current blob indexer is restricted to PDFs via the `indexedFileNameExtensions`
parameter. Widen it to accept text artifacts:

```jsonc
"parameters": {
  "configuration": {
    "indexedFileNameExtensions": ".pdf,.txt",
    "excludedFileNameExtensions": ".bigskip,.json,.error.json",
    "parsingMode": "default"
  }
}
```

OCR / MergeSkill are no-ops on `.txt` (no embedded images), so the existing
skillset works unchanged. Chunking + embedding flow identically.

Important: the **video blob itself** (`.mp4`) is still picked up by the
indexer if we widen extensions, and it cannot be parsed. So we leave video
extensions OUT of `indexedFileNameExtensions` — only the `.transcript.txt`
is indexed. The `.mp4` stays in the container purely so the frontend can
stream it.

Field-mapping addition in `_indexer_def()`:
- When `blob_name` ends in `.transcript.txt`, strip that suffix for the
  `title` / display fields (or do it client-side in
  `enrich_v2_metadata`). This way citations point at the playable video.

### 5.3 `enrich_v2_metadata()` extensions

Add to the lookup-key derivation:
- For a chunk whose `blob_name` ends in `.transcript.txt`, also try the
  basename minus `.transcript.txt` (e.g. `foo.mp4`) when resolving
  against CSV rows.
- Persist `media_type: "video" | "audio" | "document"` on each v2 chunk
  (new optional field) so the frontend can branch on render.

New index field (additive, no rebuild required if added as `retrievable`
non-searchable):
```
media_type        Edm.String   filterable, facetable, retrievable
transcript_uri    Edm.String   retrievable (deep-link to .transcript.json for timestamps)
```

### 5.4 CSV / store updates

Two options; recommend (a):

(a) **Single CSV, mixed media**
- Add columns: `media_type`, `duration_seconds`, `language`
- Video rows have `local_file_path = foo.mp4`
- `DocumentRecord` (already a Pydantic model in
  [backend/app/models.py](backend/app/models.py)) gains those three
  fields with defaults so existing PDF rows keep working.

(b) **Separate `videos.csv`** merged at load time. More plumbing; skip.

### 5.5 Backend changes

- New admin endpoint `POST /api/admin/transcribe-videos` that shells out
  to (or imports) `transcribe_videos.py` for a manual kick. Same auth
  pattern as `/api/admin/search-indexer/enrich`.
- `ask_service.py` citation builder: if `media_type == "video"`, attach
  `transcript_uri` and a `play_url` (blob SAS) to the citation so the
  frontend can render a player + jump-to-segment control.
- No changes needed to hybrid search — it operates on `content_vector`
  and `content` which are populated from the transcript text.

### 5.6 Frontend changes (out of scope for this doc, but flagged)

- `Citation` type gains `media_type`, `play_url`, `transcript_uri`,
  optional `segments[]`.
- `EvidencePanel` / `AskAnswer` renders a `<video controls>` element
  when `media_type === 'video'`, with chapter markers from the matched
  segment.

### 5.7 Infrastructure

No new Azure resources required *if* the existing AI Services
multi-service account is in a region that supports Speech batch
transcription v3.2 (eastus does). The same `ai-services-key` secret
unlocks it.

If we hit throughput limits later, provision a dedicated Speech resource
and add a second secret.

## 6. Cost / runtime estimates

Rough order-of-magnitude (eastus list pricing, May 2026):
- Speech batch transcription: ~$0.36 per audio-hour (standard model)
- Embedding (text-embedding-3-large): ~$0.13 per 1M tokens; a 1-hour
  transcript is ~9k tokens → fraction of a cent
- Storage delta: transcripts are tiny (≤ 100 KB per hour of audio)

For 100 video-hours: < $40 one-time, < $0.10 per re-embed.

## 7. Rollout plan

1. **Land schema fields** (`media_type`, `transcript_uri`) on v2 index as
   additive, non-breaking. Run `setup_all()` (idempotent) to apply.
2. **Build `transcribe_videos.py`**; test against a single small sample
   blob locally. Verify transcript fidelity.
3. **Widen indexer** to `.pdf,.transcript.txt`. Reset + rerun on a
   single transcript to confirm chunks land in v2.
4. **Extend `enrich_v2_metadata`** for video → CSV joining; run.
5. **Wire `/api/ask`** to surface `media_type` + `play_url`. Backend
   smoke test.
6. **Frontend** video citation rendering. UI smoke test.
7. **Bulk transcribe** the full video corpus; let the indexer pick up
   transcripts automatically (or trigger run).
8. **Deploy** new backend revision; commit; push.

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Long videos blow Speech quota | Cap parallelism to 8; checkpoint per-blob; resumable |
| Poor audio quality → garbage transcript | Persist `.transcript.json` with confidence scores; flag low-confidence files in admin UI for manual review |
| Multi-language / non-English clips | Use locale `auto` with language ID; index per detected locale; tag chunks with `language` |
| Speaker labels are anonymous (`Speaker 1`) | Acceptable for v1; future enhancement: speaker enrollment / identification |
| Transcript drift if source video re-uploaded | Detect by ETag / last-modified; re-run transcription when source newer than transcript |
| User searches for visual content ("saucer-shaped craft on screen") | Out of scope for v1 — document as future Video Indexer add-on |

## 9. Open questions

1. Do we want speaker diarization in v1? (Recommended: yes — cheap and
   improves citation utility.)
2. Should the `.mp4` itself be served via a SAS-protected proxy endpoint
   on the backend, or via the public blob URL? (Recommend backend proxy
   so we can rate-limit and audit.)
3. Where do we capture video metadata (capture date, sensor, callsign,
   classification)? Manual CSV row vs. filename-parser convention vs.
   admin UI form?
4. Do we want a per-segment "jump to moment" UI in v1, or just "play
   from start"? (Recommend start; segment-level can ship after.)

## 10. Acceptance criteria for "Phase 3 done"

- Drop an `.mp4` into `uap-files`, trigger the admin endpoint.
- Within reasonable time, `/api/search?q=<phrase from the video>`
  returns chunks pointing at that video.
- `/api/ask` answers a question about the video with cited segments.
- Frontend renders the video inline with the matched citation.
- All artifacts (transcript text + JSON) are durably stored in blob and
  the process is idempotent / resumable.
