import copy
from uuid import uuid4

import pytest

from backend.app.extraction.extension1688 import DomCapture, normalize_capture
from backend.app.extraction.extension_merge import merge_extension_evidence, reject_sensitive_page_state
from backend.app.extraction.extensiontaobao import TaobaoCapture, normalize_taobao_capture


URL = "https://detail.1688.com/offer/996518024136.html"


def capture(fields):
    return normalize_capture(DomCapture.model_validate({
        "source_url": URL, "offer_id": "996518024136", "fields": fields,
    }))


def test_merge_preserves_prior_fields_and_deduplicates_evidence():
    original = capture({"supplier_name": "Old supplier", "product_title": "Dress"})
    previous_data = original["supplier_data"]
    previous_data["extraction_method"] = "PUBLIC_HTTP"
    previous_data["analysis_mode"] = "ACCOUNT_PUBLIC"
    previous_data["company_information"] = {"location": "Guangzhou"}
    previous_data["products"] = [{"offer_id": "996518024136", "title": "Dress", "attributes": [{"name": "fabric", "value": "cotton"}]}]
    previous_data["reviews"] = [{"text": "Good quality", "source_url": URL, "rating": 5}]
    snapshot_id = uuid4()
    previous = {"supplier_snapshot_id": snapshot_id, "supplier_data": copy.deepcopy(previous_data)}
    current = capture({"supplier_name": "Current supplier", "product_title": "Dress", "price_text": "¥20"})
    current["supplier_data"]["reviews"] = [{"text": " good   QUALITY ", "source_url": URL},
                                           {"text": "Arrived on time", "source_url": URL}]
    current["reviews"] = current["supplier_data"]["reviews"]
    merged = merge_extension_evidence(current, previous)
    data = merged["supplier_data"]
    assert data["supplier_name"] == "Current supplier"
    assert data["company_information"] == {"location": "Guangzhou"}
    assert data["price_information"] == {"display_text": "¥20"}
    assert data["products"] == [{"offer_id": "996518024136", "title": "Dress", "attributes": [{"name": "fabric", "value": "cotton"}]}]
    assert len(data["reviews"]) == len(merged["reviews"]) == 2
    assert data["reviews"][0]["rating"] == 5
    assert data["completeness"] > current["supplier_data"]["completeness"]
    assert merged["raw_payload"]["merged_from_snapshot_id"] == str(snapshot_id)
    assert merged["raw_payload"]["field_sources"]["supplier_name"] == ["EXTENSION_DOM"]
    assert merged["raw_payload"]["field_sources"]["reviews"] == [f"snapshot:{snapshot_id}", "EXTENSION_DOM"]
    assert merged["raw_payload"]["merged_from_extraction_method"] == "PUBLIC_HTTP"
    assert previous["supplier_data"] == previous_data
    assert "merged_from_snapshot_id" not in current["raw_payload"]


def test_merge_rejects_other_page():
    current = capture({"supplier_name": "Current"})
    previous = {"supplier_snapshot_id": uuid4(), "supplier_data": copy.deepcopy(current["supplier_data"])}
    previous["supplier_data"]["offer_id"] = "123456789012"
    with pytest.raises(ValueError, match="different page"):
        merge_extension_evidence(current, previous)


@pytest.mark.parametrize("platform", ["1688", "TAOBAO"])
@pytest.mark.parametrize("field,value", [("categories", []), ("certifications", []),
                                         ("activity_history", []), ("supplier_name", "")])
def test_merge_counts_empty_inherited_values_as_legacy_extension_evidence(platform, field, value):
    if platform == "1688":
        current = capture({"product_title": "Dress", "review_count": 0})
    else:
        current = normalize_taobao_capture(TaobaoCapture(
            source_url="https://item.taobao.com/item.htm?id=1076425861755",
            source_kind="item", source_id="1076425861755",
            fields={"product_title": "Shirt", "shop_metrics": ["Source metric"]},
        ))
    prior = copy.deepcopy(current["supplier_data"])
    prior.update(extraction_method="PUBLIC_HTTP", analysis_mode="ACCOUNT_PUBLIC")
    prior[field] = value
    previous = {"supplier_snapshot_id": uuid4(), "supplier_data": prior}
    before = copy.deepcopy(previous)
    merged = merge_extension_evidence(current, previous)
    assert merged["supplier_data"][field] == value
    assert field not in merged["supplier_data"]["missing_fields"]
    assert merged["supplier_data"]["completeness"] == 0.25
    assert merged["extraction_status"] == "PARTIAL"
    assert merged["raw_payload"]["field_sources"][field] == [f"snapshot:{previous['supplier_snapshot_id']}"]
    assert previous == before


