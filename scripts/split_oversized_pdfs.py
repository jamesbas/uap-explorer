"""Split oversized PDFs in blob storage into <16MB parts for the AI Search indexer.

For each blob exceeding ``MAX_BYTES``:
  1. Download to a temp file.
  2. Slice by page-groups so each output stays under the target size.
  3. Upload parts as ``<stem>_partNN.pdf``.
  4. Rename the original to ``<orig>.pdf.bigskip`` so the indexer (which
     only picks ``.pdf``) ignores it on future runs.

Idempotent: if part blobs already exist for an original, it is skipped.

Usage:
    cd backend && .venv\\Scripts\\python.exe ..\\scripts\\split_oversized_pdfs.py
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
from pathlib import Path

# Allow running from repo root or scripts/
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / "backend" / ".env")

from azure.storage.blob import BlobServiceClient  # noqa: E402
from pypdf import PdfReader, PdfWriter  # noqa: E402

CONTAINER = os.environ.get("AZURE_STORAGE_CONTAINER", "uap-files")
ACCOUNT = os.environ["AZURE_STORAGE_ACCOUNT"]
CONN = os.environ.get("AZURE_STORAGE_CONNECTION_STRING") or (
    f"DefaultEndpointsProtocol=https;AccountName={ACCOUNT};"
    f"AccountKey={os.environ['AZURE_STORAGE_ACCOUNT_KEY']};EndpointSuffix=core.windows.net"
)
MAX_BYTES = 16 * 1024 * 1024  # AI Search Basic tier per-blob limit
TARGET_PART_BYTES = 12 * 1024 * 1024  # safety margin


def _list_oversized(container_client) -> list[tuple[str, int]]:
    out = []
    for b in container_client.list_blobs():
        if not b.name.lower().endswith(".pdf"):
            continue
        if b.size > MAX_BYTES:
            out.append((b.name, b.size))
    return sorted(out, key=lambda x: x[1])


def _existing_parts(container_client, stem: str) -> list[str]:
    prefix = f"{stem}_part"
    return [b.name for b in container_client.list_blobs(name_starts_with=prefix)]


def _split_pdf_to_parts(local_pdf: Path, target_bytes: int) -> list[bytes]:
    reader = PdfReader(str(local_pdf))
    n_pages = len(reader.pages)
    total = local_pdf.stat().st_size
    avg_per_page = max(total // max(n_pages, 1), 1)
    base_pages_per_part = max(int(target_bytes / avg_per_page), 1)

    parts: list[bytes] = []
    i = 0
    while i < n_pages:
        # Reset to base size for each new part — halving applies only
        # to the current (oversize) candidate part, not globally.
        pages_per_part = base_pages_per_part
        while True:
            writer = PdfWriter()
            end = min(i + pages_per_part, n_pages)
            for p in range(i, end):
                writer.add_page(reader.pages[p])
            buf = io.BytesIO()
            writer.write(buf)
            data = buf.getvalue()

            if len(data) <= MAX_BYTES or (end - i) <= 1:
                parts.append(data)
                i = end
                break
            # Halve and retry this candidate (do not advance i)
            pages_per_part = max((end - i) // 2, 1)
    return parts


def main() -> int:
    svc = BlobServiceClient.from_connection_string(CONN)
    cc = svc.get_container_client(CONTAINER)

    oversized = _list_oversized(cc)
    print(f"Found {len(oversized)} oversized PDFs (> {MAX_BYTES/1e6:.1f} MB)")

    for name, size in oversized:
        stem = name[:-4]  # strip .pdf
        existing = _existing_parts(cc, stem)
        if existing:
            print(f"  SKIP {name} ({size/1e6:.1f} MB) — already split into {len(existing)} parts")
            continue

        print(f"\n>>> {name}  ({size/1e6:.1f} MB)")
        # Download
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp_path = Path(tmp.name)
        try:
            print(f"    downloading…")
            with open(tmp_path, "wb") as f:
                stream = cc.download_blob(name)
                for chunk in stream.chunks():
                    f.write(chunk)

            print(f"    splitting…")
            try:
                parts = _split_pdf_to_parts(tmp_path, TARGET_PART_BYTES)
            except Exception as e:
                print(f"    !! split failed: {e}")
                continue
            print(f"    -> {len(parts)} parts")

            for idx, data in enumerate(parts, start=1):
                part_name = f"{stem}_part{idx:02d}.pdf"
                cc.upload_blob(
                    part_name, data, overwrite=True,
                    content_settings=None,
                )
                print(f"    uploaded {part_name}  ({len(data)/1e6:.1f} MB)")

            # Rename original (copy to .bigskip then delete original)
            skip_name = f"{name}.bigskip"
            src_url = cc.get_blob_client(name).url
            dest = cc.get_blob_client(skip_name)
            dest.start_copy_from_url(src_url)
            # Poll a couple seconds for copy completion
            import time
            for _ in range(60):
                props = dest.get_blob_properties()
                if (props.copy.status or "").lower() == "success":
                    break
                time.sleep(1)
            cc.delete_blob(name)
            print(f"    renamed original -> {skip_name}")
        finally:
            try:
                tmp_path.unlink()
            except Exception:
                pass

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
