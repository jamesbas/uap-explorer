#!/usr/bin/env python3
"""
Download all UFO release files using Edge browser with Playwright's native download handling.
Uses page.expect_download() to save files directly without base64 overhead.
"""
from __future__ import annotations

import argparse
import csv
import os
import time
import zipfile
from pathlib import Path
from urllib.parse import urlparse, unquote

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
        seen: set[str] = set()
        links: list[str] = []
        for row in reader:
            url = (row.get("PDF | Image Link") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            links.append(url)
    return links


def download_via_browser(page, url: str, dest: Path, retries: int, timeout_ms: int = 600_000) -> tuple[str, int | None, str]:
    """Use Playwright's native download event to save files directly."""
    if dest.exists() and dest.stat().st_size > 0:
        return "skipped_existing", dest.stat().st_size, ""

    dest.parent.mkdir(parents=True, exist_ok=True)
    last_error = ""

    for attempt in range(1, retries + 1):
        try:
            with page.expect_download(timeout=timeout_ms) as download_info:
                page.evaluate(
                    "(url) => { const a = document.createElement('a'); a.href = url; a.download = ''; document.body.appendChild(a); a.click(); a.remove(); }",
                    url
                )
            download = download_info.value
            download.save_as(str(dest))
            failure = download.failure()
            if failure:
                last_error = f"attempt {attempt}: download failed: {failure}"
                if dest.exists():
                    dest.unlink()
                time.sleep(min(10, attempt * 2))
                continue
            size = dest.stat().st_size
            if size == 0:
                last_error = f"attempt {attempt}: downloaded file is empty"
                dest.unlink()
                time.sleep(min(10, attempt * 2))
                continue
            return "downloaded", size, ""
        except Exception as e:
            last_error = f"attempt {attempt}: {type(e).__name__}: {e}"
            if dest.exists():
                try:
                    dest.unlink()
                except OSError:
                    pass
            time.sleep(min(10, attempt * 2))

    return "failed", None, last_error


def zip_files(files: list[Path], zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as zf:
        for file in files:
            if file.exists() and file.is_file() and file.stat().st_size > 0:
                zf.write(file, arcname=file.name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="uap-csv.csv")
    ap.add_argument("--out-dir", default="ufo_release_01_files")
    ap.add_argument("--zip", default="war_gov_ufo_release_01_documents.zip")
    ap.add_argument("--manifest", default="ufo_release_01_download_manifest.csv")
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--throttle", type=float, default=0.5)
    args = ap.parse_args()

    csv_path = Path(args.csv).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    zip_path = Path(args.zip).expanduser().resolve()
    manifest_path = Path(args.manifest).expanduser().resolve()

    links = read_links(csv_path)
    print(f"Found {len(links)} unique downloadable links.")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, channel="msedge")
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        print("Establishing browser session with war.gov...")
        page.goto("https://www.war.gov/", wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
        print(f"Session established: {page.title()}\n")

        records = []
        downloaded_files = []
        for i, url in enumerate(links, start=1):
            filename = safe_filename_from_url(url)
            dest = out_dir / filename
            print(f"[{i}/{len(links)}] {filename}", end=" ... ", flush=True)
            status, size, error = download_via_browser(page, url, dest, args.retries)
            if status == "downloaded":
                print(f"OK ({size:,} bytes)")
            elif status == "skipped_existing":
                print(f"skipped ({size:,} bytes)")
            else:
                print(f"FAILED: {error}")
            if status in {"downloaded", "skipped_existing"}:
                downloaded_files.append(dest)
            records.append({
                "index": i, "url": url, "filename": filename,
                "status": status, "size_bytes": size or "", "error": error
            })
            if status == "downloaded" and args.throttle:
                time.sleep(args.throttle)

        browser.close()

    with manifest_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["index", "url", "filename", "status", "size_bytes", "error"])
        writer.writeheader()
        writer.writerows(records)

    print(f"\nCreating ZIP: {zip_path}")
    zip_files(downloaded_files, zip_path)
    print(f"Done. ZIP contains {len(downloaded_files)} files.")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
