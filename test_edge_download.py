#!/usr/bin/env python3
"""Test download via Edge browser (non-headless) to bypass Akamai."""
import base64, time
from pathlib import Path

out_dir = Path("ufo_release_01_files")
out_dir.mkdir(exist_ok=True)

JS_HEAD = """async (url) => {
    try {
        const resp = await fetch(url, {method: "HEAD"});
        return {status: resp.status, type: resp.headers.get("content-type")};
    } catch(e) { return {error: e.message}; }
}"""

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

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, channel="msedge")
    ctx = browser.new_context()
    page = ctx.new_page()

    print("Navigating to war.gov...")
    page.goto("https://www.war.gov/", wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)
    print(f"Page title: {page.title()}")

    url = "https://www.war.gov/medialink/ufo/release_1/dos-uap-d1-cable-1-papua-new-guinea-january-1985.pdf"
    print(f"\nTesting HEAD: {url}")
    head = page.evaluate(JS_HEAD, url)
    print(f"HEAD result: {head}")

    if head.get("status") == 200:
        print("Downloading full file...")
        result = page.evaluate(JS_DOWNLOAD, url)
        if result["error"]:
            print(f"FAILED: {result['error']}")
        else:
            data = base64.b64decode(result["data"])
            dest = out_dir / "dos-uap-d1-cable-1-papua-new-guinea-january-1985.pdf"
            dest.write_bytes(data)
            print(f"Saved: {dest} ({len(data):,} bytes)")
    else:
        print("HEAD failed, cannot download.")

    browser.close()

print("Done.")
