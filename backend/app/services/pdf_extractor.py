"""PDF text extraction.

Primary path: Azure Document Intelligence (`prebuilt-read`) — handles scanned PDFs.
Fallback: pypdf — fast for text-based PDFs, returns nothing for image-only scans.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Tuple

from ..config import settings
from .azure_clients import document_intelligence_client

log = logging.getLogger(__name__)


def extract_with_pypdf(pdf_path: Path) -> List[Tuple[int, str]]:
    """Returns [(page_number_1based, text), ...]."""
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    pages: List[Tuple[int, str]] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as e:  # noqa: BLE001
            log.warning("pypdf failed on page %s of %s: %s", i, pdf_path.name, e)
            text = ""
        pages.append((i, text.strip()))
    return pages


def extract_with_doc_intelligence(pdf_bytes: bytes) -> List[Tuple[int, str]]:
    """Use Doc Intelligence prebuilt-read for OCR-quality extraction."""
    from azure.ai.documentintelligence.models import AnalyzeDocumentRequest

    client = document_intelligence_client()
    poller = client.begin_analyze_document(
        "prebuilt-read",
        AnalyzeDocumentRequest(bytes_source=pdf_bytes),
    )
    result = poller.result()
    pages: List[Tuple[int, str]] = []
    for page in result.pages or []:
        lines = [ln.content for ln in (page.lines or [])]
        pages.append((page.page_number, "\n".join(lines).strip()))
    return pages


def extract_pages(
    pdf_path: Path,
    use_doc_intelligence: bool = True,
) -> List[Tuple[int, str]]:
    """Try pypdf first; if it returns mostly empty pages, fall back to Doc Intelligence.

    If Doc Intelligence is unavailable (e.g. key auth disabled), fall back to the
    pypdf result — even if sparse — rather than failing the document outright.
    The caller decides what to do with an empty result.
    """
    pypdf_pages = extract_with_pypdf(pdf_path)
    text_pages = sum(1 for _, t in pypdf_pages if len(t) > 50)
    coverage = text_pages / max(1, len(pypdf_pages))

    if coverage >= 0.5 or not use_doc_intelligence:
        return pypdf_pages

    if not settings.docintel_endpoint:
        log.warning("Doc Intelligence not configured; returning sparse pypdf result for %s", pdf_path.name)
        return pypdf_pages

    log.info(
        "Falling back to Document Intelligence for %s (pypdf coverage %.0f%%)",
        pdf_path.name,
        coverage * 100,
    )
    try:
        with pdf_path.open("rb") as fh:
            data = fh.read()
        return extract_with_doc_intelligence(data)
    except Exception as e:  # noqa: BLE001
        log.warning("Doc Intelligence failed on %s: %s", pdf_path.name, e)
        # Use whatever pypdf gave us. If it was empty too, the caller will see it.
        return pypdf_pages


def chunk_page_text(text: str, max_chars: int, overlap: int) -> List[str]:
    """Sliding-window chunker that respects paragraph and sentence boundaries."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: List[str] = []
    i = 0
    n = len(text)
    while i < n:
        end = min(i + max_chars, n)
        # Try to break on paragraph or sentence boundary
        if end < n:
            for boundary in ("\n\n", ". ", "\n", " "):
                idx = text.rfind(boundary, i + int(max_chars * 0.5), end)
                if idx != -1:
                    end = idx + len(boundary)
                    break
        chunks.append(text[i:end].strip())
        if end >= n:
            break
        i = max(end - overlap, i + 1)
    return [c for c in chunks if c]
