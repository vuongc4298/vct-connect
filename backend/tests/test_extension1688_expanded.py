"""Strict, source-bound expanded 1688 browser evidence normalization."""
import pytest
import json
from pathlib import Path
from pydantic import ValidationError

from backend.app.extraction.extension1688 import DomCapture, normalize_capture

SOURCE = "https://detail.1688.com/offer/1027322610455.html"


def capture(**fields):
    return DomCapture.model_validate(dict(source_url=SOURCE, offer_id="1027322610455",
                                         fields=dict(product_title="400g Cotton T-shirt", **fields)))


def pair(name, value):
    return dict(name=name, value=value)


def test_browser_captured_saved_offer_retains_the_full_attribute_table():
    raw = json.loads((Path(__file__).parent / "fixtures" / "1688_extension_offer_1027322610455.json").read_text(encoding="utf-8"))
    data = normalize_capture(DomCapture.model_validate(raw))["supplier_data"]
    attributes = data["products"][0]["attributes"]
    assert len(attributes) == 41
    assert [x["value"] for x in attributes if x["name"] == "Style"] == ["Street hip hop", "pullover"]
    assert next(x["value"] for x in attributes if x["name"] == "Gram weight") == "300g (inclusive)-350g (exclusive)"
    assert "400g" in data["products"][0]["title"]  # Preserve the conflicting source claims.
    assert "After coupon \u00a50.10" in data["price_information"]["display_text"]
    assert "\u00a58.70 Minimum order" in data["price_information"]["display_text"]
    assert data["products"][0]["sku_options"][0]["value"] == "\u00a58.7 \u00b7 Inventory790pc"
    assert data["rating"] == 4.6
    assert len(data["transaction_signals"]["source_metrics"]) == 13
    assert "40+" in data["transaction_signals"]["review_count_display_text"]
    assert "review_count" not in data["transaction_signals"]
    assert data["missing_fields"] == ["years_active", "certifications", "activity_history"]


def test_expanded_evidence_retains_labels_scopes_and_unknowns():
    result = normalize_capture(capture(
        supplier_name="  Guangzhou Cotton Company  ", supplier_tenure="诚信通 3年",
        company_location="广东 广州", main_business="主营: 男装",
        supplier_metrics=[pair("复购率", "48%"), pair("响应率", "100%")],
        product_attributes=[pair("面料", "纯棉"), pair("克重", "400g")],
        sku_options=[pair("颜色", "黑色"), pair("尺码", "XL")],
        price_text="券后 \u00a520", price_details="批发 \u00a535 起; 2件起批; 优惠券另计",
        shipping_details=[pair("发货地", "广州"), pair("承诺", "48小时发货")],
        consign_metrics=[pair("代发率", "98%")],
        review_summary="评价 40+", rating=4.8,
        reviews=[dict(text="  很厚实，纯棉  ", original_length=80)],
    ))
    data = result["supplier_data"]
    assert data["extractor_version"] == "1688-extension-dom.v2"
    assert data["company_information"] == dict(location="广东 广州",
        platform_tenure_display_text="诚信通 3年", main_business="主营: 男装")
    assert data["categories"] == ["主营: 男装"]
    assert data["years_active"] is None
    assert data["certifications"] is None
    assert data["activity_history"] is None
    assert data["products"][0]["attributes"] == [pair("面料", "纯棉"), pair("克重", "400g")]
    assert data["products"][0]["sku_options"] == [pair("颜色", "黑色"), pair("尺码", "XL")]
    assert data["price_information"]["display_text"].startswith("批发 \u00a535")
    transaction = data["transaction_signals"]
    assert transaction["review_count_display_text"] == "评价 40+"
    assert "review_count" not in transaction
    assert [metric["scope"] for metric in transaction["source_metrics"]] == [
        "SUPPLIER_PLATFORM", "SUPPLIER_PLATFORM", "CONSIGN_DROPSHIPPING"]
    assert data["rating"] == 4.8
    assert data["delivery_information"]["source_metrics"][0] == dict(
        label="发货地", value="广州", scope="PRODUCT_SHIPPING")
    assert result["reviews"] == [dict(text="很厚实，纯棉", source_url=SOURCE)]
    assert data["reviews"] == result["reviews"]
    raw = result["raw_payload"]["selected_fields"]
    assert raw["reviews"][0] == dict(text="  很厚实，纯棉  ", original_length=80)
    assert result["extraction_status"] == "PARTIAL"
    assert data["completeness"] == 0.75
    assert data["missing_fields"] == ["years_active", "certifications", "activity_history"]


