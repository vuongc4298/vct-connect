import copy
import json
from pathlib import Path
import pytest
from backend.tests.test_supplier_bundle import selected, normalize, SHOP, FACTORY


def html_sources(value):
    product = value["product"]["source_url"]
    def page(kind, url, body):
        return {"page": kind, "source_url": url, "html": f'<!doctype html><html><head><link rel="canonical" href="{url}"></head><body>{body}</body></html>'}
    return [
        page("PRODUCT", product, f'<div id="shopNavigation"><a class="shop-company-name" href="{SHOP}">Supplier</a></div>'
             '<div id="description">Detailed fabric composition and washing instructions</div><div id="productPackInfo">10 shirts per carton</div>'
             '<section id="vct-review-bodies">' + '<div class="review-item">Good fabric</div>' * 10 + '</section>'),
        page("SHOP", SHOP, f'<div id="bd_2_container_0"><div class="module-wrapper">Company introduction: wholesaler. After-sales experience 3.0<a href="{SHOP}page/creditdetail.html">See more</a></div>'
             '<div>UNRELATED_RECOMMENDED_SUPPLIER ISO9001</div></div>'),
        page("FACTORY", FACTORY, f'<div id="pc_card_baseinfo"><a href="{SHOP}">Shop</a></div><div id="pc_card_exhibition"><div>工厂展厅</div><div>Wholesale business introduction</div></div>'),
    ]


def test_html_enriches_same_snapshot_without_replacing_reviews_or_manufacturing_certifications():
    value = selected(); value["html_sources"] = html_sources(value)
    result = normalize(value); data = result["supplier_data"]
    assert data["extractor_version"] == "1688-linked-browser-bundle.v2"
    assert data["products"][0]["packaging_display_text"] == "10 shirts per carton"
    assert "washing instructions" in data["products"][0]["description_display_text"]
    assert "After-sales experience" in data["company_information"]["shop_introduction_display_text"]
    assert "UNRELATED_RECOMMENDED_SUPPLIER" not in json.dumps(data)
    assert len(result["reviews"]) == 10 and data["certifications"] is None
    assert len(result["raw_payload"]["html_sources"]) == 3
    assert all(x["status"] == "PARSED" and len(x["html_sha256"]) == 64 for x in data["html_capture_status"])
    assert "html_sources" not in result["raw_payload"]["linked_collection"]


def test_named_shop_html_sources_parse_together_with_matching_factory_backlink():
    value = selected()
    value["html_sources"] = html_sources(value)
    value = json.loads(json.dumps(value).replace(SHOP, "https://hztxsy.1688.com/"))
    result = normalize(value)
    assert all(source["status"] == "PARSED" for source in result["supplier_data"]["html_capture_status"])
    assert len(result["raw_payload"]["html_sources"]) == 3
    value["html_sources"][2]["html"] = value["html_sources"][2]["html"].replace("https://hztxsy.1688.com/", SHOP)
    with pytest.raises(ValueError):
        normalize(value)


@pytest.mark.parametrize("change", ["canonical", "source", "duplicate", "script", "button", "event", "secret", "link", "size", "encoded_secret", "uncollected"])
def test_unsafe_html_is_rejected(change):
    value = selected(); value["html_sources"] = html_sources(value)
    source = value["html_sources"][0]
    if change == "canonical": source["html"] = source["html"].replace(value["product"]["source_url"], "https://detail.1688.com/offer/999999999.html")
    if change == "source": source["source_url"] = "https://detail.1688.com/offer/999999999.html"
    if change == "duplicate": value["html_sources"][1] = copy.deepcopy(source)
    if change == "script": source["html"] += '<script>window.privateState</script>'
    if change == "button": source["html"] = source["html"].replace('Detailed fabric', '<button>PRIVATE_ACCOUNT_CONTROL</button>Detailed fabric')
    if change == "event": source["html"] += '<div onclick="privateState">test</div>'
    if change == "secret": source["html"] += '<div>access_token=private</div>'
    if change == "encoded_secret": source["html"] += '<div>access&#95;token=private</div>'
    if change == "link": source["html"] += '<a href="javascript:alert(1)">unsafe</a>'
    if change == "size": source["html"] += '厚' * 700_000
    if change == "uncollected": value["shop"] = None; value["factory"] = None; value["outcomes"] = [{"page":"SHOP","status":"UNAVAILABLE"},{"page":"FACTORY","status":"LINK_UNAVAILABLE"}]
    with pytest.raises(ValueError): normalize(value)


