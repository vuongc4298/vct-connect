r"""Outcome parity captured at 90bead71 before the shared-helper refactor.

Canonical test input policy: convert fixture CRLF bytes to LF before supplying
any HTTP response body or upload bytes. Parsing and raw hashes therefore use the
same LF input on Windows and Linux, regardless of Git checkout line endings.
This policy applies only to this parity generator, not production extraction.

Isolated baseline capture (PowerShell, from the repository root, with the existing
.venv dependencies). Choose a fresh temporary directory; do not regenerate the
recorded fixture using refactored production code. Archive the exact revision,
then copy only this generator and its recorded fixture into that archive. Keep
the archived production modules and archived HTML fixtures:

    $capturePython = (Resolve-Path '.venv/Scripts/python.exe').Path
    $captureRoot = Join-Path (Get-Location).Path 'tmp/refactor-baseline-90bead71'
    git -c core.autocrlf=false archive --format=zip --output=tmp/refactor-baseline-90bead71.zip 90bead71cd8073f352fb6b6801099e3c784d120c
    Expand-Archive -LiteralPath tmp/refactor-baseline-90bead71.zip -DestinationPath $captureRoot
    Copy-Item backend/tests/test_refactor_parity.py (Join-Path $captureRoot 'backend/tests/test_refactor_parity.py')
    Copy-Item backend/tests/fixtures/refactor_baseline.json (Join-Path $captureRoot 'backend/tests/fixtures/refactor_baseline.json')
    Push-Location $captureRoot
    try {
        & $capturePython -I -c 'import json, sys; from pathlib import Path; sys.path.insert(0, str(Path.cwd())); from backend.tests.test_refactor_parity import outcomes; data = {"baseline_revision": "90bead71cd8073f352fb6b6801099e3c784d120c", "outcomes": outcomes()}; Path("captured.json").write_text(json.dumps(data, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"); assert data == json.loads(Path("backend/tests/fixtures/refactor_baseline.json").read_text(encoding="utf-8"))'
    } finally {
        Pop-Location
    }

captured.json is the independently generated candidate, never an automatic
replacement for the recorded fixture. The assertion verifies exact equality.
The -I invocation adds only the archive root to sys.path, excluding this checkout.
"""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import httpx
import pytest

from backend.app.extraction import (
    extract_1688, extract_taobao, extract_alibaba,
    parse_1688_page, parse_taobao_page, parse_alibaba_page,
)
from backend.app.extraction.extension1688 import DomCapture, normalize_capture
from backend.app.extraction.extensiontaobao import TaobaoCapture, normalize_taobao_capture
from backend.app.extraction.extension_merge import merge_extension_evidence, reject_sensitive_page_state
from backend.app.extraction.renormalize import renormalize_public_fields
from backend.app.extraction.contracts import EVIDENCE_FIELDS
from backend.app.extraction.browser import field_count
from backend.tests.test_browser_fallback import fixture, gain

FIXTURES = Path(__file__).parent / "fixtures"
AT = datetime(2026, 10, 3, tzinfo=timezone.utc)
SNAPSHOT = UUID("00000000-0000-0000-0000-000000000028")
LAYOUTS = {
    "1688_offer": (extract_1688, parse_1688_page, "1688_offer_996518024136.html", "https://detail.1688.com/offer/996518024136.html"),
    "taobao_item": (extract_taobao, parse_taobao_page, "taobao_item_1076425861755.html", "https://item.taobao.com/item.htm?id=1076425861755"),
    "taobao_shop": (extract_taobao, parse_taobao_page, "taobao_shop_159450000.html", "https://shop159450000.world.taobao.com/category.htm"),
    "alibaba_product": (extract_alibaba, parse_alibaba_page, "alibaba_product_1600147809763.html", "https://www.alibaba.com/product-detail/100-Cotton-180gsm-T-shirts-Men_1600147809763.html"),
    "alibaba_profile": (extract_alibaba, parse_alibaba_page, "alibaba_profile_dgxuandele.html", "https://dgxuandele.en.alibaba.com/company_profile.html"),
}


class FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return AT.astimezone(tz)


def replay(result):
    data = result["supplier_data"]
    return renormalize_public_fields(
        raw_payload=result["raw_payload"], source_url=result["source_url"],
        extraction_method=data["extraction_method"], analysis_mode=data["analysis_mode"],
        extracted_at=data["extracted_at"], source_snapshot_id=SNAPSHOT,
        source_extractor_version=data["extractor_version"], renormalized_at=AT,
    )


