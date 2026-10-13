from datetime import datetime, timezone
from uuid import uuid4
import pytest
from backend.app.extraction.supplier_bundle import SupplierBundle, normalize_bundle
from backend.app.extraction.shop1688_identity import shop_identity
from backend.app.extraction.factory1688_identity import factory_identity

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


def test_named_shop_bundle_preserves_identity_across_all_sources():
    import json
    named = "https://hztxsy.1688.com/"
    value = json.loads(json.dumps(selected()).replace(SHOP, named))
    result = normalize(value)
    assert result["supplier_data"]["company_information"]["factory_profile_source_url"] == FACTORY
    assert shop_identity(named + "?offerId=778418840629") == named
    value["factory"]["shop_url"] = SHOP
    with pytest.raises(ValueError):
        normalize(value)


def test_named_factory_card_and_canonical_profile_resolve_to_one_identity():
    named = "https://www.1688.com/factory/hztxsy.html"
    assert factory_identity("https://sale.1688.com/factory/card.html?memberId=hztxsy&facMemId=hztxsy") == named
    assert factory_identity(named) == named
    import json
    value = json.loads(json.dumps(selected()).replace(SHOP, "https://hztxsy.1688.com/").replace(FACTORY, named))
    normalize(value)


@pytest.mark.parametrize("url", ["https://sale.1688.com/factory/card.html?memberId=hztxsy&memberId=",
    "https://sale.1688.com/factory/card.html?memberId=hztxsy&facMemId=other",
    "https://www.1688.com/factory/..%2Fhztxsy.html", "https://sale.1688.com:443/factory/card.html?memberId=hztxsy"])
def test_named_factory_rejects_ambiguous_or_unsafe_identity(url):
    with pytest.raises(ValueError): factory_identity(url)


@pytest.mark.parametrize("url", ["https://detail.1688.com/", "https://sale.1688.com/",
    "https://login.1688.com/", "https://www.1688.com/", "https://hztxsy.1688.com.evil.test/",
    "https://hztxsy.1688.com:443/", "https://user@hztxsy.1688.com/", "https://hztxsy.1688.com/page/offerlist.htm"])
def test_named_shop_identity_rejects_service_and_foreign_hosts(url):
    with pytest.raises(ValueError):
        shop_identity(url)


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


def test_company_area_and_staff_range_keep_their_actual_scope():
    value = selected()
    value['factory']['claims'].append({'name': '企业面积', 'value': '2100m²'})
    company = normalize(value)['supplier_data']['company_information']
    assert company['company_area_sqm'] == 2100
    assert company['employee_count_display_text'] == '11~50人'
    assert 'factory_area_sqm' not in company and 'employee_count' not in company
    assert company['factory_profile_claims']['企业面积'] == '2100m²'


def test_explicit_factory_area_and_production_lines_are_normalized():
    value = selected()
    value['factory']['claims'] += [{'name': '工厂面积', 'value': '3600m²'}, {'name': '生产线数量', 'value': '4条'}]
    company = normalize(value)['supplier_data']['company_information']
    assert company['factory_area_sqm'] == 3600 and company['production_line_count'] == 4
