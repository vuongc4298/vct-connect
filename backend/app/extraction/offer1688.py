"""Bounded public HTTP extraction for 1688 offer pages.

SupplierData v1 coverage is the number of present optional evidence fields divided
by the 12 names in EVIDENCE_FIELDS. Required provenance does not inflate coverage.
An absent field is unknown, never a safe-risk observation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import ipaddress
import json
import math
import socket
import ssl
import time
from urllib.parse import urljoin, urlsplit

import certifi
import httpcore
import httpx
from selectolax.parser import HTMLParser

from .contracts import (
    EVIDENCE_FIELDS, assemble_supplier_data, evidence_status, evidence_present as _present,
)
from .evidence import (
    MalformedPage, field as _field, object as _object, string as _string,
    text as _text, validate_json_evidence as _validate_json_evidence,
)
from .dom import login_page as _login_page
from .urls import normalize_1688_url, offer_id

EXTRACTOR_VERSION = "1688-http.v1"
UPLOAD_EXTRACTOR_VERSION = "1688-user-upload.v1"
from .fetch import (
    MAX_HTML_BYTES, MAX_REDIRECTS, FETCH_BUDGET_SECONDS, RETRY_DELAYS,
    TRANSIENT_HTTP_STATUSES, UnsafeDestination, TemporaryDNSFailure,
    DNSResolutionFailed, DeadlineStream, PublicOnlyBackend, _public_transport,
    _public_addresses, _public_dns, bounded_extract,
)


def _embedded_model(tree: HTMLParser) -> dict:
    marker = "})(window.contextPath,"
    malformed = False
    for script in tree.css("script"):
        content = script.text()
        at = content.find(marker)
        if at >= 0:
            try:
                model = json.JSONDecoder().raw_decode(content[at + len(marker):].lstrip(" \t\r\n"))[0]
                if isinstance(model, dict):
                    return model
                malformed = True
            except (ValueError, TypeError):
                malformed = True
                continue
    if malformed:
        raise MalformedPage
    return {}


def _blocked_page(tree: HTMLParser) -> bool:
    title = (_text(tree.css_first("title")) or "").lower()
    body = (_text(tree.css_first("body")) or "")[:2000].lower()
    markers = ("captcha", "verify you are human", "security verification", "access denied",
               "滑动验证", "安全验证", "请输入验证码", "访问受限")
    if any(marker in title or marker in body for marker in markers):
        return True
    # 1688 may return a JavaScript-only challenge with HTTP 200 and no body.
    for script in tree.css("script"):
        content = script.text()
        if "_____tmd_____/punish" in content or "sessionStorage.x5referer" in content:
            return True
    return False


def parse_1688_page(html: str, source_url: str, **kwargs) -> dict:
    """Parse captured evidence, returning fixed failures for malformed layouts."""
    source_url = normalize_1688_url(source_url)
    try:
        return _parse_1688_page(html, source_url, **kwargs)
    except (MalformedPage, RecursionError) as exc:
        tree = HTMLParser(html)
        visible = _text(tree.css_first(".shop-company-name h1")) or _text(tree.css_first(".title-content h1"))
        if _login_page(tree, has_public_evidence=bool(visible)):
            return {"source_url": source_url, "extraction_status": "AUTH_REQUIRED", "reason": "LOGIN_REQUIRED"}
        return {"source_url": source_url, "extraction_status": "PARSE_FAILED",
                "reason": "PARSER_LIMIT" if isinstance(exc, RecursionError) else "MALFORMED_PAGE"}


def _parse_1688_page(html: str, source_url: str, *, analysis_mode: str = "ACCOUNT_PUBLIC",
                    extracted_at: datetime | None = None,
                    extraction_method: str = "PUBLIC_HTTP",
                    uploaded_bytes: bytes | None = None) -> dict:
    """Parse one already fetched page; no network access or external assets."""
    if extraction_method not in {"PUBLIC_HTTP", "USER_UPLOAD"}:
        raise ValueError("Unsupported extraction method")
    source_url = normalize_1688_url(source_url)
    timestamp = (extracted_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    uploaded = extraction_method == "USER_UPLOAD"
    tree = HTMLParser(html)
    if _blocked_page(tree):
        return {"source_url": source_url, "extraction_status": "BLOCKED", "reason": "ACCESS_CHALLENGE"}
    if _login_page(tree, has_public_evidence=True):
        return {"source_url": source_url, "extraction_status": "AUTH_REQUIRED", "reason": "LOGIN_REQUIRED"}
    model = _embedded_model(tree)
    data = _object(_field(model, "result", "data"))
    title_fields = _object(_field(data, "productTitle", "fields"))
    shop = _object(title_fields.get("shopInfo"))
    rate = _object(title_fields.get("rateInfo"))
    price = _object(_field(data, "mainPrice", "fields", "finalPriceModel", "tradeWithoutPromotion"))
    root = _object(_field(data, "Root", "fields", "dataJson", "offerBaseInfo"))
    supplier_name = _string(shop.get("authCompanyName")) or _string(shop.get("companyName")) or _text(tree.css_first(".shop-company-name h1"))
    offer_title = _string(title_fields.get("title")) or _text(tree.css_first(".title-content h1"))
    if _login_page(tree, has_public_evidence=bool(supplier_name or offer_title)):
        return {"source_url": source_url, "extraction_status": "AUTH_REQUIRED", "reason": "LOGIN_REQUIRED"}
    canonical = tree.css_first('link[rel="canonical"]')
    matched_offer = False
    if canonical and canonical.attributes.get("href"):
        try:
            if normalize_1688_url(canonical.attributes["href"]) != source_url:
                return {"source_url": source_url, "extraction_status": "PARSE_FAILED", "reason": "OFFER_MISMATCH"}
            matched_offer = True
        except ValueError:
            return {"source_url": source_url, "extraction_status": "PARSE_FAILED", "reason": "OFFER_MISMATCH"}
    for value in (root.get("offerId"), root.get("sellerUserId"),
                  *(price.get(key) for key in ("offerMinPrice", "offerMaxPrice", "offerBeginAmount")),
                  rate.get("goodRates"), rate.get("goodsGrade"), shop.get("byrRepeatRate3m")):
        if value is not None and (not isinstance(value, (str, int, float)) or isinstance(value, bool)
                                  or isinstance(value, float) and not math.isfinite(value)):
            raise MalformedPage
    for value in (rate.get("goodRates"), rate.get("goodsGrade")):
        if value is not None and not isinstance(value, (int, float)):
            raise MalformedPage
    if _present(root.get("offerId")) and str(root["offerId"]) != offer_id(source_url):
        return {"source_url": source_url, "extraction_status": "PARSE_FAILED", "reason": "OFFER_MISMATCH"}
    if _present(root.get("offerId")):
        matched_offer = True
    if not matched_offer:
        return {"source_url": source_url, "extraction_status": "PARSE_FAILED", "reason": "UNVERIFIED_OFFER"}

    review_count = None
    tags = rate.get("commonTagNodeList")
    if tags is not None and (not isinstance(tags, list) or not all(isinstance(tag, dict) for tag in tags)):
        raise MalformedPage
    for tag in tags or []:
        if tag.get("name") == "全部" and type(tag.get("count")) is int:
            review_count = tag["count"]
            break
    supplier_id = root.get("sellerUserId") or _field(model, "result", "global", "globalData", "model", "offerDetail", "sellerUserId")
    if supplier_id is not None and (not isinstance(supplier_id, (str, int)) or isinstance(supplier_id, bool)):
        raise MalformedPage
    reviews = []
    seen_reviews = set()
    for card in tree.css(".evaluation-item, .review-item, .comment-item, .od-evaluation-item, [data-review-id]"):
        review_text = _text(card)
        if review_text and review_text not in seen_reviews:
            seen_reviews.add(review_text)
            reviews.append({"text": review_text[:2000], "source_url": source_url})
        if len(reviews) >= 20:
            break
    company_information = {
        key: value for key, value in {
            "registered_name": _string(shop.get("authCompanyName")),
            "display_name": _string(shop.get("companyName")),
            "location": _string(root.get("province")) or _string(root.get("location")),
        }.items() if _present(value)
    }
    price_information = {
        key: value for key, value in {
            "minimum": price.get("offerMinPrice"),
            "maximum": price.get("offerMaxPrice"),
            "minimum_order_quantity": price.get("offerBeginAmount"),
        }.items() if _present(value)
    }
    transaction_signals = {
        key: value for key, value in {
            "review_count": review_count,
            "positive_review_rate": rate.get("goodRates"),
            "repeat_purchase_rate": shop.get("byrRepeatRate3m"),
        }.items() if _present(value)
    }
    evidence = {
        "supplier_name": supplier_name,
        "company_information": company_information or None,
        "years_active": None,
        "categories": None,
        "certifications": None,
        "products": [{"offer_id": offer_id(source_url), "title": offer_title}] if offer_title else None,
        "price_information": price_information or None,
        "transaction_signals": transaction_signals or None,
        "rating": rate.get("goodsGrade"),
        "reviews": reviews or None,
        "delivery_information": None,
        "activity_history": None,
    }
    # Review aggregates are evidence; individual review text is only populated
    # when it is present in the fetched page. This capture has aggregates only.
    if not supplier_name and not offer_title:
        return {"source_url": source_url, "extraction_status": "PARSE_FAILED", "reason": "NO_PUBLIC_EVIDENCE"}
    supplier_data = assemble_supplier_data(
        evidence, platform="1688", source_url=source_url, offer_id=offer_id(source_url),
        platform_supplier_id=str(supplier_id) if supplier_id else None,
        extracted_at=timestamp, extraction_method=extraction_method, analysis_mode=analysis_mode,
        extractor_version=UPLOAD_EXTRACTOR_VERSION if uploaded else EXTRACTOR_VERSION,
    )
    raw_evidence = {
        "source_url": source_url,
        "captured_at": None if uploaded else timestamp,
        **({"imported_at": timestamp} if uploaded else {}),
        "html_sha256": sha256(uploaded_bytes if uploaded_bytes is not None else html.encode("utf-8")).hexdigest(),
        "public_fields": {
            "title": offer_title,
            "shop_info": {key: shop.get(key) for key in
                          ("authCompanyName", "companyName", "byrRepeatRate3m")},
            "rate_info": {key: rate.get(key) for key in
                          ("commonTagNodeList", "goodsGrade", "goodRates")},
            "price": {key: price.get(key) for key in
                      ("offerMinPrice", "offerMaxPrice", "offerBeginAmount")},
            "offer_base": {key: root.get(key) for key in
                           ("offerId", "sellerUserId", "province", "location")},
            "reviews": reviews,
        },
    }
    _validate_json_evidence(supplier_data)
    _validate_json_evidence(raw_evidence)
    return {
        "source_url": source_url,
        "extraction_status": evidence_status(supplier_data),
        "supplier_data": supplier_data,
        "raw_payload": raw_evidence,
        "reviews": reviews,
    }


def _login_destination(value: str) -> bool:
    try:
        target = urlsplit(value)
        return (target.scheme == "https" and target.netloc == "login.1688.com"
                and target.path == "/member/signin.htm" and not target.fragment)
    except ValueError:
        return False


def extract_1688(source_url: str, *, analysis_mode: str = "ACCOUNT_PUBLIC",
                 client: httpx.Client | None = None, dns_check=_public_dns,
                 clock=time.monotonic, sleep=time.sleep, browser_fallback=False, browser_renderer=None) -> dict:
    def access(html):
        tree = HTMLParser(html)
        if _blocked_page(tree):
            return "BLOCKED", "ACCESS_CHALLENGE"
        if _login_page(tree):
            return "AUTH_REQUIRED", "LOGIN_REQUIRED"
        return None

    return bounded_extract(
        source_url, normalize=normalize_1688_url, identity=offer_id,
        parse=lambda html, url, page_bytes, **kwargs: parse_1688_page(html, url, uploaded_bytes=page_bytes, **kwargs),
        classify_access=access, login_destination=_login_destination,
        allowed_hosts=("detail.1688.com",), analysis_mode=analysis_mode,
        client=client, dns_check=dns_check, clock=clock, sleep=sleep,
        accept_cookies=False, browser_fallback=browser_fallback, browser_renderer=browser_renderer,
    )
