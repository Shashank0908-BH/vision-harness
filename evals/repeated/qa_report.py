"""Browser QA; run with system Python and installed Playwright Chromium."""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[2]
report = root / "reports/kromp-repeated-20260922"
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto((report / "index.html").as_uri())
    page.eval_on_selector_all("img", 'els=>els.forEach(e=>e.loading="eager")')
    page.wait_for_function(
        "Array.from(document.images).every(i=>i.complete && i.naturalWidth>0)", timeout=60000
    )
    checks = []
    for width in [1440, 768, 390, 320]:
        page.set_viewport_size({"width": width, "height": 1000})
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"), width
        for n in range(1, 38):
            page.select_option("#page", str(n))
            assert page.locator(f"#task-{n}").is_visible()
            assert page.locator(".task:visible").count() == 1
        page.locator("#prev").click()
        assert page.locator("#task-36").is_visible()
        page.locator("#next").click()
        assert page.locator("#task-37").is_visible()
        checks.append(
            {"width": width, "all_37_pages_work": True, "horizontal_document_overflow": False}
        )
    page.select_option("#page", "1")
    page.set_viewport_size({"width": 1440, "height": 1100})
    page.evaluate("window.scrollTo(0,0)")
    page.screenshot(path="/tmp/vision-repeated-desktop.png")
    page.set_viewport_size({"width": 390, "height": 1000})
    page.screenshot(path="/tmp/vision-repeated-mobile.png")
    links = page.locator("a").evaluate_all('es=>es.map(e=>e.getAttribute("href"))')
    bad = [
        h
        for h in links
        if not h.startswith(("http:", "https:", "#")) and not (report / h).resolve().exists()
    ]
    assert not bad, bad
    assert not errors, errors
    result = {
        "viewports": checks,
        "images_loaded": page.locator("img").count(),
        "local_links_checked": sum(not h.startswith(("http:", "https:", "#")) for h in links),
        "javascript_errors": errors,
        "broken_links": bad,
    }
    (report / "visual-qa.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    browser.close()
