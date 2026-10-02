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


@pytest.mark.parametrize("text", ["password=secret", "Cookie: sid=secret", "session_token=secret", "Bearer abcdefghijklmnop"])
def test_secret_shaped_selected_text_is_rejected(text):
    with pytest.raises(ValueError, match="sensitive page state"):
        reject_sensitive_page_state({"fields": {"product_title": text}})
