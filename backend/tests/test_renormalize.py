from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from backend.app.extraction import parse_1688_page, parse_taobao_page, parse_alibaba_page
from backend.app.extraction.renormalize import UnsupportedRawEvidence, renormalize_public_fields


URL = "https://detail.1688.com/offer/996518024136.html"
AT = datetime(2026, 9, 1, tzinfo=timezone.utc)


def retained():
    html = (Path(__file__).parent / "fixtures" / "1688_offer_996518024136.html").read_text(encoding="utf-8")
    result = parse_1688_page(html, URL, extracted_at=AT)
    return dict(raw_payload=result["raw_payload"], source_url=URL,
                extraction_method="PUBLIC_HTTP", analysis_mode="ACCOUNT_PUBLIC",
                extracted_at=result["supplier_data"]["extracted_at"],
                source_snapshot_id=uuid4(),
                source_extractor_version=result["supplier_data"]["extractor_version"])


def retained_layout(layout):
    if layout == "offer":
        return retained()
    parser, filename, url = {
        "item": (parse_taobao_page, "taobao_item_1076425861755.html", "https://item.taobao.com/item.htm?id=1076425861755"),
        "shop": (parse_taobao_page, "taobao_shop_159450000.html", "https://shop159450000.world.taobao.com/category.htm"),
        "product": (parse_alibaba_page, "alibaba_product_1600147809763.html", "https://www.alibaba.com/product-detail/100-Cotton-180gsm-T-shirts-Men_1600147809763.html"),
        "profile": (parse_alibaba_page, "alibaba_profile_dgxuandele.html", "https://dgxuandele.en.alibaba.com/company_profile.html"),
    }[layout]
    result = parser((Path(__file__).parent / "fixtures" / filename).read_text(encoding="utf-8"), url, extracted_at=AT)
    return retained() | {"raw_payload": result["raw_payload"], "source_url": url,
                         "source_extractor_version": result["supplier_data"]["extractor_version"]}


@pytest.mark.parametrize("layout", ["offer", "item", "shop", "product", "profile"])
@pytest.mark.parametrize("version", ["unknown", "1688-http.v99", "taobao-http.v1", "alibaba-http.v1", "public-browser.v1"])
def test_http_replay_uses_only_approved_source_revisions(layout, version):
    args = retained_layout(layout)
    if version == args["source_extractor_version"]:
        assert renormalize_public_fields(**args)["supplier_data"]["extractor_version"].endswith("-raw.v2")
        return
    with pytest.raises(UnsupportedRawEvidence, match="source revision"):
        renormalize_public_fields(**(args | {"source_extractor_version": version}))


@pytest.mark.parametrize("layout", ["offer", "item", "shop", "product", "profile"])
def test_retained_http_revision_must_match_and_raw_is_preserved(layout):
    args = retained_layout(layout)
    args["raw_payload"]["extractor_version"] = args["source_extractor_version"]
    before = deepcopy(args["raw_payload"])
    replay = renormalize_public_fields(**args)
    provenance = {key: replay[key] for key in ("renormalized_from_snapshot_id", "source_extractor_version", "renormalized_at", "replay_limitation")}
    assert replay["raw_payload"] == before | provenance
    assert args["raw_payload"] == before
    args["raw_payload"]["extractor_version"] = "future.v9"
    with pytest.raises(UnsupportedRawEvidence):
        renormalize_public_fields(**args)


@pytest.mark.parametrize("layout,path", [
    ("offer", ("shop_info",)), ("offer", ("rate_info", "commonTagNodeList", 0)),
    ("item", ("seller",)), ("item", ("prices", "price")), ("item", ("rate",)),
    ("item", ("reviews", 0)), ("shop", ("evaluates", 0)), ("shop", ("products", 0)),
    ("product", ("seller",)), ("product", ("jsonld_identity", 0, "offers", 0)),
    ("product", ("productBasicProperties", 0)), ("product", ("offer_price", "productRangePrices")),
    ("product", ("storeReview",)), ("product", ("tradeHalfYear",)),
    ("product", ("onlinePerformance", 0)), ("product", ("delivery", "ladderPeriodList", 0)),
    ("product", ("review_bodies", 0)), ("profile", ("supplierPerformance", "years")),
    ("profile", ("supplierActionBar",)), ("profile", ("factoryCapability", 0)),
    ("profile", ("markets", 0)), ("profile", ("categories", 0)),
    ("profile", ("certifications", 0)), ("profile", ("products", 0)),
])
def test_unknown_nested_selections_are_rejected(layout, path):
    args = retained_layout(layout)
    node = args["raw_payload"]["public_fields"]
    for key in path:
        node = node[key]
    node["unselected"] = "must not survive"
    with pytest.raises(UnsupportedRawEvidence, match="nested selected"):
        renormalize_public_fields(**args)


@pytest.mark.parametrize("layout,path", [
    ("offer", ("price", "offerMinPrice")), ("offer", ("shop_info", "byrRepeatRate3m")),
    ("offer", ("offer_base", "sellerUserId")), ("offer", ("rate_info", "goodsGrade")),
    ("offer", ("rate_info", "goodRates")), ("item", ("seller", "tmall")),
    ("item", ("prices", "price", "priceText")), ("item", ("reviews", 0, "original_length")),
    ("product", ("offer_price", "productRangePrices", "priceRangeLow")),
    ("product", ("storeReview", "reviewRatingText")), ("product", ("seller", "localCompanyJoinYears")),
    ("profile", ("supplierActionBar", "reviewCount")), ("profile", ("products", 0, "title")),
])
@pytest.mark.parametrize("value", [True, {}, [], float("nan")])
def test_incompatible_retained_scalar_shapes_are_rejected(layout, path, value):
    args = retained_layout(layout)
    node = args["raw_payload"]["public_fields"]
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    # A real boolean is the audited tmall type, but True still denotes unsupported Tmall.
    with pytest.raises(UnsupportedRawEvidence):
        renormalize_public_fields(**args)