def fixture_bytes(path):
    """Canonical LF input for HTTP, uploads and their retained raw hashes."""
    return path.read_bytes().replace(b"\r\n", b"\n")


def outcomes():
    """Keep full normalized and raw JSON, including hashes and source labels."""
    results = {}
    for name, (extractor, parser, filename, url) in LAYOUTS.items():
        content = fixture_bytes(FIXTURES / filename)
        with patch(parser.__module__ + ".datetime", FixedDatetime):
            with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(
                    200, headers={"content-type": "text/html; charset=utf-8"}, content=content))) as client:
                result = extractor(url, client=client, dns_check=lambda _: True)
            results[name + "/http"] = result
            results[name + "/replay"] = replay(result)
            if name.startswith(("1688", "taobao")):
                results[name + "/upload"] = parser(content.decode("utf-8"), url,
                                                    extraction_method="USER_UPLOAD", uploaded_bytes=content)

    for platform, (extractor, parser, _, _) in {
            "1688": LAYOUTS["1688_offer"], "TAOBAO": LAYOUTS["taobao_item"],
            "ALIBABA": LAYOUTS["alibaba_product"]}.items():
        url, html = fixture(platform)
        with patch(parser.__module__ + ".datetime", FixedDatetime):
            sparse = parser(html, url)
            results[platform + "/sparse"] = sparse
            with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(
                    200, headers={"content-type": "text/html"}, text=html))) as client:
                rendered = extractor(url, client=client, dns_check=lambda _: True,
                                     browser_fallback=True, browser_renderer=lambda *_: gain(sparse))
            results[platform + "/browser_gain"] = rendered
            # Retain valid adapter-selected raw fields in the simulated DOM gain.
            browser_raw = deepcopy(results[{"1688": "1688_offer", "TAOBAO": "taobao_item", "ALIBABA": "alibaba_product"}[platform] + "/http"])
            browser_raw["supplier_data"].update(extraction_method="PUBLIC_BROWSER", extractor_version="public-browser.v1")
            browser_raw["raw_payload"].update(extraction_method="PUBLIC_BROWSER", extractor_version="public-browser.v1",
                                            rendered_at=AT.isoformat(), rendered_html_sha256=sha256(b"rendered").hexdigest())
            results[platform + "/browser_replay"] = replay(browser_raw)
        for label, body in {"blocked": "<title>Captcha</title>", "login": "<title>Login</title>",
                            "malformed": "<html><body>No audited evidence</body></html>"}.items():
            with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(
                    200, headers={"content-type": "text/html"}, text=body))) as client:
                results[platform + "/" + label] = extractor(url, client=client, dns_check=lambda _: True)

        def timeout(_):
            raise httpx.ReadTimeout("source details must not escape")
        with httpx.Client(transport=httpx.MockTransport(timeout)) as client:
            results[platform + "/timeout"] = extractor(url, client=client, dns_check=lambda _: True, sleep=lambda _: None)
        with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(
                302, headers={"location": "https://127.0.0.1/private"}))) as client:
            results[platform + "/unsafe_redirect"] = extractor(url, client=client, dns_check=lambda _: True)

    with patch("backend.app.extraction.extension1688.datetime", FixedDatetime):
        current = normalize_capture(DomCapture(source_url=LAYOUTS["1688_offer"][3], offer_id="996518024136",
                                              fields={"supplier_name": "Selected supplier", "product_title": "Selected dress", "review_count": 0}))
    results["1688/extension"] = current
    prior = results["1688_offer/http"]
    results["1688/merge"] = merge_extension_evidence(current, prior | {"supplier_snapshot_id": SNAPSHOT})
    with patch("backend.app.extraction.extensiontaobao.datetime", FixedDatetime):
        current = normalize_taobao_capture(TaobaoCapture(
            source_url=LAYOUTS["taobao_item"][3], source_kind="item", source_id="1076425861755",
            fields={"product_title": "Selected shirt", "reviews": [{"text": "Good shirt", "original_length": 10}] * 2,
                    "shop_metrics": ["平均24小时发货"]}))
    results["TAOBAO/extension"] = current
    prior = results["taobao_item/http"]
    prior_before, current_before = deepcopy(prior), deepcopy(current)
    results["TAOBAO/merge"] = merge_extension_evidence(current, prior | {"supplier_snapshot_id": SNAPSHOT})
    assert prior == prior_before and current == current_before
    return results


