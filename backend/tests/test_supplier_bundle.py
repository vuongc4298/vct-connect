from datetime import datetime, timezone
from uuid import uuid4
import pytest
from backend.app.extraction.supplier_bundle import SupplierBundle, normalize_bundle

SHOP = "https://shopabcdef123.1688.com/"
FACTORY = "https://www.1688.com/factory/b2b-abcdef123.html"


def selected():
    return {"job_id": str(uuid4()), "product": {"source_url": "https://detail.1688.com/offer/1027322610455.html",
        "offer_id": "1027322610455", "fields": {"supplier_name": "Supplier", "product_title": "Shirt",
        "reviews": [{"text": "Good fabric", "original_length": 11}] * 10}}, "shop_url": SHOP,
        "shop": {"source_url": SHOP, "credit_url": SHOP + "page/creditdetail.html", "factory_url": FACTORY},
        "factory": {"source_url": FACTORY, "canonical_url": FACTORY, "shop_url": SHOP,
                    "claims": [{"name": "成立时间", "value": "2025.07.14"}, {"name": "员工总数", "value": "11~50人"}],
                    "description": "经销批发"},
        "outcomes": [{"page": "SHOP", "status": "OK"}, {"page": "FACTORY", "status": "OK"}]}


def normalize(value):
    return normalize_bundle(SupplierBundle.model_validate(value), at=datetime(2026, 10, 11, tzinfo=timezone.utc))


@pytest.mark.parametrize("field", ["description", "claim"])
def test_factory_text_rejects_jsonb_null_characters(field):
    value = selected()
    if field == "description": value["factory"]["description"] = "invalid\x00text"
    else: value["factory"]["claims"][0]["value"] = "invalid\x00text"
    with pytest.raises(ValueError): normalize(value)


def test_bundle_preserves_reviews_and_keeps_unknown_certificates_and_platform_claim_provenance():
    result = normalize(selected())
    data = result["supplier_data"]
    assert len(result["reviews"]) == 10
    assert data["years_active"] == 1
    assert data["certifications"] is None and data["activity_history"] is None
    assert data["extraction_method"] == "EXTENSION_DOM"
    assert data["company_information"]["factory_profile_source_url"] == FACTORY


@pytest.mark.parametrize("change", ["shop", "backlink", "canonical", "field", "future", "credentials", "outcome"])
def test_mismatched_or_unpermitted_supplier_evidence_rejected(change):
    value = selected()
    if change == "shop": value["shop"]["source_url"] = "https://shopdifferent123.1688.com/"
    if change == "backlink": value["factory"]["shop_url"] = "https://shopdifferent123.1688.com/"
    if change == "canonical": value["factory"]["canonical_url"] = "https://www.1688.com/factory/b2b-other123.html"
    if change == "field": value["factory"]["claims"].append({"name": "CCC", "value": "recommended company"})
    if change == "future": value["factory"]["claims"][0]["value"] = "2030.07.14"
    if change == "credentials": value["factory"]["description"] = "access_token=private"
    if change == "outcome": value["outcomes"][1]["status"] = "UNAVAILABLE"
    with pytest.raises(ValueError): normalize(value)


def test_collection_metadata_does_not_manufacture_company_evidence():
    value = selected()
    del value["shop"]; del value["factory"]
    value["outcomes"] = [{"page": p, "status": "NO_PERMISSION"} for p in ("SHOP", "FACTORY")]
    result = normalize(value)
    assert result["supplier_data"]["company_information"] is None
    assert "company_information" in result["supplier_data"]["missing_fields"]
