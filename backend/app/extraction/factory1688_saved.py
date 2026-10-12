"""Offline enrichment from linked, user-saved 1688 supplier pages.

No network requests or source scripts are executed. Profile facts are platform
claims, not independently verified legal or certification records.
"""
import copy
import json
from datetime import datetime, timezone
from hashlib import sha256
import re
from urllib.parse import parse_qs, urlsplit

from .contracts import evidence_coverage, evidence_status
from .dom import active, tree
from .urls import normalize_1688_url
from .shop1688_identity import shop_host

MAX_PAGE_BYTES = 2_000_000


def _shop(value):
    url = urlsplit(value)
    if (url.scheme != "https" or url.username or url.password or url.port or
            not shop_host(url.netloc)):
        raise ValueError("Unsupported linked shop identity")
    return f"https://{url.netloc}/"


def _page(html):
    if len(html.encode("utf-8")) > MAX_PAGE_BYTES:
        raise ValueError("Saved supplier page exceeds the size limit")
    parsed = tree(html)
    for node in parsed.css("script,style,iframe,form"):
        node.decompose()
    # Remove inactive descendants before reading parent text.
    inactive_roots = [node for node in parsed.css("*") if not active(node)
                      and (node.parent is None or active(node.parent))]
    for node in inactive_roots:
        node.decompose()
    return parsed


def _text(node, limit=1000):
    return " ".join(node.text(separator=" ").split())[:limit] if node else None


def enrich_saved_factory(base, *, product_html, shop_html, factory_html, factory_url, at=None):
    at = at or datetime.now(timezone.utc)
    source = normalize_1688_url(base["source_url"])
    if base["supplier_data"]["source_url"] != source or base["supplier_data"]["platform"] != "1688":
        raise ValueError("Base snapshot does not match the product")
    product, shop, factory = [_page(value) for value in (product_html, shop_html, factory_html)]
    canonical = product.css_first('link[rel="canonical"]')
    if canonical is None or normalize_1688_url(canonical.attributes.get("href", "")) != source:
        raise ValueError("Saved product identity does not match")
    product_links = {_shop(n.attributes["href"]) for n in product.css("#shopNavigation a.shop-company-name[href]")}
    if len(product_links) != 1:
        raise ValueError("Missing or ambiguous supplier shop link")
    shop_url = next(iter(product_links))
    shop_canonical = shop.css_first('link[rel="canonical"]')
    if shop_canonical is not None and _shop(shop_canonical.attributes.get("href", "")) != shop_url:
        raise ValueError("Saved shop canonical identity conflicts with the supplier")
    # The supplier's company-introduction module links its own credit page.
    # Recommendation/catalog links elsewhere cannot establish shop identity.
    shop_links = {n.attributes["href"].split("?")[0] for n in shop.css('#bd_2_container_0 a[href]')}
    if shop_url + "page/creditdetail.html" not in shop_links:
        raise ValueError("Saved shop does not match the linked supplier")
    factory_links = {n.attributes["href"].split("?")[0] for n in factory.css("#pc_card_baseinfo a[href]")}
    if shop_url not in factory_links:
        raise ValueError("Factory profile does not link back to the supplier shop")
    supplied = urlsplit(factory_url)
    ids = parse_qs(supplied.query).get("memberId", [])
    fac_ids = parse_qs(supplied.query).get("facMemId", [])
    if (supplied.scheme != "https" or supplied.netloc != "sale.1688.com" or
            supplied.path != "/factory/card.html" or len(ids) != 1 or
            not re.fullmatch(r"b2b-[a-z0-9]{6,60}", ids[0]) or fac_ids not in ([], ids)):
        raise ValueError("Unsupported factory profile identity")
    profile_url = f"https://www.1688.com/factory/{ids[0]}.html"
    profile_canonical = factory.css_first('link[rel="canonical"]')
    if profile_canonical is None or profile_canonical.attributes.get("href") != profile_url:
        raise ValueError("Factory member does not match saved canonical identity")
    claims = {}
    for label in factory.css("#pc_card_exhibition .ability_info .ability_key"):
        value = label.next
        if value and "ability_value" in (value.attributes.get("class") or "").split():
            name, text = _text(label, 80), _text(value, 240)
            if name in claims and claims[name] != text:
                raise ValueError("Conflicting factory profile labels")
            if name and text:
                claims[name] = text
            if len(claims) > 32:
                raise ValueError("Too many factory profile fields")
    if not claims:
        raise ValueError("No supported factory profile fields found")
    result = copy.deepcopy(base)
    data = result["supplier_data"]
    company = data.get("company_information") or {}
    company.update({"factory_profile_source_url": profile_url, "shop_source_url": shop_url,
                    "factory_profile_claims_display_text": "; ".join(f"{key}: {value}" for key, value in claims.items())})
    # The showroom introduction is selected separately from recommendations.
    for title in factory.css("#pc_card_exhibition div"):
        if _text(title) == "工厂展厅":
            company["factory_description_display_text"] = _text(title.next)
    established = claims.get("成立时间")
    if established:
        founded = datetime.strptime(established, "%Y.%m.%d").date()
        if founded > at.date():
            raise ValueError("Factory establishment date is in the future")
        company["established_date_claim"] = founded.isoformat()
        company["age_basis"] = "Completed years since platform-displayed establishment date; not independently verified"
        data["years_active"] = at.year - founded.year - ((at.month, at.day) < (founded.month, founded.day))
    data["company_information"] = company
    # Qualification links and recommendation badges are not certificates.
    # Product reviews/new-product badges are not supplier activity history.
    data["extraction_method"] = "USER_UPLOAD"
    data["analysis_mode"] = "ACCOUNT_PUBLIC"
    data["extractor_version"] = "1688-saved-factory-enrichment.v1"
    data["extracted_at"] = at.isoformat()
    data.update(evidence_coverage(data))
    result["extraction_status"] = evidence_status(data)
    result["raw_payload"] = {
        "provenance": "USER_SAVED_LINKED_SUPPLIER_PAGES",
        "base_snapshot_extracted_at": base["supplier_data"]["extracted_at"],
        "base_extraction_method": base["supplier_data"]["extraction_method"],
        "base_snapshot_id": base.get("supplier_snapshot_id"),
        "base_raw_sha256": sha256(json.dumps(base.get("raw_payload", {}), sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest(),
        "profile_source_url": profile_url, "shop_source_url": shop_url,
        "profile_claims": claims,
        "profile_sha256": sha256(factory_html.encode("utf-8")).hexdigest(),
        "shop_sha256": sha256(shop_html.encode("utf-8")).hexdigest(),
        "saved_page_capture_age": "UNKNOWN",
    }
    return result