def test_legacy_fields_and_zero_values_still_normalize():
    result = normalize_capture(capture(supplier_name="Supplier", price_text="\u00a535",
                                      company_location="广州", review_count=0, rating=0.0))
    data = result["supplier_data"]
    assert data["transaction_signals"] == {"review_count": 0}
    assert data["rating"] == 0.0
    assert data["price_information"] == {"display_text": "\u00a535"}
    assert data["company_information"] == {"location": "广州"}


def test_deduplication_preserves_different_values_and_does_not_invent_reviews():
    attrs = [pair(" 克重 ", "400g"), pair("克重", "400g"), pair("克重", "300g")]
    data = normalize_capture(capture(product_attributes=attrs, reviews=[dict(text=" ", original_length=1)]))["supplier_data"]
    assert data["products"][0]["attributes"] == [pair("克重", "400g"), pair("克重", "300g")]
    assert data["reviews"] is None
    assert data["rating"] is None
    assert data["transaction_signals"] is None


@pytest.mark.parametrize("fields", [
    {"cookies": "secret"}, {"supplier_metrics": [dict(name="x", value="y", session="secret")]},
    {"reviews": [dict(text="review", original_length=6, author="buyer")]},
    {"review_count": "40"}, {"rating": "4.8"}, {"rating": float("nan")},
    {"rating": 5.1}, {"rating": -0.1}, {"review_count": True},
    {"reviews": [dict(text="review", original_length=5)]},
    {"reviews": [dict(text="x", original_length=2_000_001)]},
    {"reviews": [dict(text="x", original_length="1")]},
    {"supplier_tenure": "x" * 161}, {"main_business": "x" * 161},
    {"price_details": "x" * 1201}, {"review_summary": "x" * 161},
    {"supplier_metrics": [pair("x", "y")] * 11},
    {"product_attributes": [pair("x", "y")] * 51},
    {"sku_options": [pair("x", "y")] * 21},
    {"shipping_details": [pair("x", "y")] * 11},
    {"consign_metrics": [pair("x", "y")] * 11},
    {"reviews": [dict(text="x", original_length=1)] * 21},
    {"reviews": [dict(text="x" * 2001, original_length=2001)]},
    {"product_attributes": [pair("x" * 81, "y")]},
    {"product_attributes": [pair("x", "y" * 241)]},
    {"product_attributes": [pair(" ", "y")]},
    {"reviews": [dict(text="x\x00y", original_length=3)]},
    {"supplier_metrics": [pair("x", "y\x01")]},
    {"price_details": "bad\rtext"}, {"main_business": "bad\ud800"},
])
def test_strict_bounds_privacy_and_recursive_invalid_text(fields):
    with pytest.raises(ValidationError):
        capture(**fields)


def test_source_identity_is_enforced_and_review_text_bound_to_canonical_offer():
    good = capture(reviews=[dict(text="Review", original_length=6)])
    good.source_url += "?tracking=x"
    result = normalize_capture(good)
    assert result["reviews"][0]["source_url"] == SOURCE
    good.offer_id = "996518024136"
    with pytest.raises(ValueError, match="Offer ID"):
        normalize_capture(good)


def test_metrics_alone_do_not_claim_successful_offer_capture():
    payload = DomCapture.model_validate(dict(source_url=SOURCE, offer_id="1027322610455",
        fields=dict(supplier_metrics=[pair("复购率", "48%")], rating=4.8)))
    assert normalize_capture(payload)["extraction_status"] == "PARSE_FAILED"