@pytest.fixture(scope="module")
def parity_outcomes():
    generated = outcomes()
    recorded = json.loads((FIXTURES / "refactor_baseline.json").read_text(encoding="utf-8"))["outcomes"]
    assert set(generated) == set(recorded), "Generated and recorded baseline cases differ"
    return generated


def test_baseline_case_set(parity_outcomes):
    # Runs even if the recorded fixture has no cases to parametrize.
    assert parity_outcomes


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"], ids=["LF", "CRLF"])
def test_fixture_newlines_do_not_change_parity(newline, tmp_path, monkeypatch, parity_outcomes):
    for _, _, filename, _ in LAYOUTS.values():
        content = fixture_bytes(FIXTURES / filename)
        (tmp_path / filename).write_bytes(content.replace(b"\n", newline))
    monkeypatch.setattr(__name__ + ".FIXTURES", tmp_path)
    assert outcomes() == parity_outcomes


@pytest.mark.parametrize("case", json.loads((FIXTURES / "refactor_baseline.json").read_text(encoding="utf-8"))["outcomes"])
def test_baseline_outcome_json(case, parity_outcomes):
    baseline = json.loads((FIXTURES / "refactor_baseline.json").read_text(encoding="utf-8"))
    assert parity_outcomes[case] == baseline["outcomes"][case]


@pytest.mark.parametrize("text", ["bad\x00text", "bad\ud800text"])
@pytest.mark.parametrize("field", ["supplier_name", "product_title", "reviews", "shop_metrics", "products"])
def test_taobao_selected_text_validation_survives_shared_exception_move(text, field):
    value = ([{"text": text, "original_length": len(text)}] if field == "reviews" else
             [text] if field == "shop_metrics" else
             [{"source_url": LAYOUTS["taobao_item"][3], "title": text}] if field == "products" else text)
    with pytest.raises(ValueError, match="Invalid selected evidence text|valid string"):
        capture = TaobaoCapture(source_url=LAYOUTS["taobao_item"][3], source_kind="item", source_id="1076425861755", fields={field: value})
        normalize_taobao_capture(capture)


@pytest.mark.parametrize("text", ["password=secret", "Cookie: sid=secret", "Bearer abcdefghijklmnop"])
def test_selected_text_secret_rejection(text):
    with pytest.raises(ValueError, match="sensitive page state"):
        reject_sensitive_page_state({"fields": {"supplier_name": text}})


def test_zero_evidence_and_browser_empty_object_guard():
    from backend.app.extraction.contracts import assemble_supplier_data, evidence_status

    evidence = dict.fromkeys(EVIDENCE_FIELDS)
    evidence.update(years_active=0, rating=0.0, company_information={}, reviews=[], supplier_name="")
    data = assemble_supplier_data(evidence, platform="1688", offer_id="996518024136")
    assert data["completeness"] == 0.25
    assert data["missing_fields"] == ["supplier_name", "categories", "certifications", "products",
                                      "price_information", "transaction_signals", "reviews",
                                      "delivery_information", "activity_history"]
    assert evidence_status(data) == "PARTIAL"
    assert field_count(data) == 2  # Browser gain still requires a nonempty object.
    data["completeness_denominator"].clear()
    assert len(EVIDENCE_FIELDS) == 12  # Outcome lists cannot mutate the frozen contract.


def test_complete_evidence_uses_success_without_provenance_inflating_coverage():
    from backend.app.extraction.contracts import assemble_supplier_data, evidence_status

    data = assemble_supplier_data(dict.fromkeys(EVIDENCE_FIELDS, "observed"), platform="1688")
    assert data["completeness"] == 1.0 and data["missing_fields"] == []
    assert data["completeness_denominator"] == list(EVIDENCE_FIELDS)
    assert evidence_status(data) == "SUCCESS"


def test_legacy_utility_imports_reference_the_shared_implementations():
    from backend.app.extraction import offer1688, taobao, alibaba, evidence, dom
    assert offer1688.MalformedPage is taobao.MalformedPage is alibaba.MalformedPage is evidence.MalformedPage
    assert offer1688._validate_json_evidence is evidence.validate_json_evidence
    assert offer1688._field is evidence.field
    assert offer1688._object is evidence.object
    assert offer1688._string is evidence.string
    assert offer1688._text is evidence.text
    assert taobao._tree is dom.tree
    assert taobao._active is dom.active
    assert taobao._scripts is dom.scripts
    assert taobao._prune_dom is dom.prune_dom
    assert alibaba._stylesheet_hidden is dom.stylesheet_hidden
