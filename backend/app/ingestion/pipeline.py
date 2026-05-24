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
import tempfile
import threading
from pathlib import Path
from typing import List, Optional, Tuple

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

# Populated at the start of each run with the set of blob names currently in
# the uap-files container. Lets selection + extraction fall back to blob when
# the deployed container has no local copy of the PDF.
_BLOB_NAMES: set[str] = set()


def _refresh_blob_index() -> set[str]:
    global _BLOB_NAMES
    try:
        _BLOB_NAMES = set(blob_storage.list_blobs())
    except Exception as e:  # noqa: BLE001
        status.log(f"Blob listing unavailable: {e}")
        _BLOB_NAMES = set()
    return _BLOB_NAMES


def _has_source(doc: DocumentRecord) -> bool:
    """True if we can obtain the original file via local disk OR blob."""
    if doc.local_file_path and Path(doc.local_file_path).exists():
        return True
    name = _filename_from(doc)
    return bool(name and name in _BLOB_NAMES)


def _resolve_source(doc: DocumentRecord) -> Tuple[Optional[Path], Optional[Path], bool]:
    """Return (source_path, temp_path_to_cleanup, already_in_blob).

    Prefers local disk. Falls back to streaming the blob into a temp file.
    """
    if doc.local_file_path:
        p = Path(doc.local_file_path)
        if p.exists():
            return p, None, False

    name = _filename_from(doc)
    if not name or name not in _BLOB_NAMES:
        return None, None, False

    try:
        data = blob_storage.download_blob_bytes(name)
    except Exception as e:  # noqa: BLE001
        status.log(f"  blob download failed for {name}: {e}")
        return None, None, False

    suffix = Path(name).suffix or ".pdf"
    tf = tempfile.NamedTemporaryFile(prefix="uap-blob-", suffix=suffix, delete=False)
    try:
        tf.write(data)
    finally:
        tf.close()
    return Path(tf.name), Path(tf.name), True


# --------------------------------------------------------------------- helpers
def _select_documents(document_ids: Optional[List[str]], max_docs: int) -> List[DocumentRecord]:
    docs = store.documents
    if document_ids:
        chosen = [d for d in docs if d.document_id in set(document_ids)]
    else:
        # Default selection: PDFs we can obtain a source file for, either from
        # local disk OR from the blob container. Smallest first so quick wins
        # happen before the large scanned files.
        candidates = [d for d in docs if (d.file_type or "") == "pdf" and _has_source(d)]
        if not candidates:
            candidates = [d for d in docs if _has_source(d)]

        def _size(d: DocumentRecord) -> int:
            try:
                if d.local_file_path and Path(d.local_file_path).exists():
                    return Path(d.local_file_path).stat().st_size
            except Exception:
                pass
            return 1 << 62  # blob-only files sort last (size unknown)

        chosen = sorted(candidates, key=_size)
    return chosen[: max(0, max_docs)]


def _list_indexed_document_ids() -> set[str]:
    """Return the set of document_ids that already have chunks in the search index."""
    try:
        client = search_index.search_client()
    except Exception:
        return set()
    seen: set[str] = set()
    try:
        results = client.search(
            search_text="*",
            facets=["document_id,count:10000"],
            top=0,
        )
        # Touch results so the response is materialized, then read facets.
        try:
            list(results)  # may yield nothing because top=0
        except Exception:
            pass
        facets = results.get_facets() or {}
        for entry in facets.get("document_id", []) or []:
            v = entry.get("value")
            if v:
                seen.add(v)
    except Exception:
        pass
    if seen:
        return seen
    # Fallback: paginate through chunks pulling distinct document_ids.
    try:
        results = client.search(
            search_text="*", select=["document_id"], top=1000
        )
        for r in results:
            v = r.get("document_id") if isinstance(r, dict) else getattr(r, "document_id", None)
            if v:
                seen.add(v)
    except Exception:
        pass
    return seen


def _select_documents_for_summaries(
    document_ids: Optional[List[str]], max_docs: int
) -> List[DocumentRecord]:
    """Selection for summaries-only mode: include any PDF with text available
    via cached extraction, local file, OR existing chunks in the search index.
    """
    docs = store.documents
    if document_ids:
        return [d for d in docs if d.document_id in set(document_ids)][: max(0, max_docs)]

    indexed_ids = _list_indexed_document_ids()

    def _has_text(d: DocumentRecord) -> bool:
        if d.local_file_path and Path(d.local_file_path).exists():
            return True
        if (EXTRACTED_DIR / f"{d.document_id}.json").exists():
            return True
        if d.document_id in indexed_ids:
            return True
        name = _filename_from(d)
        return bool(name and name in _BLOB_NAMES)

    candidates = [d for d in docs if (d.file_type or "").lower() == "pdf" and _has_text(d)]

    def _size(d: DocumentRecord) -> int:
        try:
            return Path(d.local_file_path).stat().st_size if d.local_file_path else 1 << 62
        except Exception:
            return 1 << 62

    candidates.sort(key=_size)
    return candidates[: max(0, max_docs)]


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


