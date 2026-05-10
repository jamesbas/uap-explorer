"""End-to-end ingestion pipeline.

For each selected document:
  1. Ensure original file exists locally (under UAP_FILE_ROOT). If missing, skip.
  2. Upload to Azure Blob Storage if not already there.
  3. Extract text page-by-page (pypdf, fall back to Doc Intelligence for scans).
  4. Chunk text.
  5. Embed chunks via Azure OpenAI.
  6. Upsert chunks into Azure AI Search (deletes prior chunks for that doc first).
  7. Generate + cache an AI summary.
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import List, Optional

from ..config import settings
from ..models import DocumentRecord
from ..services import blob_storage, openai_service, search_index
from ..services.pdf_extractor import chunk_page_text, extract_pages
from ..services.store import store
from . import status

log = logging.getLogger(__name__)

SUMMARY_DIR = settings.processed_root / "summaries"
EXTRACTED_DIR = settings.processed_root / "extracted"

_RUN_LOCK = threading.Lock()


# --------------------------------------------------------------------- helpers
def _select_documents(document_ids: Optional[List[str]], max_docs: int) -> List[DocumentRecord]:
    docs = store.documents
    if document_ids:
        chosen = [d for d in docs if d.document_id in set(document_ids)]
    else:
        # Default selection: PDFs we already have on disk, smallest first so
        # quick wins happen before the large scanned files.
        candidates = [d for d in docs if (d.file_type or "") == "pdf" and d.local_file_path]
        if not candidates:
            candidates = [d for d in docs if d.local_file_path]

        def _size(d: DocumentRecord) -> int:
            try:
                return Path(d.local_file_path).stat().st_size if d.local_file_path else 1 << 62
            except Exception:
                return 1 << 62

        chosen = sorted(candidates, key=_size)
    return chosen[: max(0, max_docs)]


def _filename_from(doc: DocumentRecord) -> Optional[str]:
    if doc.local_file_path:
        return Path(doc.local_file_path).name
    if doc.source_url:
        return doc.source_url.rsplit("/", 1)[-1]
    return None


def _ensure_uploaded(doc: DocumentRecord) -> Optional[str]:
    name = _filename_from(doc)
    if not name or not doc.local_file_path:
        return None
    p = Path(doc.local_file_path)
    if not p.exists():
        return None
    if not blob_storage.blob_exists(name):
        status.log(f"Uploading to blob: {name}")
        blob_storage.upload_file(p, blob_name=name)
    return name


def _build_chunks(doc: DocumentRecord, pages) -> list[dict]:
    out: list[dict] = []
    for page_num, page_text in pages:
        for ci, piece in enumerate(
            chunk_page_text(page_text, settings.chunk_chars, settings.chunk_overlap)
        ):
            out.append(
                {
                    "chunk_id": f"{doc.document_id}-p{page_num}-{ci}",
                    "document_id": doc.document_id,
                    "title": doc.title,
                    "agency": doc.agency or "",
                    "release_date": doc.release_date or "",
                    "incident_date": doc.incident_date or "",
                    "location": doc.incident_location or "",
                    "page_number": page_num,
                    "chunk_index": ci,
                    "content": piece,
                    "source_url": doc.source_url or "",
                }
            )
    return out


SUMMARY_SYSTEM = (
    "You are an analyst summarizing a government-released UAP record. "
    "Use only the provided document text. Be neutral, evidence-first, and concise. "
    "Do not speculate about extraterrestrial origins. If the source does not establish "
    "a fact, say so explicitly. Respond ONLY with valid JSON matching the requested schema."
)

SUMMARY_USER_TEMPLATE = """Summarize the following UAP record.

Title: {title}
Agency: {agency}
Release date: {release_date}
Incident date: {incident_date}
Incident location: {incident_location}

--- BEGIN DOCUMENT TEXT (truncated) ---
{body}
--- END DOCUMENT TEXT ---

