#!/usr/bin/env python3
"""
Download all file links from the Department of War PURSUE/UFO CSV and zip them.

Usage:
  python download_and_zip_ufo_files.py --csv uap-csv.csv

Outputs:
  ufo_release_01_files/                         # downloaded PDFs/images
  ufo_release_01_download_manifest.csv          # status for each URL
  war_gov_ufo_release_01_documents.zip          # single ZIP containing downloaded files
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import time
import urllib.request
import urllib.error
import zipfile
from pathlib import Path
from urllib.parse import urlparse, unquote

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) UFO release downloader/1.0"
INVALID_CHARS = r'<>:"/\\|?*'


def safe_filename_from_url(url: str) -> str:
    path = urlparse(url).path
    name = unquote(Path(path).name).strip()
    if not name:
        name = "downloaded_file"
    trans = str.maketrans({ch: "_" for ch in INVALID_CHARS})
    return name.translate(trans)


def read_links(csv_path: Path) -> list[str]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if "PDF | Image Link" not in reader.fieldnames:
            raise ValueError("CSV is missing the 'PDF | Image Link' column.")
        seen = set()
        links = []
        for row in reader:
            url = (row.get("PDF | Image Link") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            links.append(url)
    return links


def download_file(url: str, dest: Path, retries: int, throttle: float) -> tuple[str, int | None, str]:
    if dest.exists() and dest.stat().st_size > 0:
        return "skipped_existing", dest.stat().st_size, ""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    headers = {"User-Agent": USER_AGENT}
    last_error = ""
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=120) as resp, part.open("wb") as out:
                total = 0
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    total += len(chunk)
            part.replace(dest)
            if throttle:
                time.sleep(throttle)
            return "downloaded", dest.stat().st_size, ""
        except Exception as e:
            last_error = f"attempt {attempt}: {type(e).__name__}: {e}"
            if part.exists():
                try:
                    part.unlink()
                except OSError:
                    pass
            time.sleep(min(10, attempt * 2))
    return "failed", None, last_error


def zip_files(files: list[Path], zip_path: Path, base_dir: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as zf:
        for file in files:
            if file.exists() and file.is_file() and file.stat().st_size > 0:
                zf.write(file, arcname=str(file.relative_to(base_dir)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="uap-csv.csv", help="Path to uap-csv.csv")
    ap.add_argument("--out-dir", default="ufo_release_01_files", help="Download folder")
    ap.add_argument("--zip", default="war_gov_ufo_release_01_documents.zip", help="Output ZIP path")
    ap.add_argument("--manifest", default="ufo_release_01_download_manifest.csv", help="Download status CSV")
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--throttle", type=float, default=0.5, help="Seconds to pause between downloads")
    args = ap.parse_args()

    csv_path = Path(args.csv).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    zip_path = Path(args.zip).expanduser().resolve()
    manifest_path = Path(args.manifest).expanduser().resolve()

    links = read_links(csv_path)
    print(f"Found {len(links)} unique downloadable links in {csv_path.name}.")

    records = []
    downloaded_files = []
    for i, url in enumerate(links, start=1):
        filename = safe_filename_from_url(url)
        dest = out_dir / filename
        print(f"[{i}/{len(links)}] {filename}")
        status, size, error = download_file(url, dest, args.retries, args.throttle)
        print(f"    {status}" + (f" ({size:,} bytes)" if size else ""))
        if status in {"downloaded", "skipped_existing"}:
            downloaded_files.append(dest)
        records.append({"index": i, "url": url, "filename": filename, "status": status, "size_bytes": size or "", "error": error})

    with manifest_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["index", "url", "filename", "status", "size_bytes", "error"])
        writer.writeheader()
        writer.writerows(records)

    print(f"Creating ZIP: {zip_path}")
    zip_files(downloaded_files, zip_path, out_dir)
    print(f"Done. ZIP contains {len(downloaded_files)} files: {zip_path}")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
