"""Actual extension injections against an inert, public source-layout regression fixture."""
import json
import os
from pathlib import Path

import pytest


@pytest.mark.skipif(os.getenv("VCT_TEST_BROWSER") != "true", reason="Actual Chromium runs in the network-denied image")
def test_serialized_extension_captures_capability_source_layout_and_rejects_changed_html():
    from playwright.sync_api import sync_playwright

    functions = json.loads(Path(os.environ["VCT_ALIBABA_CAPTURE_FUNCTIONS"]).read_text(encoding="utf-8"))
    fixture = Path(__file__).parent / "fixtures" / "alibaba_capability_gzlianxian.html"
    source = "https://gzlianxian.en.alibaba.com/company_profile.html"
    expected = json.loads(fixture.with_suffix(".json").read_text(encoding="utf-8"))
    with sync_playwright() as playwright:
        options = {"headless": True, "chromium_sandbox": True}
        if executable := os.getenv("VCT_TEST_CHROME_EXECUTABLE"):
            options["executable_path"] = executable
        browser = playwright.chromium.launch(**options)
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1100})
            page.route("**/*", lambda route: route.fulfill(body=fixture.read_text(encoding="utf-8"), content_type="text/html; charset=utf-8")
                       if route.request.resource_type == "document" else route.abort())
            page.goto(source)
            selected = page.evaluate("fn => (0,eval)('(' + fn + ')')('FACTORY')", functions["dom"])
            assert selected == expected["selected"]
            snapshot = page.evaluate("arg => (0,eval)('(' + arg.fn + ')')('FACTORY', arg.source, arg.selected)",
                                     {"fn": functions["html"], "source": source, "selected": selected})
            assert snapshot == expected["snapshot"]
            # No source scripts/globals are involved; mutations model hydration between injections.
            page.get_by_text("Number of production line", exact=True).evaluate("node => node.nextElementSibling.textContent = '3'")
            assert page.evaluate("arg => (0,eval)('(' + arg.fn + ')')('FACTORY', arg.source, arg.selected)",
                                 {"fn": functions["html"], "source": source, "selected": selected}) is None
        finally:
            browser.close()
