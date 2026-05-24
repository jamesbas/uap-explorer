#!/usr/bin/env python3
"""Upload a folder of release files to the `uap-files` blob container.

Usage examples:
    # Upload every file in ufo_release_02_files/ (skips files already present)
    python scripts/upload_release_to_blob.py --folder ufo_release_02_files

    # Re-upload everything, overwriting existing blobs
    python scripts/upload_release_to_blob.py --folder ufo_release_02_files --overwrite

    # Dry run (just show what would be uploaded)
    python scripts/upload_release_to_blob.py --folder ufo_release_02_files --dry-run

Reads Azure credentials from backend/.env (same config as the backend service).
The deployed admin "Run ingestion" button will pick up these blobs as ingest
candidates once Release 02 records are in the source CSV.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make `backend.app` importable when running from the repo root.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services import blob_storage  # noqa: E402  (after sys.path tweak)
from app.config import settings  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--folder",
        required=True,
        help="Path to a folder of files to upload (relative to repo root or absolute).",
    )
    ap.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-upload files even if a blob with the same name already exists.",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned actions without uploading.",
    )
    ap.add_argument(
        "--pattern",
        default="*",
        help="Glob pattern for files to include (default: *).",
    )
    args = ap.parse_args()

    folder = Path(args.folder)
    if not folder.is_absolute():
        folder = (REPO_ROOT / folder).resolve()
    if not folder.is_dir():
        print(f"ERROR: folder not found: {folder}", file=sys.stderr)
        return 2

    print(f"Source folder : {folder}")
    print(f"Container     : {settings.storage_container}")
    print(f"Account       : {settings.storage_account or '(from connection string)'}")
    print()

    files = sorted(p for p in folder.glob(args.pattern) if p.is_file())
    if not files:
        print("No files matched.")
        return 0

    # Snapshot existing blob names once.
    try:
        existing = set(blob_storage.list_blobs())
    except Exception as e:
        print(f"ERROR: could not list blobs: {e}", file=sys.stderr)
        return 1

    uploaded = 0
    skipped = 0
    failed = 0
    for f in files:
        present = f.name in existing
        if present and not args.overwrite:
            print(f"  skip   {f.name}  (already in container)")
            skipped += 1
            continue
        action = "would upload" if args.dry_run else ("re-upload" if present else "upload")
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  {action:<12} {f.name}  ({size_mb:,.2f} MB)")
        if args.dry_run:
            continue
        try:
            blob_storage.upload_file(f, blob_name=f.name)
            uploaded += 1
        except Exception as e:
            print(f"    FAILED: {e}", file=sys.stderr)
            failed += 1

    print()
    print(f"Done. uploaded={uploaded} skipped={skipped} failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
