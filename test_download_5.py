#!/usr/bin/env python3
"""Quick test: download first 5 UFO files via Playwright browser."""
from __future__ import annotations
import base64, csv, time
from pathlib import Path
from urllib.parse import urlparse, unquote

INVALID_CHARS = r'<>:"/\\|?*'

def safe_filename_from_url(url):
    name = unquote(Path(urlparse(url).path).name).strip() or "file"
    return name.translate(str.maketrans({ch: "_" for ch in INVALID_CHARS}))

def read_links(csv_path, limit=5):
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        seen, links = set(), []
        for row in csv.DictReader(f):
            url = (row.get("PDF | Image Link") or "").strip()
            if url and url not in seen:
                seen.add(url); links.append(url)
                if len(links) >= limit:
                    break
    return links

out_dir = Path("ufo_release_01_files")
out_dir.mkdir(exist_ok=True)
links = read_links("uap-csv.csv", limit=5)
print(f"Testing {len(links)} URLs...\n")

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    page = ctx.new_page()
    print("Navigating to war.gov to establish session...")
    page.goto("https://www.war.gov/", wait_until="domcontentloaded", timeout=30000)
    time.sleep(2)
    print("Session ready.\n")

    for i, url in enumerate(links, 1):
        fname = safe_filename_from_url(url)
        dest = out_dir / fname
        print(f"[{i}/{len(links)}] {fname}")
        try:
            result = page.evaluate("""async (url) => {
                const resp = await fetch(url);
                if (!resp.ok) return { error: `HTTP ${resp.status}`, data: null };
                const buf = await resp.arrayBuffer();
                const bytes = new Uint8Array(buf);
                let binary = '';
                for (let i = 0; i < bytes.length; i += 32768)
                    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + 32768));
                return { error: null, data: btoa(binary) };
            }""", url)
            if result["error"]:
                print(f"  FAILED: {result['error']}")
            else:
                data = base64.b64decode(result["data"])
                dest.write_bytes(data)
                print(f"  OK: {len(data):,} bytes -> {dest}")
        except Exception as e:
            print(f"  ERROR: {e}")
        time.sleep(0.5)

    browser.close()
print("\nDone.")