def _load_cached_extracted_text(doc_id: str) -> Optional[str]:
    """Return concatenated page text from the cached extraction JSON, or None."""
    p = EXTRACTED_DIR / f"{doc_id}.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        pages = data.get("pages") or []
        return "\n\n".join((pg.get("text") or "") for pg in pages).strip() or None
    except Exception:
        return None


def _load_text_from_search_index(doc_id: str, max_chunks: int = 400) -> Optional[str]:
    """Reconstruct document text from chunks already indexed in Azure AI Search.

    Used as a fallback when neither the local PDF nor the cached extraction
    JSON is available (e.g. the deployed container that only has access to
    the search index, not the original PDFs).
    """
    try:
        chunks = search_index.get_document_chunks(doc_id, max_chunks=max_chunks)
    except Exception:
        return None
    if not chunks:
        return None
    text = "\n\n".join((c.get("content") or "") for c in chunks).strip()
    return text or None


def _process_one_summary_only(doc: DocumentRecord, regenerate: bool) -> None:
    """Generate (or regenerate) only the AI summary for one document.

    Skips blob upload, chunking, embedding, and search-index writes. Sources
    the document text in this order:
      1. Cached extraction JSON in data/processed/extracted/.
      2. Local PDF on disk (re-extracts and caches).
      3. Chunks already stored in Azure AI Search (deployed-container path).
    """
    status.set_current(doc.title)
    status.log(f"Summary-only: {doc.title}")

    if not regenerate and (SUMMARY_DIR / f"{doc.document_id}.json").exists():
        status.record_skipped(f"summary already cached: {doc.title}")
        return

    if (doc.file_type or "").lower() != "pdf":
        status.record_skipped(f"non-PDF file type: {doc.title}")
        return

    full_text = _load_cached_extracted_text(doc.document_id)
    if not full_text and doc.local_file_path and Path(doc.local_file_path).exists():
        try:
            pages = extract_pages(Path(doc.local_file_path), use_doc_intelligence=True)
        except Exception as e:  # noqa: BLE001
            status.record_error(doc.document_id, doc.title, f"extraction failed: {e}")
            return
        full_text = "\n\n".join(t for _, t in pages if t).strip()
        if full_text:
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

    if not full_text:
        # Last-resort fallback: pull the chunked text back out of the search index.
        full_text = _load_text_from_search_index(doc.document_id)
        if full_text:
            status.log(f"  using text reconstructed from search index for {doc.title}")

    if not full_text:
        status.record_skipped(
            f"no text available (no local file, no cached extraction, no indexed chunks): {doc.title}"
        )
        return

    try:
        summary = _generate_summary(doc, full_text)
        _save_summary(doc.document_id, summary)
        status.log(f"  → summary cached for {doc.title}")
        status.record_completed()
    except Exception as e:  # noqa: BLE001
        status.record_error(doc.document_id, doc.title, f"summary failed: {e}")


# ---------------------------------------------------------------- main runner
def _process_one(doc: DocumentRecord) -> None:
    status.set_current(doc.title)
    status.log(f"Processing: {doc.title}")

    if (doc.file_type or "").lower() != "pdf":
        status.record_skipped(f"non-PDF file type: {doc.title}")
        return

    source_path, temp_path, from_blob = _resolve_source(doc)
    if source_path is None:
        status.record_skipped(
            f"no source available (no local file, no blob): {doc.title}"
        )
        return

    if from_blob:
        status.log(f"  using blob source for {doc.title}")

    try:
        # Blob upload (best-effort, non-fatal). Skipped when the source itself
        # came from blob — it's already there.
        if not from_blob:
            try:
                _ensure_uploaded(doc)
            except Exception as e:  # noqa: BLE001
                status.log(f"Blob upload failed for {doc.title}: {e}")

        # Extract
        try:
            pages = extract_pages(source_path, use_doc_intelligence=True)
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
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass


def run_ingestion(
    document_ids: Optional[List[str]] = None,
    max_docs: Optional[int] = None,
    ensure_index: bool = True,
    summaries_only: bool = False,
    regenerate_summaries: bool = False,
) -> dict:
    """Synchronous run. Use run_ingestion_async() from the API layer."""
    if not _RUN_LOCK.acquire(blocking=False):
        return {"started": False, "reason": "ingestion already running"}

    try:
        cap = max_docs if max_docs is not None else settings.ingestion_max_docs
        _refresh_blob_index()
        if summaries_only:
            targets = _select_documents_for_summaries(document_ids, cap)
        else:
            targets = _select_documents(document_ids, cap)
        mode = "summaries-only" if summaries_only else "api"
        status.begin_run(target_count=len(targets), max_docs=cap, mode=mode)

        if ensure_index and not summaries_only:
            try:
                search_index.create_or_update_index()
                status.log("Search index ensured.")
            except Exception as e:  # noqa: BLE001
                status.log(f"Index create/update failed: {e}")

        for doc in targets:
            try:
                if summaries_only:
                    _process_one_summary_only(doc, regenerate=regenerate_summaries)
                else:
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
    summaries_only: bool = False,
    regenerate_summaries: bool = False,
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
            "summaries_only": summaries_only,
            "regenerate_summaries": regenerate_summaries,
        },
        daemon=True,
        name="uap-ingestion",
    )
    t.start()
    return {"started": True}