def test_taobao_review_merge_keeps_one_copy_of_repeated_text():
    source = "https://item.taobao.com/item.htm?id=1076425861755"
    current = normalize_taobao_capture(TaobaoCapture.model_validate({
        "source_url": source, "source_kind": "item", "source_id": "1076425861755",
        "fields": {"supplier_name": "Shop", "product_title": "Shirt",
                   "reviews": [{"text": "Good shirt", "original_length": 10},
                               {"text": "Fast delivery", "original_length": 13}]},
    }))
    previous_data = copy.deepcopy(current["supplier_data"])
    previous_data["reviews"] = [{"text": "good  shirt", "source_url": source, "rating": 5}]
    previous_data["extraction_method"] = "PUBLIC_HTTP"
    previous_data["analysis_mode"] = "ACCOUNT_PUBLIC"
    merged = merge_extension_evidence(current, {"supplier_snapshot_id": uuid4(), "supplier_data": previous_data})
    assert len(merged["reviews"]) == 2
    assert merged["reviews"][0]["rating"] == 5
    assert merged["supplier_data"]["reviews"] == merged["reviews"]


def test_repeated_merge_keeps_original_field_and_dictionary_key_provenance():
    public = capture({"supplier_name": "Public supplier"})["supplier_data"]
    public["extraction_method"] = "PUBLIC_HTTP"
    public["analysis_mode"] = "ACCOUNT_PUBLIC"
    public["extracted_at"] = "2026-09-01T00:00:00+00:00"
    public["company_information"] = {"location": "Guangzhou", "registration": "Source claim"}
    public_id, first_id = uuid4(), uuid4()
    first = merge_extension_evidence(capture({"supplier_name": "First", "company_location": "Shenzhen"}),
                                     {"supplier_snapshot_id": public_id, "supplier_data": public})
    second = merge_extension_evidence(capture({"supplier_name": "Second", "company_location": "Beijing"}),
                                      {"supplier_snapshot_id": first_id,
                                       "supplier_data": first["supplier_data"],
                                       "raw_payload": first["raw_payload"]})
    raw = second["raw_payload"]
    assert second["supplier_data"]["company_information"] == {
        "location": "Beijing", "registration": "Source claim",
    }
    assert raw["dict_key_sources"]["company_information"] == {
        "location": ["EXTENSION_DOM"], "registration": [f"snapshot:{public_id}"],
    }
    assert raw["field_sources"]["company_information"] == ["EXTENSION_DOM", f"snapshot:{public_id}"]
    assert raw["merged_from_extracted_at"] == public["extracted_at"]
    assert raw["merged_from_extraction_method"] == "PUBLIC_HTTP"
    assert str(first_id) not in raw["source_snapshots"]


def test_merge_limits_repeated_review_and_product_growth():
    current = capture({"supplier_name": "Current"})
    prior = copy.deepcopy(current["supplier_data"])
    prior["extraction_method"] = "PUBLIC_HTTP"
    prior["analysis_mode"] = "ACCOUNT_PUBLIC"
    prior["company_information"] = {"location": "Guangzhou"}
    prior["reviews"] = [{"text": f"old review {i}", "source_url": URL} for i in range(20)]
    prior["products"] = [{"offer_id": str(i), "title": f"old product {i}"} for i in range(20)]
    current["supplier_data"]["reviews"] = [{"text": f"new review {i}", "source_url": URL} for i in range(20)]
    current["supplier_data"]["products"] = [{"offer_id": str(i + 20), "title": f"new product {i}"} for i in range(20)]
    merged = merge_extension_evidence(current, {"supplier_snapshot_id": uuid4(), "supplier_data": prior})
    assert len(merged["reviews"]) == len(merged["supplier_data"]["products"]) == 20
    assert merged["reviews"][0]["text"] == "new review 0"
    assert merged["supplier_data"]["products"][0]["title"] == "new product 0"
    assert merged["raw_payload"]["omitted_review_count"] == 20
    assert merged["raw_payload"]["omitted_product_count"] == 20
    assert merged["raw_payload"]["field_sources"]["reviews"] == ["EXTENSION_DOM"]


def test_duplicate_only_capture_is_deduplicated_without_prior_contribution():
    source = "https://item.taobao.com/item.htm?id=1076425861755"
    current = normalize_taobao_capture(TaobaoCapture.model_validate({
        "source_url": source, "source_kind": "item", "source_id": "1076425861755",
        "fields": {"supplier_name": "Shop", "product_title": "Shirt",
                   "reviews": [{"text": "Good shirt", "original_length": 10},
                               {"text": "Good shirt", "original_length": 10}]},
    }))
    prior = copy.deepcopy(current["supplier_data"])
    prior["reviews"] = None
    merged = merge_extension_evidence(current, {"supplier_snapshot_id": uuid4(), "supplier_data": prior})
    assert len(merged["reviews"]) == 1
    assert merged["supplier_data"]["reviews"] == merged["reviews"]
    assert "merged_from_snapshot_id" not in merged["raw_payload"]


@pytest.mark.parametrize("text", ["password=secret", "Cookie: sid=secret", "session_token=secret",
                                      "Bearer abcdefghijklmnop", "sid=abc123; auth=xyz",
                                      "csrftoken=abc123", "ASP.NET_SessionId=abc123",
                                      "cart=abc123; login=xyz"])
def test_secret_shaped_selected_text_is_rejected(text):
    with pytest.raises(ValueError, match="sensitive page state"):
        reject_sensitive_page_state({"fields": {"product_title": text}})
