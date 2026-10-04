"""Check local report links, images and small-screen layout."""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

REPORT = Path(__file__).resolve().parents[2] / "reports/stardist-audit-20260922"

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto((REPORT / "index.html").as_uri())
    page.wait_for_function("Array.from(document.images).every(i=>i.complete && i.naturalWidth>0)")
    widths = [1440, 768, 390, 320]
    for width in widths:
        page.set_viewport_size({"width": width, "height": 1000})
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"), width
        page.locator("details").evaluate_all("els=>els.forEach(e=>e.open=true)")
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"), width
        page.locator("details").evaluate_all("els=>els.forEach(e=>e.open=false)")
    links = page.locator("a").evaluate_all("els=>els.map(e=>e.getAttribute('href'))")
    local = [h for h in links if not h.startswith(("http:", "https:", "#"))]
    assert all((REPORT / link).resolve().exists() for link in local)
    assert not errors
    for width, name in [(1440, "desktop"), (390, "mobile")]:
        page.set_viewport_size({"width": width, "height": 1000})
        page.screenshot(path=f"/tmp/vision-stardist-audit-{name}.png")
    result = {"widths_checked": widths, "document_overflow": False,
              "images_loaded": page.locator("img").count(), "local_links_checked": len(local),
              "javascript_errors": errors, "expandable_tables_work": True}
    (REPORT / "visual-qa.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    browser.close()
