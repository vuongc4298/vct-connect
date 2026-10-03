"""Replay the selected public fields retained by the audited HTTP adapters.

This cannot recover page content that the original selector did not retain.
Unsupported or incomplete raw shapes fail closed instead of borrowing values
from the old normalized snapshot.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from html import unescape
import math
import re
from urllib.parse import urlsplit
from uuid import UUID

from .contracts import (
    EVIDENCE_FIELDS, assemble_supplier_data, evidence_status, evidence_present as _present,
)
from .evidence import string as _string, validate_json_evidence as _validate_json_evidence
from .taobao import _id, _shop_binding
from .alibaba import _number, _metric, _supplier_host, _hint, _product_id
from .urls import (alibaba_identity, normalize_alibaba_url, normalize_source_url,
                   normalize_taobao_url, offer_id, source_platform, taobao_identity)


class UnsupportedRawEvidence(ValueError):
    """Retained fields cannot establish the requested revised mapping."""


VERSIONS = {"1688": "1688-raw.v2", "TAOBAO": "taobao-raw.v2",
            "ALIBABA": "alibaba-raw.v2"}
TOP_LEVEL_FIELDS = {"source_url", "captured_at", "html_sha256", "public_fields",
                    "rendered_html_sha256", "extraction_method", "extractor_version", "rendered_at"}
PUBLIC_FIELD_GROUPS = {
    ("1688", "offer"): {"title", "shop_info", "rate_info", "price", "offer_base", "reviews"},
    ("TAOBAO", "item"): {"item", "ssrItemId", "prices", "starting_price_text", "rate", "reviews",
                         "shop_metrics_display_text", "dom_title", "seller"},
    ("TAOBAO", "shop"): {"shopDuration", "evaluates", "products", "seller"},
    ("ALIBABA", "product"): {"product_identity", "jsonld_identity", "seller", "subject", "breadcrumb_names",
                             "offer_price", "storeReview", "tradeHalfYear", "onlinePerformance", "delivery",
                             "review_bodies", "productBasicProperties", "productKeyIndustryProperties",
                             "productOtherProperties"},
    ("ALIBABA", "profile"): {"esiteSubDomain", "supplierPerformance", "supplierActionBar", "factoryCapability",
                             "markets", "company_card_claims", "categories", "certifications", "products"},
}


def _mapping(value):
    if not isinstance(value, dict):
        raise UnsupportedRawEvidence("Unsupported public field shape")
    return value


def _sequence(value):
    if not isinstance(value, list) or len(value) > 2000:
        raise UnsupportedRawEvidence("Unsupported public field list")
    return value


def _scalar(value):
    # Match the finite scalar checks in the 1688 parser before counting evidence.
    if value is not None and (not isinstance(value, (str, int, float))
            or isinstance(value, bool) or isinstance(value, float) and not math.isfinite(value)):
        raise UnsupportedRawEvidence("Invalid 1688 scalar")


def _rating(value):
    _scalar(value)
    if value is not None and not isinstance(value, (int, float)):
        raise UnsupportedRawEvidence("Invalid 1688 rating")


def _integer(value):
    if value is not None and type(value) is not int:
        raise UnsupportedRawEvidence("Invalid integer metadata")


def _boolean(value):
    if value is not None and type(value) is not bool:
        raise UnsupportedRawEvidence("Invalid boolean metadata")


def _seller_id(value):
    if value is not None and (isinstance(value, bool) or not isinstance(value, (str, int))):
        raise UnsupportedRawEvidence("Invalid 1688 seller identifier")


def _selected(value, schema):
    """Validate every retained selection, including unused fields, without rewriting it."""
    if isinstance(schema, dict):
        value = _mapping(value)
        if not value.keys() <= schema.keys():
            raise UnsupportedRawEvidence("Unexpected nested selected field")
        for key, child in value.items():
            _selected(child, schema[key])
    elif isinstance(schema, list):
        for child in _sequence(value):
            _selected(child, schema[0])
    else:
        schema(value)


def _validate_selections(fields, platform, kind):
    strings = lambda *keys: dict.fromkeys(keys, _string)
    number = _number
    integer = lambda value: _number(value, integer=True)
    product = strings("offer_id", "title", "source_url")
    review = strings("text", "source_url")
    seller = strings("shopName", "pcShopUrl", "sellerType") | {"shopId": _id, "sellerId": _id, "tmall": _boolean}
    if platform == "1688":
        schema = {
            "title": _string, "shop_info": strings("authCompanyName", "companyName") | {"byrRepeatRate3m": _scalar},
            "rate_info": {"goodsGrade": _rating, "goodRates": _rating,
                          "commonTagNodeList": lambda value: _selected(value, [strings("name") | {"count": _integer}]) if value is not None else None},
            "price": dict.fromkeys(("offerMinPrice", "offerMaxPrice", "offerBeginAmount"), _scalar),
            "offer_base": strings("province", "location") | {"offerId": _scalar, "sellerUserId": _seller_id},
            "reviews": [review],
        }
    elif platform == "TAOBAO":
        schema = {"seller": seller}
        if kind == "item":
            price = strings("priceText", "priceTitle", "priceUnit", "priceDesc")
            schema |= {"item": strings("title", "vagueSellCount") | {"itemId": _id}, "ssrItemId": _id,
                       "prices": {"price": price, "extraPrice": price}, "starting_price_text": _string,
                       "rate": strings("sales_display_text", "review_count_display_text", "positive_review_rate_display_text"),
                       "reviews": [review | {"original_length": _integer, "retained_length": _integer,
                                              "normalized_limit": _integer, "truncated": _boolean}],
                       "shop_metrics_display_text": [_string], "dom_title": _string}
        else:
            schema |= {"shopDuration": _string, "evaluates": [strings("type", "title", "score", "levelText")], "products": [product]}
    elif kind == "product":
        identity_hint = strings("hostname", "path")
        attributes = [strings("attrName", "attrValue")]
        schema = {
            "product_identity": _product_id, "jsonld_identity": [{"sku": _product_id, "offers": [identity_hint]}],
            "seller": strings("subDomain", "companyProfileUrl", "companyName", "companyBusinessType", "companyRegisterCountry", "localCompanyJoinYears")
                      | {"companyJoinYears": integer, "home_identity": identity_hint},
            "subject": _string, "breadcrumb_names": [_string],
            "productBasicProperties": attributes, "productKeyIndustryProperties": attributes, "productOtherProperties": attributes,
            "offer_price": {"productRangePrices": strings("priceRangeText") | dict.fromkeys(
                                ("dollarPriceRangeLow", "dollarPriceRangeHigh", "priceRangeLow", "priceRangeHigh"), number),
                            "unit": _string, "moq": integer},
            "storeReview": strings("reviewRatingText") | {"averageStar": number, "totalReviewCount": integer},
            "tradeHalfYear": {"ordAmt": _string, "ordAmt6m": number, "ordCnt6m": integer},
            "onlinePerformance": [strings("title", "value", "desc")],
            "delivery": strings("packagingDesc", "unitSize", "unitWeight", "supplierOnTimeDeliveryRate", "responseTimeText")
                        | {"ladderPeriodList": [dict.fromkeys(("minQuantity", "maxQuantity", "processPeriod"), integer)]},
            "review_bodies": [review | {"original_length": _integer, "truncated": _boolean}],
        }
    else:
        schema = {
            "esiteSubDomain": _string,
            "supplierPerformance": {"companyName": _string, "years": strings("label", "value"),
                "reviews": strings("value", "label") | {"count": integer}} | dict.fromkeys(
                ("onlineTransactions", "bigBuyerCount", "reorderRate", "shippingDays", "responseTime"), strings("amount", "value", "label")),
            "supplierActionBar": {"companyName": _string, "rating": number, "reviewCount": integer},
            "factoryCapability": [strings("fieldName", "label", "type", "value")],
            "markets": [strings("name", "percentage")], "company_card_claims": [_string],
            "categories": [strings("text", "href")], "certifications": [strings("name", "category")],
            "products": [product | strings("price_display_text", "minimum_order_display_text")],
        }
    _selected(fields, schema)
    _validate_json_evidence(fields)


def _reviews(values, source_url):
    result = []
    for item in _sequence(values):
        body = _mapping(item).get("text")
        if item.get("source_url") != source_url or not isinstance(body, str):
            raise UnsupportedRawEvidence("Unbound review evidence")
        review = {"text": body[:4096].strip()[:2000], "source_url": source_url}
        if review["text"] and review not in result and len(result) < 20:
            result.append(review)
    return result


def _offer(fields, url):
    if not {"title", "shop_info", "rate_info", "price", "offer_base", "reviews"} <= fields.keys():
        raise UnsupportedRawEvidence("Missing 1688 field group")
    shop, rate, price, base = (_mapping(fields[key]) for key in
                               ("shop_info", "rate_info", "price", "offer_base"))
    identity = offer_id(url)
    if str(base.get("offerId")) != identity:
        raise UnsupportedRawEvidence("Unbound 1688 offer")
    reviews = _reviews(fields["reviews"], url)
    name = _string(shop.get("authCompanyName")) or _string(shop.get("companyName"))
    title = _string(fields["title"])
    if not name and not title:
        raise UnsupportedRawEvidence("No retained 1688 identity evidence")
    count = next((tag.get("count") for tag in _sequence(rate.get("commonTagNodeList") or [])
                  if _mapping(tag).get("name") == "全部" and type(tag.get("count")) is int), None)
    company = {key: value for key, value in {
        "registered_name": _string(shop.get("authCompanyName")),
        "display_name": _string(shop.get("companyName")),
        "location": _string(base.get("province")) or _string(base.get("location")),
    }.items() if _present(value)}
    quote = {key: price.get(source) for key, source in
             (("minimum", "offerMinPrice"), ("maximum", "offerMaxPrice"),
              ("minimum_order_quantity", "offerBeginAmount")) if _present(price.get(source))}
    signals = {key: value for key, value in {
        "review_count": count, "positive_review_rate": rate.get("goodRates"),
        "repeat_purchase_rate": shop.get("byrRepeatRate3m"),
    }.items() if _present(value)}
    evidence = dict.fromkeys(EVIDENCE_FIELDS)
    evidence.update(supplier_name=name, company_information=company or None,
                    products=[{"offer_id": identity, "title": title}] if title else None,
                    price_information=quote or None, transaction_signals=signals or None,
                    rating=rate.get("goodsGrade"), reviews=reviews or None)
    return str(base["sellerUserId"]) if _present(base.get("sellerUserId")) else None, identity, evidence, reviews


def _taobao(fields, url):
    kind, identity = taobao_identity(url)
    seller = _mapping(fields.get("seller"))
    if kind == "item":
        if not {"item", "ssrItemId", "prices", "starting_price_text", "rate", "reviews", "shop_metrics_display_text", "dom_title"} <= fields.keys():
            raise UnsupportedRawEvidence("Missing Taobao item field group")
        item = _mapping(fields["item"])
        bound = [_id(item.get("itemId")), _id(fields["ssrItemId"])]
        if not any(bound) or any(value is not None and value != identity for value in bound):
            raise UnsupportedRawEvidence("Unbound Taobao item")
        if any(value is not None for value in seller.values()):
            _shop_binding(seller)
    else:
        if not {"shopDuration", "evaluates", "products"} <= fields.keys() or _id(seller.get("shopId")) != identity:
            raise UnsupportedRawEvidence("Unbound Taobao shop")
        _shop_binding(seller, identity)
    evidence = dict.fromkeys(EVIDENCE_FIELDS)
    evidence["supplier_name"] = _string(seller.get("shopName"))
    reviews = []
    if kind == "item":
        title = _string(item.get("title")) or _string(fields["dom_title"])
        evidence["products"] = [{"offer_id": identity, "title": title}] if title else None
        prices = _mapping(fields["prices"])
        quote = {}
        for name in ("price", "extraPrice"):
            selected = {key: _string(value) for key, value in _mapping(prices.get(name)).items()}
            if selected.get("priceText"):
                quote[name] = selected
        starting = _string(fields["starting_price_text"])
        if starting:
            quote["starting_price_text"] = starting
        evidence["price_information"] = quote or None
        signals = {key: _string(value) for key, value in _mapping(fields["rate"]).items() if _string(value)}
        metrics = [_string(value) for value in _sequence(fields["shop_metrics_display_text"])]
        metrics = [value for value in metrics if value]
        if metrics:
            signals["shop_metrics_display_text"] = metrics
            shipping = [value for value in metrics if re.fullmatch(r"平均[0-9]+小时发货", value)]
            evidence["delivery_information"] = {"shop_shipping_display_text": shipping} if shipping else None
        evidence["transaction_signals"] = signals or None
        reviews = _reviews(fields["reviews"], url)
        evidence["reviews"] = reviews or None
    else:
        duration = _string(fields["shopDuration"])
        match = re.fullmatch(r"([0-9]{1,3})年老店", duration or "")
        evidence["years_active"] = int(match[1]) if match else None
        metrics = [{key: _string(value) for key, value in _mapping(entry).items()}
                   for entry in _sequence(fields["evaluates"])]
        metrics = [item for item in metrics if item.get("title") and item.get("score")]
        evidence["transaction_signals"] = {"shop_evaluations": metrics} if metrics else None
        products = []
        for entry in _sequence(fields["products"]):
            entry = _mapping(entry)
            product_url = normalize_taobao_url(entry.get("source_url"))
            product_kind, product_id = taobao_identity(product_url)
            if product_kind != "item" or entry.get("offer_id") != product_id:
                raise UnsupportedRawEvidence("Unbound Taobao shop product")
            product = {"offer_id": product_id, "title": _string(entry.get("title")), "source_url": product_url}
            if not any(item["offer_id"] == product_id for item in products) and len(products) < 20:
                products.append(product)
        evidence["products"] = products or None
    if not evidence["supplier_name"] and not evidence["products"]:
        raise UnsupportedRawEvidence("No retained Taobao identity evidence")
    return _id(seller.get("sellerId")), identity if kind == "item" else None, evidence, reviews


def _alibaba(fields, url):
    kind, identity = alibaba_identity(url)
    evidence = dict.fromkeys(EVIDENCE_FIELDS)
    reviews = []
    if kind == "product":
        required = {"product_identity", "seller", "subject", "breadcrumb_names", "offer_price",
                    "storeReview", "tradeHalfYear", "onlinePerformance", "delivery", "review_bodies"}
        if not required <= fields.keys() or str(fields["product_identity"]) != identity:
            raise UnsupportedRawEvidence("Unbound Alibaba product")
        for entry in _sequence(fields.get("jsonld_identity", [])):
            entry = _mapping(entry)
            if "sku" in entry and _product_id(entry["sku"]) != identity:
                raise UnsupportedRawEvidence("Conflicting Alibaba product identity")
            for offer in _sequence(entry.get("offers", [])):
                offer = _mapping(offer)
                _hint(f"https://{offer.get('hostname', '')}{offer.get('path', '')}", (kind, identity))
        seller = _mapping(fields["seller"])
        hosts = [_supplier_host(seller.get(key)) for key in ("subDomain", "companyProfileUrl")
                 if seller.get(key) is not None]
        if "home_identity" in seller:
            home = _mapping(seller["home_identity"])
            hosts.append(_supplier_host(f"https://{home.get('hostname', '')}{home.get('path', '')}"))
        hosts = [value for value in hosts if value]
        if len(set(hosts)) > 1:
            raise UnsupportedRawEvidence("Conflicting Alibaba supplier identity")
        host = hosts[0] if hosts else None
        evidence["supplier_name"] = _string(seller.get("companyName"))
        company = {key: value for key, value in {
            "company_name": evidence["supplier_name"], "business_type": _string(seller.get("companyBusinessType")),
            "register_country": _string(seller.get("companyRegisterCountry")),
        }.items() if value}
        evidence["company_information"] = company or None
        evidence["years_active"] = _number(seller.get("companyJoinYears"), integer=True, maximum=200)
        attributes = []
        for group in ("productBasicProperties", "productKeyIndustryProperties", "productOtherProperties"):
            for entry in _sequence(fields.get(group, [])):
                entry = _mapping(entry)
                label, value = _string(entry.get("attrName")), _string(entry.get("attrValue"))
                if label and value and {"name": label, "value": value} not in attributes:
                    attributes.append({"name": label, "value": value})
        title = _string(fields["subject"])
        evidence["products"] = [{"offer_id": identity, "title": title, "source_url": url, "attributes": attributes}] if title else None
        evidence["categories"] = list(dict.fromkeys(value for value in
                                      (_string(item) for item in _sequence(fields["breadcrumb_names"])) if value)) or None
        price = _mapping(fields["offer_price"])
        ranges = _mapping(price.get("productRangePrices"))
        low, high = (_number(ranges.get(key)) for key in ("dollarPriceRangeLow", "dollarPriceRangeHigh"))
        if low is not None and high is not None and low > high:
            raise UnsupportedRawEvidence("Inconsistent Alibaba price")
        quote = {key: value for key, value in {
            "minimum": str(ranges["dollarPriceRangeLow"]) if low is not None else None,
            "maximum": str(ranges["dollarPriceRangeHigh"]) if high is not None else None,
            "currency": "USD" if low is not None or high is not None else None,
            "display_text": _string(ranges.get("priceRangeText")), "unit": _string(price.get("unit")),
            "minimum_order_quantity": _number(price.get("moq"), integer=True),
        }.items() if value is not None}
        evidence["price_information"] = quote if low is not None or high is not None or quote.get("display_text") else None
        store = _mapping(fields["storeReview"])
        evidence["rating"] = _number(store.get("averageStar"), maximum=5)
        count = _number(store.get("totalReviewCount"), integer=True)
        metrics = [_metric(_mapping(item).get("title"), item.get("value"), "supplier performance", item.get("desc"))
                   for item in _sequence(fields["onlinePerformance"])]
        metrics = [item for item in metrics if item]
        trade = _mapping(fields["tradeHalfYear"])
        if trade.get("ordAmt") is not None:
            metric = _metric("Online order amount (past 6 months)", trade["ordAmt"], "supplier tradeHalfYear")
            if metric:
                metrics.append(metric)
        for key, label in (("ordAmt6m", "Online order amount (past 6 months)"), ("ordCnt6m", "Online orders (past 6 months)")):
            if trade.get(key) is not None:
                metrics.append({"label": label, "value": str(_number(trade[key], integer=key == "ordCnt6m")), "scope": "supplier tradeHalfYear"})
        delivery_labels = {"Response time ⓘ", "On-time dispatch rate ⓘ", "Average dispatch time ⓘ"}
        transaction = [item for item in metrics if item["label"] not in delivery_labels]
        evidence["transaction_signals"] = ({"review_count": count} if count is not None else {}) | ({"source_metrics": transaction} if transaction else {}) or None
        delivery = _mapping(fields["delivery"])
        delivery_metrics = [item for item in metrics if item["label"] in delivery_labels]
        for key, label in (("packagingDesc", "Packaging"), ("unitSize", "Package size"), ("unitWeight", "Package weight"),
                           ("supplierOnTimeDeliveryRate", "On-time dispatch rate"), ("responseTimeText", "Response time")):
            metric = _metric(label, delivery.get(key), "supplier performance" if key.startswith("supplier") or key == "responseTimeText" else "main product packaging")
            if metric:
                delivery_metrics.append(metric)
        lead_times = []
        for item in _sequence(delivery.get("ladderPeriodList", [])):
            item = _mapping(item)
            selected = {key: _number(item.get(key), integer=True) for key in ("minQuantity", "maxQuantity", "processPeriod")}
            if all(value is not None for value in selected.values()):
                if selected["minQuantity"] > selected["maxQuantity"]:
                    raise UnsupportedRawEvidence("Inconsistent Alibaba lead time")
                lead_times.append(selected)
        evidence["delivery_information"] = ({"source_metrics": delivery_metrics} if delivery_metrics else {}) | ({"lead_times": lead_times} if lead_times else {}) or None
        reviews = _reviews(fields["review_bodies"], url)
        evidence["reviews"] = reviews or None
    else:
        required = {"esiteSubDomain", "supplierPerformance", "supplierActionBar", "factoryCapability", "markets",
                    "categories", "certifications", "products"}
        if not required <= fields.keys() or fields["esiteSubDomain"] != f"{identity}.en.alibaba.com":
            raise UnsupportedRawEvidence("Unbound Alibaba profile")
        host = fields["esiteSubDomain"]
        performance, action = _mapping(fields["supplierPerformance"]), _mapping(fields["supplierActionBar"])
        names = [_string(value) for value in (performance.get("companyName"), action.get("companyName")) if value is not None]
        if len(set(names)) > 1:
            raise UnsupportedRawEvidence("Conflicting Alibaba supplier names")
        evidence["supplier_name"] = names[0] if names else None
        years = _string(_mapping(performance.get("years")).get("value"))
        match = re.fullmatch(r"([0-9]{1,3}) yrs?", years or "")
        if years and not match:
            raise UnsupportedRawEvidence("Unsupported Alibaba tenure")
        evidence["years_active"] = int(match[1]) if match else None
        company = {"company_name": evidence["supplier_name"]} if evidence["supplier_name"] else {}
        for item in _sequence(fields["factoryCapability"]):
            item = _mapping(item)
            label, value = _string(item.get("label")), _string(item.get("value"))
            if label and value:
                company[label] = value
        markets = [_mapping(item) for item in _sequence(fields["markets"])]
        if markets:
            company["markets_display_text"] = " · ".join(" ".join((_string(item.get("name")) or "", _string(item.get("percentage")) or "")).strip() for item in markets)
        for claim in _sequence(fields.get("company_card_claims", [])):
            if claim not in {"Custom Manufacturer", "CN"}:
                raise UnsupportedRawEvidence("Unsupported Alibaba company claim")
            company["business_type" if claim != "CN" else "register_country"] = claim
        evidence["company_information"] = company or None
        for item in _sequence(fields["categories"]):
            parsed = urlsplit(item.get("href") or "")
            if (parsed.scheme not in {"", "https"} or parsed.netloc and parsed.netloc != host
                    or "/productgrouplist-" not in parsed.path):
                raise UnsupportedRawEvidence("Unbound Alibaba category")
        evidence["categories"] = list(dict.fromkeys(value for value in
            (unescape(_string(_mapping(item).get("text")) or "").strip()
             for item in _sequence(fields["categories"])) if value)) or None
        evidence["certifications"] = list(dict.fromkeys(
            f"{_string(_mapping(item).get('name'))} ({_string(item.get('category'))})"
            for item in _sequence(fields["certifications"])
            if _string(_mapping(item).get("name")) and _string(item.get("category")))) or None
        products = []
        for item in _sequence(fields["products"]):
            item = _mapping(item)
            product_url = normalize_alibaba_url(item.get("source_url"))
            product_kind, product_id = alibaba_identity(product_url)
            if product_kind != "product" or item.get("offer_id") != product_id:
                raise UnsupportedRawEvidence("Unbound Alibaba profile product")
            product = {key: unescape(value).strip() if isinstance(value, str)
                       and key not in {"offer_id", "source_url"} else value
                       for key, value in item.items()}
            if not any(entry["offer_id"] == product_id for entry in products) and len(products) < 20:
                products.append(product)
        evidence["products"] = products or None
        rating = _mapping(performance.get("reviews"))
        evidence["rating"] = _number(rating.get("value"), maximum=5)
        count = _number(rating.get("count"), integer=True)
        metrics, delivery = [], []
        for name in ("onlineTransactions", "bigBuyerCount", "reorderRate", "shippingDays", "responseTime"):
            item = _mapping(performance.get(name))
            metric = _metric(item.get("label"), item.get("amount", item.get("value")), "supplier performance")
            if metric:
                (delivery if name in {"shippingDays", "responseTime"} else metrics).append(metric)
        action_rating = _number(action.get("rating"), maximum=5)
        if action_rating is not None:
            metrics.append({"label": "Rating", "value": str(action_rating), "scope": "supplier action bar"})
        evidence["transaction_signals"] = ({"source_metrics": metrics} if metrics else {}) | ({"review_count": count} if count is not None else {}) or None
        evidence["delivery_information"] = {"source_metrics": delivery} if delivery else None
    if not evidence["supplier_name"] and not evidence["products"]:
        raise UnsupportedRawEvidence("No retained Alibaba identity evidence")
    return host, identity if kind == "product" else None, evidence, reviews


def renormalize_public_fields(*, raw_payload: dict, source_url: str, extraction_method: str,
                              analysis_mode: str, extracted_at: str, source_snapshot_id: UUID,
                              source_extractor_version: str, renormalized_at: datetime | None = None) -> dict:
    """Return a new outcome from retained fields, or raise UnsupportedRawEvidence."""
    try:
        if normalize_source_url(source_url) != source_url or extraction_method not in {"PUBLIC_HTTP", "PUBLIC_BROWSER"} or analysis_mode != "ACCOUNT_PUBLIC":
            raise UnsupportedRawEvidence("Only owned public captures can be replayed")
        raw = _mapping(raw_payload)
        fields = _mapping(raw.get("public_fields"))
        if (raw.get("source_url") != source_url or raw.get("captured_at") != extracted_at
                or not isinstance(raw.get("html_sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", raw["html_sha256"])
                or "renormalized_from_snapshot_id" in raw):
            raise UnsupportedRawEvidence("Incompatible raw capture provenance")
        platform = source_platform(source_url)
        if not isinstance(source_snapshot_id, UUID) or not isinstance(source_extractor_version, str) or not source_extractor_version:
            raise UnsupportedRawEvidence("Missing source revision identity")
        expected_version = f"{platform.lower()}-http.v1" if extraction_method == "PUBLIC_HTTP" else "public-browser.v1"
        if source_extractor_version != expected_version or raw.get("extractor_version", expected_version) != expected_version:
            raise UnsupportedRawEvidence("Unsupported source revision")
        kind = ("offer" if platform == "1688" else
                taobao_identity(source_url)[0] if platform == "TAOBAO" else alibaba_identity(source_url)[0])
        if not set(raw) <= TOP_LEVEL_FIELDS or not set(fields) <= PUBLIC_FIELD_GROUPS[platform, kind]:
            raise UnsupportedRawEvidence("Unexpected raw field group")
        if raw.get("extraction_method", extraction_method) != extraction_method:
            raise UnsupportedRawEvidence("Incompatible capture method")
        _selected({key: value for key, value in raw.items() if key != "public_fields"},
                  dict.fromkeys(TOP_LEVEL_FIELDS - {"public_fields"}, _string))
        _validate_selections(fields, platform, kind)
        captured = datetime.fromisoformat(extracted_at)
        if captured.tzinfo is None:
            raise UnsupportedRawEvidence("Capture time needs a timezone")
        if extraction_method == "PUBLIC_BROWSER" and (
                raw.get("extractor_version") != source_extractor_version
                or raw.get("rendered_at") != extracted_at
                or not isinstance(raw.get("rendered_html_sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", raw["rendered_html_sha256"])):
            raise UnsupportedRawEvidence("Incompatible render provenance")
        supplier_id, product_id, evidence, reviews = {"1688": _offer, "TAOBAO": _taobao,
                                                        "ALIBABA": _alibaba}[platform](fields, source_url)
        replay_time = (renormalized_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
        provenance = {"renormalized_from_snapshot_id": str(source_snapshot_id),
                      "source_extractor_version": source_extractor_version,
                      "renormalized_at": replay_time,
                      "replay_limitation": "retained_public_fields_only"}
        data = assemble_supplier_data(
            evidence, platform=platform, source_url=source_url, offer_id=product_id,
            platform_supplier_id=supplier_id, extracted_at=extracted_at,
            extraction_method=extraction_method, analysis_mode=analysis_mode,
            extractor_version=VERSIONS[platform], **provenance,
        )
        replay_raw = deepcopy(raw) | provenance
        result = {"source_url": source_url, "extraction_status": evidence_status(data),
                  **provenance, "supplier_data": data, "raw_payload": replay_raw, "reviews": reviews}
        _validate_json_evidence(result)
        return result
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        if isinstance(exc, UnsupportedRawEvidence):
            raise
        raise UnsupportedRawEvidence("Unsupported retained public field shape") from exc
