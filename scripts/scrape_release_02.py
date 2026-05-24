"""Scrape Release 02 record details from war.gov via Playwright."""
import json
import time
from playwright.sync_api import sync_playwright

URL = "https://www.war.gov/UFO/?releaseDate=Release+02"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, channel="msedge")
    ctx = browser.new_context()
    page = ctx.new_page()
    # Visit landing first to establish session, then navigate to filtered view.
    page.goto("https://www.war.gov/UFO/", wait_until="domcontentloaded", timeout=60_000)
    page.wait_for_timeout(2500)
    page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
    # Wait for record cards to render
    page.wait_for_timeout(6000)

    # Filter to Release 02 if needed (the URL parameter usually does it).
    # Dump rendered HTML of the results area.
    html = page.content()
    out = "scraped_release_02.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {out} ({len(html):,} chars)")

    # Also try to find any embedded JSON dataset
    data = page.evaluate(
        "() => { const out={};"
        "for (const k of Object.keys(window)) {"
        "  try { const v = window[k];"
        "    if (Array.isArray(v) && v.length && typeof v[0]==='object'"
        "        && (('Title' in v[0]) || ('title' in v[0]) || ('PDF' in JSON.stringify(v[0]).slice(0,200)))) {"
        "       out[k] = v.slice(0,3);"
        "    } } catch(e){} }"
        " return out; }"
    )
    print("Window arrays sample:", json.dumps(data, indent=2)[:3000])

    browser.close()
