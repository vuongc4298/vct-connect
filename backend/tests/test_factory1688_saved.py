from datetime import datetime, timezone
import copy

import pytest

from backend.app.extraction.extension1688 import DomCapture, normalize_capture
from backend.app.extraction.factory1688_saved import enrich_saved_factory

PRODUCT = "https://detail.1688.com/offer/1027322610455.html"
SHOP = "https://shop3e1674729h322.1688.com/"
PROFILE = "https://sale.1688.com/factory/card.html?memberId=b2b-222030383828763a1d&facMemId=b2b-222030383828763a1d"
CANONICAL = "https://www.1688.com/factory/b2b-222030383828763a1d.html"
PRODUCT_HTML = f'<link rel="canonical" href="{PRODUCT}"><div id="shopNavigation"><a class="shop-company-name" href="{SHOP}">Supplier</a></div>'
SHOP_HTML = f'<div id="bd_2_container_0"><a href="{SHOP}page/creditdetail.html">Company</a></div>'
FACTORY_HTML = f'''<link rel="canonical" href="{CANONICAL}">
<div id="pc_card_baseinfo"><a href="{SHOP}">Shop</a><div>2 years membership</div></div>
<div id="pc_card_exhibition"><div class="title">工厂展厅</div><div>经销批发</div>
<div class="ability_info"><div><span class="ability_key">成立时间</span><span class="ability_value">2025.07.14</span></div>
<div><span class="ability_key">员工总数</span><span class="ability_value">11~50人</span></div>
<div hidden><span class="ability_key">CERT</span><span class="ability_value">PRIVATE_SENTINEL</span></div></div></div>
<div>Other recommended supplier: ISO 9001 CCC</div><script>session_token="PRIVATE_SENTINEL"</script>'''


def base():
    return normalize_capture(DomCapture.model_validate({"source_url": PRODUCT, "offer_id": "1027322610455",
        "fields": {"supplier_name": "Supplier", "product_title": "Shirt", "reviews": [
            {"text": "Good fabric", "original_length": 11}]}}))


def enrich(**changes):
    args = dict(product_html=PRODUCT_HTML, shop_html=SHOP_HTML, factory_html=FACTORY_HTML, factory_url=PROFILE,
                at=datetime(2026, 10, 11, tzinfo=timezone.utc))
    return enrich_saved_factory(base(), **{**args, **changes})


def test_selected_profile_claims_preserve_unknowns_identity_and_product_evidence():
    result = enrich()
    data = result["supplier_data"]
    assert data["years_active"] == 1
    assert data["company_information"]["established_date_claim"] == "2025-07-14"
    assert data["company_information"]["factory_description_display_text"] == "经销批发"
    assert "11~50人" in data["company_information"]["factory_profile_claims_display_text"]
    assert data["certifications"] is None and data["activity_history"] is None
    assert data["products"] == base()["supplier_data"]["products"]
    assert result["reviews"] == base()["reviews"]
    assert result["raw_payload"]["profile_source_url"] == CANONICAL
    assert "PRIVATE_SENTINEL" not in str(result)
    assert "ISO 9001" not in str(result)


@pytest.mark.parametrize("changes", [
    {"product_html": PRODUCT_HTML.replace("1027322610455", "996518024136")},
    {"shop_html": SHOP_HTML.replace("shop3e1674729h322", "shopdifferent123")},
    {"shop_html": '<link rel="canonical" href="https://shopdifferent123.1688.com/">' + SHOP_HTML},
    {"shop_html": SHOP_HTML.replace('id="bd_2_container_0"', 'id="recommendations"')},
    {"factory_html": FACTORY_HTML.replace(SHOP, "https://shopdifferent123.1688.com/")},
    {"factory_html": FACTORY_HTML.replace("2025.07.14", "2030.07.14")},
    {"factory_url": PROFILE.replace("222030383828763a1d", "different123")},
    {"factory_url": PROFILE.replace("sale.1688.com", "evil.example")},
    {"shop_html": "x" * 2_000_001},
])
def test_rejects_mismatched_linked_sources_and_bounds(changes):
    with pytest.raises(ValueError):
        enrich(**changes)


def test_enrichment_does_not_mutate_the_original_snapshot():
    original = base()
    before = copy.deepcopy(original)
    enrich_saved_factory(original, product_html=PRODUCT_HTML, shop_html=SHOP_HTML,
                         factory_html=FACTORY_HTML, factory_url=PROFILE)
    assert original == before
