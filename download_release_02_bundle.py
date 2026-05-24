#!/usr/bin/env python3
"""
Download the Release 02 document bundle from war.gov via Edge (Playwright),
then extract its contents into ufo_release_02_files/.

war.gov is fronted by Akamai which 403s non-browser clients, so we drive a
real Edge session (same approach that worked for Release 01).
"""
from __future__ import annotations

import time
import zipfile
from pathlib import Path

BUNDLE_URL = "https://www.war.gov/medialink/ufo/052226/release_02/release_02_document_bundle.zip"
LANDING_URL = "https://www.war.gov/UFO/?releaseDate=Release+02"

ROOT = Path(__file__).parent.resolve()
OUT_DIR = ROOT / "ufo_release_02_files"
ZIP_PATH = ROOT / "war_gov_ufo_release_02_document_bundle.zip"


def main() -> int:
    from playwright.sync_api import sync_playwright

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, channel="msedge")
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        print("Establishing browser session with war.gov ...")
        page.goto(LANDING_URL, wait_until="domcontentloaded", timeout=60_000)
        time.sleep(2)
        print(f"Session established: {page.title()}")

        print(f"Downloading bundle: {BUNDLE_URL}")
        with page.expect_download(timeout=600_000) as dl_info:
            page.evaluate(
                "(url) => { const a = document.createElement('a');"
                " a.href = url; a.download = ''; document.body.appendChild(a);"
                " a.click(); a.remove(); }",
                BUNDLE_URL,
            )
        download = dl_info.value
        download.save_as(str(ZIP_PATH))
        failure = download.failure()
        if failure:
            print(f"Download failed: {failure}")
            browser.close()
            return 1

        size = ZIP_PATH.stat().st_size
        print(f"Saved {ZIP_PATH.name} ({size:,} bytes)")
        browser.close()

    print(f"Extracting to {OUT_DIR} ...")
    extracted = 0
    skipped = 0
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            # Flatten: take just the basename so files land directly in OUT_DIR
            target_name = Path(member.filename).name
            if not target_name:
                continue
            target = OUT_DIR / target_name
            if target.exists() and target.stat().st_size > 0:
                skipped += 1
                continue
            with zf.open(member) as src, target.open("wb") as dst:
                dst.write(src.read())
            extracted += 1

    print(f"Done. Extracted {extracted} file(s); skipped {skipped} existing.")
    print(f"Folder: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