def test_html_cannot_bypass_selected_evidence_limit():
    value = selected(); value["html_sources"] = html_sources(value)
    value["product"]["fields"]["reviews"] = [{"text": "厚" * 2000, "original_length": 2000}] * 20
    with pytest.raises(ValueError, match="32 KB"): normalize(value)


def test_optional_html_failure_keeps_selected_evidence_and_marks_missing_snapshots():
    value = selected(); value["html_capture_requested"] = True
    result = normalize(value)
    assert len(result["reviews"]) == 10
    assert {x["page"] for x in result["supplier_data"]["html_capture_status"]} == {"PRODUCT", "SHOP", "FACTORY"}
    assert all(x["status"] == "NOT_CAPTURED" for x in result["supplier_data"]["html_capture_status"])


def test_real_browser_generated_sanitized_snapshots_parse_together():
    value = selected()
    shop = "https://shop3e1674729h322.1688.com/"
    factory = "https://www.1688.com/factory/b2b-222030383828763a1d.html"
    value["shop_url"] = shop
    value["shop"].update(source_url=shop, credit_url=shop + "page/creditdetail.html", factory_url=factory)
    value["factory"].update(source_url=factory, canonical_url=factory, shop_url=shop)
    value["html_sources"] = [{"page": page, "source_url": url,
        "html": (Path(__file__).parent / "fixtures" / f"1688_browser_html_{page.lower()}.html").read_text(encoding="utf-8")}
        for page, url in (("PRODUCT", value["product"]["source_url"]), ("SHOP", shop), ("FACTORY", factory))]
    result = normalize(value)
    assert all(x["status"] == "PARSED" for x in result["supplier_data"]["html_capture_status"])
    assert "Extra washing instructions" in result["supplier_data"]["products"][0]["description_display_text"]
    assert "After-sales experience" in result["supplier_data"]["company_information"]["shop_introduction_display_text"]
    assert "PRIVATE_" not in json.dumps(result)


def header_only_shop_fixture():
    value = selected()
    value["shop"] = {"source_url": SHOP, "company_name": "Shenzhen supplier"}
    value.pop("factory")
    value["outcomes"] = [{"page": "SHOP", "status": "OK"}, {"page": "FACTORY", "status": "UNAVAILABLE"}]
    value["html_sources"] = [{"page": "SHOP", "source_url": SHOP, "html":
        f'<html><head><link rel="canonical" href="{SHOP}"></head><body>'
        '<div id="pcMainCompanyNameV2">Shenzhen supplier</div>'
        '<div id="pcV2SellerTagYear">2 years of presence</div>'
        '<div id="pcV2MainCateLabel">Digital, computer</div></body></html>'}]
    result = normalize(value)
    company = result["supplier_data"]["company_information"]
    assert company["shop_company_name_display_text"] == "Shenzhen supplier"
    assert company["shop_evidence_scope"] == "SHOP_HEADER_ONLY"
    assert company["shop_header_claims_display_text"]["platform_tenure"] == "2 years of presence"
    assert "shop_introduction_display_text" not in company
    assert result["supplier_data"]["years_active"] is None
    assert result["supplier_data"]["html_capture_status"][0]["content_scope"] == "SHOP_HEADER_ONLY"
    return value


def test_header_only_shop_is_parsed_without_inventing_introduction_or_registered_age():
    header_only_shop_fixture()


@pytest.mark.parametrize("change", ["missing_html", "name_mismatch", "no_name", "wrong_credit"])
def test_header_only_shop_still_requires_matching_supplier_evidence(change):
    value = header_only_shop_fixture()
    if change == "missing_html": value.pop("html_sources")
    if change == "name_mismatch": value["shop"]["company_name"] = "Different company"
    if change == "no_name": value["html_sources"][0]["html"] = value["html_sources"][0]["html"].replace('id="pcMainCompanyNameV2"', 'id="unrelated"')
    if change == "wrong_credit": value["shop"]["credit_url"] = "https://shopwrong123.1688.com/page/creditdetail.html"
    with pytest.raises(ValueError): normalize(value)