@pytest.mark.parametrize("field", ["goodsGrade", "goodRates"])
def test_1688_numeric_rating_cannot_be_a_string(field):
    args = retained()
    args["raw_payload"]["public_fields"]["rate_info"][field] = "4.9"
    with pytest.raises(UnsupportedRawEvidence):
        renormalize_public_fields(**args)


@pytest.mark.parametrize("missing", ["ssrItemId", "itemId"])
def test_taobao_item_with_one_matching_retained_identifier_is_valid(missing):
    args = retained_layout("item")
    fields = args["raw_payload"]["public_fields"]
    (fields if missing == "ssrItemId" else fields["item"])[missing] = None
    assert renormalize_public_fields(**args)["supplier_data"]["offer_id"] == "1076425861755"


@pytest.mark.parametrize("layout", ["item", "shop"])
@pytest.mark.parametrize("field,value", [("pcShopUrl", "https://shop1.taobao.com/"), ("sellerType", "B"), ("tmall", True)])
def test_taobao_replay_rejects_seller_conflicts(layout, field, value):
    args = retained_layout(layout)
    args["raw_payload"]["public_fields"]["seller"][field] = value
    with pytest.raises(UnsupportedRawEvidence):
        renormalize_public_fields(**args)


@pytest.mark.parametrize("href", ["https://other.en.alibaba.com/productgrouplist-1.html", "http://dgxuandele.en.alibaba.com/productgrouplist-1.html", "/unrelated.html"])
def test_alibaba_categories_must_bind_to_the_profile(href):
    args = retained_layout("profile")
    args["raw_payload"]["public_fields"]["categories"][0]["href"] = href
    with pytest.raises(UnsupportedRawEvidence):
        renormalize_public_fields(**args)


@pytest.mark.parametrize("layout", ["shop", "profile"])
def test_duplicate_offer_ids_use_the_first_title_without_consuming_a_slot(layout):
    args = retained_layout(layout)
    products = args["raw_payload"]["public_fields"]["products"]
    duplicate = deepcopy(products[0]) | {"title": "Different title"}
    products.insert(1, duplicate)
    replay = renormalize_public_fields(**args)["supplier_data"]["products"]
    assert len({item["offer_id"] for item in replay}) == len(replay)
    assert replay[0]["title"] != "Different title"
    assert len(replay) == len(products) - 1


@pytest.mark.parametrize("change", [
    {"analysis_mode": "GUEST_PUBLIC"}, {"extraction_method": "EXTENSION_DOM"},
    {"source_url": URL.replace("996518024136", "1")},
    {"extracted_at": "2026-09-02T00:00:00+00:00"},
    {"source_extractor_version": "1688-raw.v2"}, {"source_snapshot_id": "unknown"},
])
def test_incompatible_revision_and_source_provenance_are_rejected(change):
    with pytest.raises(UnsupportedRawEvidence):
        renormalize_public_fields(**(retained() | change))


@pytest.mark.parametrize("kind", ["missing", "extra", "hash", "review_source"])
def test_raw_replay_rejects_incompatible_retained_fields(kind):
    args = retained()
    raw = args["raw_payload"]
    if kind == "missing":
        raw["public_fields"].pop("offer_base")
    elif kind == "extra":
        raw["public_fields"]["page_globals"] = {"private": "sentinel"}
    elif kind == "hash":
        raw["html_sha256"] = "invalid"
    else:
        raw["public_fields"]["reviews"] = [{"text": "Review", "source_url": "https://example.com"}]
    with pytest.raises(UnsupportedRawEvidence):
        renormalize_public_fields(**args)


def test_public_browser_replay_preserves_capture_and_render_provenance():
    args = retained()
    args["extraction_method"] = "PUBLIC_BROWSER"
    args["source_extractor_version"] = "public-browser.v1"
    args["raw_payload"].update(extraction_method="PUBLIC_BROWSER",
                               extractor_version="public-browser.v1",
                               rendered_at=args["extracted_at"], rendered_html_sha256="b" * 64)
    before = deepcopy(args)
    result = renormalize_public_fields(**args, renormalized_at=datetime(2026, 10, 3, tzinfo=timezone.utc))
    assert args == before
    assert result["supplier_data"]["extracted_at"] == AT.isoformat()
    assert result["supplier_data"]["extraction_method"] == "PUBLIC_BROWSER"
    assert result["raw_payload"]["rendered_html_sha256"] == "b" * 64
    assert result["raw_payload"]["source_extractor_version"] == "public-browser.v1"
    assert result["renormalized_at"] == "2026-10-03T00:00:00+00:00"


def test_browser_replay_requires_retained_render_metadata():
    args = retained()
    args.update(extraction_method="PUBLIC_BROWSER", source_extractor_version="public-browser.v1")
    with pytest.raises(UnsupportedRawEvidence, match="render provenance"):
        renormalize_public_fields(**args)