Respond with this JSON shape:
{{
  "summary": "2-4 sentence neutral summary in plain English",
  "key_facts": ["short factual bullets grounded in the text"],
  "evidence_types": ["e.g. eyewitness, photo, radar, sensor, transcript"],
  "notable_locations": ["string"],
  "notable_dates": ["string"],
  "possible_topics": ["string"],
  "uncertainty_notes": "what the source does NOT establish"
}}
"""


def _generate_summary(doc: DocumentRecord, full_text: str) -> dict:
    # Cap the prompt size — most summary value comes from the first ~24k chars.
    body = full_text[:24000]
    prompt = SUMMARY_USER_TEMPLATE.format(
        title=doc.title,
        agency=doc.agency or "Unknown",
        release_date=doc.release_date or "Unknown",
        incident_date=doc.incident_date or "Unknown",
        incident_location=doc.incident_location or "Unknown",
        body=body,
    )
    text, usage = openai_service.chat_completion(
        SUMMARY_SYSTEM, prompt, temperature=0.1, max_tokens=1200
    )
    status.add_tokens(
        prompt=usage.get("prompt_tokens", 0),
        completion=usage.get("completion_tokens", 0),
    )
    parsed: dict
    try:
        # Strip code fences if present
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].lstrip()
        parsed = json.loads(cleaned)
    except Exception:
        parsed = {"summary": text, "key_facts": [], "evidence_types": [],
                  "notable_locations": [], "notable_dates": [],
                  "possible_topics": [], "uncertainty_notes": ""}
    parsed["_usage"] = usage
    return parsed


def _save_summary(doc_id: str, summary: dict) -> None:
    (SUMMARY_DIR / f"{doc_id}.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )


def get_cached_summary(doc_id: str) -> Optional[dict]:
    p = SUMMARY_DIR / f"{doc_id}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


# ---------------------------------------------------------------- main runner
def _process_one(doc: DocumentRecord) -> None:
    status.set_current(doc.title)
    status.log(f"Processing: {doc.title}")

    if (doc.file_type or "").lower() != "pdf":
        status.record_skipped(f"non-PDF file type: {doc.title}")
        return

    if not doc.local_file_path or not Path(doc.local_file_path).exists():
        status.record_skipped(f"local file missing for: {doc.title}")
        return

    # Blob upload (best-effort, non-fatal)
    try:
        _ensure_uploaded(doc)
    except Exception as e:  # noqa: BLE001
        status.log(f"Blob upload failed for {doc.title}: {e}")

    # Extract
    try:
        pages = extract_pages(Path(doc.local_file_path), use_doc_intelligence=True)
    except Exception as e:  # noqa: BLE001
        status.record_error(doc.document_id, doc.title, f"extraction failed: {e}")
        return
    full_text = "\n\n".join(t for _, t in pages if t)
    if not full_text.strip():
        status.record_error(doc.document_id, doc.title, "no extractable text (empty pages)")
        return

    # Cache extracted text
    try:
        (EXTRACTED_DIR / f"{doc.document_id}.json").write_text(
            json.dumps(
                {"document_id": doc.document_id, "title": doc.title,
                 "pages": [{"page": p, "text": t} for p, t in pages]},
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass

    # Chunks + embeddings
    chunks = _build_chunks(doc, pages)
    if not chunks:
        status.record_error(doc.document_id, doc.title, "no chunks produced")
        return

    status.log(f"  → {len(chunks)} chunks; embedding…")
    embeddings = openai_service.embed_texts([c["content"] for c in chunks])
    # Token estimate for embeddings
    est_tokens = sum(openai_service.count_tokens(c["content"]) for c in chunks)
    status.add_tokens(embedding=est_tokens)

    for c, vec in zip(chunks, embeddings):
        c["content_vector"] = vec

    # Upsert into search index (replace prior chunks for this doc)
    try:
        search_index.delete_document_chunks(doc.document_id)
    except Exception as e:  # noqa: BLE001
        status.log(f"  prior-chunk delete failed for {doc.title}: {e}")
    search_index.upload_chunks(chunks)
    status.log(f"  → indexed {len(chunks)} chunks for {doc.title}")

    # Summary
    try:
        summary = _generate_summary(doc, full_text)
        _save_summary(doc.document_id, summary)
        status.log(f"  → summary cached for {doc.title}")
    except Exception as e:  # noqa: BLE001
        status.log(f"  summary failed for {doc.title}: {e}")

    status.record_completed()


def run_ingestion(
    document_ids: Optional[List[str]] = None,
    max_docs: Optional[int] = None,
    ensure_index: bool = True,
) -> dict:
    """Synchronous run. Use run_ingestion_async() from the API layer."""
    if not _RUN_LOCK.acquire(blocking=False):
        return {"started": False, "reason": "ingestion already running"}

    try:
        cap = max_docs if max_docs is not None else settings.ingestion_max_docs
        targets = _select_documents(document_ids, cap)
        status.begin_run(target_count=len(targets), max_docs=cap, mode="api")

        if ensure_index:
            try:
                search_index.create_or_update_index()
                status.log("Search index ensured.")
            except Exception as e:  # noqa: BLE001
                status.log(f"Index create/update failed: {e}")

        for doc in targets:
            try:
                _process_one(doc)
            except Exception as e:  # noqa: BLE001
                status.record_error(doc.document_id, doc.title, str(e))

        st = status.get_status()
        summary = (
            f"Done. completed={st['completed']} failed={st['failed']} "
            f"skipped={st['skipped']} tokens={st['tokens']['total']}"
        )
        status.end_run(summary)
        return {"started": True, "summary": summary}
    finally:
        _RUN_LOCK.release()


def run_ingestion_async(
    document_ids: Optional[List[str]] = None,
    max_docs: Optional[int] = None,
    ensure_index: bool = True,
) -> dict:
    """Spawn ingestion in a background thread; returns immediately."""
    if status.is_running():
        return {"started": False, "reason": "ingestion already running"}

    t = threading.Thread(
        target=run_ingestion,
        kwargs={
            "document_ids": document_ids,
            "max_docs": max_docs,
            "ensure_index": ensure_index,
        },
        daemon=True,
        name="uap-ingestion",
    )
    t.start()
    return {"started": True}
