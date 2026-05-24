"""Fetch the master uap-data.csv from war.gov using a real Edge session
(needed because Akamai blocks non-browser clients)."""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

CSV_URL = "https://www.war.gov/Portals/1/Interactive/2026/UFO/uap-data.csv"
OUT = Path(__file__).resolve().parents[1] / "uap-data-master.csv"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, channel="msedge")
    ctx = browser.new_context(accept_downloads=True)
    page = ctx.new_page()
    page.goto("https://www.war.gov/UFO/?releaseDate=Release+02", wait_until="domcontentloaded", timeout=60_000)
    time.sleep(2)

    # Fetch the CSV from inside the page context so cookies/session are reused.
    text = page.evaluate(
        "async (url) => { const r = await fetch(url, {credentials:'include'});"
        " if (!r.ok) throw new Error('HTTP ' + r.status); return await r.text(); }",
        CSV_URL,
    )
    OUT.write_text(text, encoding="utf-8", newline="")
    print(f"Wrote {OUT} ({len(text):,} chars)")
    browser.close()
