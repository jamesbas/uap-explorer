#!/usr/bin/env python3
"""Test download of first 5 CSV links via Edge browser."""
import base64, csv, time
from pathlib import Path
from urllib.parse import urlparse, unquote

INVALID_CHARS = r'<>:"/\\|?*'

def safe_filename(url):
    name = unquote(Path(urlparse(url).path).name).strip() or "file"
    return name.translate(str.maketrans({ch: "_" for ch in INVALID_CHARS}))

def read_links(path, limit=5):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        seen, links = set(), []
        for row in csv.DictReader(f):
            url = (row.get("PDF | Image Link") or "").strip()
            if url and url not in seen:
                seen.add(url); links.append(url)
                if len(links) >= limit: break
    return links

JS_DOWNLOAD = """async (url) => {
    const resp = await fetch(url);
    if (!resp.ok) return {error: "HTTP " + resp.status, data: null};
    const buf = await resp.arrayBuffer();
    const bytes = new Uint8Array(buf);
    let b = "";
    for (let i = 0; i < bytes.length; i += 32768)
        b += String.fromCharCode.apply(null, bytes.subarray(i, i + 32768));
    return {error: null, data: btoa(b)};
}"""

out_dir = Path("ufo_release_01_files")
out_dir.mkdir(exist_ok=True)
links = read_links("uap-csv.csv", limit=5)
print(f"Testing {len(links)} URLs...\n")

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, channel="msedge")
    page = browser.new_context().new_page()
    print("Establishing session...")
    page.goto("https://www.war.gov/", wait_until="domcontentloaded", timeout=30000)
    time.sleep(2)
    print(f"Title: {page.title()}\n")

    for i, url in enumerate(links, 1):
        fname = safe_filename(url)
        dest = out_dir / fname
        print(f"[{i}/{len(links)}] {fname}", end=" ... ", flush=True)
        if dest.exists() and dest.stat().st_size > 0:
            print(f"skipped ({dest.stat().st_size:,} bytes)")
            continue
        try:
            r = page.evaluate(JS_DOWNLOAD, url)
            if r["error"]:
                print(f"FAILED: {r['error']}")
            else:
                data = base64.b64decode(r["data"])
                dest.write_bytes(data)
                print(f"OK ({len(data):,} bytes)")
        except Exception as e:
            print(f"ERROR: {e}")
        time.sleep(0.5)

    browser.close()
print("\nDone.")
