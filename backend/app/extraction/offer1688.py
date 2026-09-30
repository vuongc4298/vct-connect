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
import socket
import ssl
import time
from urllib.parse import urljoin

import certifi
import httpcore
import httpx
from selectolax.parser import HTMLParser

from .contracts import CONTRACT_VERSION, EVIDENCE_FIELDS
from .urls import normalize_1688_url, offer_id

EXTRACTOR_VERSION = "1688-http.v1"
UPLOAD_EXTRACTOR_VERSION = "1688-user-upload.v1"
MAX_HTML_BYTES = 2_000_000
MAX_REDIRECTS = 3


class UnsafeDestination(OSError):
    """DNS did not resolve only to public addresses for the approved host."""


class PublicOnlyBackend(httpcore.SyncBackend):
    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        if host != "detail.1688.com" or port != 443:
            raise UnsafeDestination("Unapproved connection destination")
        try:
            answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            addresses = {item[4][0] for item in answers}
            if not addresses or not all(ipaddress.ip_address(address).is_global for address in addresses):
                raise UnsafeDestination("Destination must have only public addresses")
        except (OSError, ValueError) as exc:
            raise UnsafeDestination("Destination DNS check failed") from exc
        # Connect to the checked literal IP. The HTTP origin stays the hostname,
        # so TLS still verifies detail.1688.com and sends the correct SNI.
        return super().connect_tcp(sorted(addresses)[0], port, timeout, local_address, socket_options)


def _public_transport() -> httpx.HTTPTransport:
    transport = httpx.HTTPTransport(trust_env=False)
    transport._pool.close()
    transport._pool = httpcore.ConnectionPool(
        ssl_context=ssl.create_default_context(cafile=certifi.where()),
        network_backend=PublicOnlyBackend(),
        max_connections=1,
        max_keepalive_connections=0,
    )
    return transport


def _text(node) -> str | None:
    if node is None:
        return None
    value = node.text(strip=True)
    return value or None


def _embedded_model(tree: HTMLParser) -> dict:
    marker = "})(window.contextPath,"
    for script in tree.css("script"):
        content = script.text()
        at = content.find(marker)
        if at >= 0:
            try:
                return json.JSONDecoder().raw_decode(content[at + len(marker):])[0]
            except (ValueError, TypeError):
                continue
    return {}


def _field(model: dict, *path):
    value = model
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _object(value) -> dict:
    return value if isinstance(value, dict) else {}


def _string(value) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    return None


def _present(value) -> bool:
    return value is not None and value != "" and value != []


def _blocked_page(tree: HTMLParser) -> bool:
    title = (_text(tree.css_first("title")) or "").lower()
    body = (_text(tree.css_first("body")) or "")[:2000].lower()
    markers = ("captcha", "verify you are human", "security verification", "access denied",
               "滑动验证", "安全验证", "请输入验证码", "登录后", "请登录", "访问受限")
    if any(marker in title or marker in body for marker in markers):
        return True
    # 1688 may return a JavaScript-only challenge with HTTP 200 and no body.
    for script in tree.css("script"):
        content = script.text()
        if "_____tmd_____/punish" in content or "sessionStorage.x5referer" in content:
            return True
    return False


def parse_1688_page(html: str, source_url: str, *, analysis_mode: str = "ACCOUNT_PUBLIC",
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
    canonical = tree.css_first('link[rel="canonical"]')
    matched_offer = False
    if canonical and canonical.attributes.get("href"):
        try:
            if normalize_1688_url(canonical.attributes["href"]) != source_url:
                return {"source_url": source_url, "extraction_status": "PARSE_FAILED", "reason": "OFFER_MISMATCH"}
            matched_offer = True
        except ValueError:
            return {"source_url": source_url, "extraction_status": "PARSE_FAILED", "reason": "OFFER_MISMATCH"}

    model = _embedded_model(tree)
    data = _object(_field(model, "result", "data"))
    title_fields = _object(_field(data, "productTitle", "fields"))
    shop = _object(title_fields.get("shopInfo"))
    rate = _object(title_fields.get("rateInfo"))
    price = _object(_field(data, "mainPrice", "fields", "finalPriceModel", "tradeWithoutPromotion"))
    root = _object(_field(data, "Root", "fields", "dataJson", "offerBaseInfo"))
    if _present(root.get("offerId")) and str(root["offerId"]) != offer_id(source_url):
        return {"source_url": source_url, "extraction_status": "PARSE_FAILED", "reason": "OFFER_MISMATCH"}
    if _present(root.get("offerId")):
        matched_offer = True
    if not matched_offer:
        return {"source_url": source_url, "extraction_status": "PARSE_FAILED", "reason": "UNVERIFIED_OFFER"}

    review_count = None
    for tag in rate.get("commonTagNodeList") or []:
        if isinstance(tag, dict) and tag.get("name") == "全部" and isinstance(tag.get("count"), int):
            review_count = tag["count"]
            break
    supplier_id = root.get("sellerUserId") or _field(model, "result", "global", "globalData", "model", "offerDetail", "sellerUserId")
    reviews = []
    seen_reviews = set()
    for card in tree.css(".evaluation-item, .review-item, .comment-item, .od-evaluation-item, [data-review-id]"):
        review_text = _text(card)
        if review_text and review_text not in seen_reviews:
            seen_reviews.add(review_text)
            reviews.append({"text": review_text[:2000], "source_url": source_url})
        if len(reviews) >= 20:
            break
    supplier_name = _string(shop.get("authCompanyName")) or _string(shop.get("companyName")) or _text(tree.css_first(".shop-company-name h1"))
    offer_title = _string(title_fields.get("title")) or _text(tree.css_first(".title-content h1"))
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
    missing = [key for key in EVIDENCE_FIELDS if not _present(evidence[key])]
    supplier_data = {
        "contract_version": CONTRACT_VERSION,
        "platform": "1688",
        "source_url": source_url,
        "offer_id": offer_id(source_url),
        "platform_supplier_id": str(supplier_id) if supplier_id else None,
        "extracted_at": timestamp,
        "extraction_method": extraction_method,
        "analysis_mode": analysis_mode,
        "extractor_version": (UPLOAD_EXTRACTOR_VERSION if extraction_method == "USER_UPLOAD"
                              else EXTRACTOR_VERSION),
        "completeness": round((len(EVIDENCE_FIELDS) - len(missing)) / len(EVIDENCE_FIELDS), 4),
        "completeness_denominator": list(EVIDENCE_FIELDS),
        "missing_fields": missing,
        **evidence,
    }
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
    return {
        "source_url": source_url,
        "extraction_status": "PARTIAL" if missing else "SUCCESS",
        "supplier_data": supplier_data,
        "raw_payload": raw_evidence,
        "reviews": reviews,
    }


def _public_dns(host: str) -> bool:
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
        return bool(addresses) and all(ipaddress.ip_address(address).is_global for address in addresses)
    except (OSError, ValueError):
        return False


def extract_1688(source_url: str, *, analysis_mode: str = "ACCOUNT_PUBLIC",
                 client: httpx.Client | None = None, dns_check=_public_dns,
                 clock=time.monotonic) -> dict:
    source_url = normalize_1688_url(source_url)
    owns_client = client is None
    if client is None:
        client = httpx.Client(transport=_public_transport(), follow_redirects=False, trust_env=False,
                              timeout=httpx.Timeout(10.0, connect=5.0),
                              headers={"User-Agent": "VCTConnectPublicEvidence/1.0", "Accept": "text/html"})
    try:
        current = source_url
        deadline = clock() + 25
        for _ in range(MAX_REDIRECTS + 1):
            if clock() >= deadline:
                return {"source_url": source_url, "extraction_status": "TIMEOUT", "reason": "HTTP_TIMEOUT"}
            if not dns_check("detail.1688.com"):
                return {"source_url": source_url, "extraction_status": "BLOCKED", "reason": "UNSAFE_DESTINATION"}
            try:
                with client.stream("GET", current, follow_redirects=False) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("location", "")
                        try:
                            current = normalize_1688_url(urljoin(current, location))
                        except ValueError:
                            return {"source_url": source_url, "extraction_status": "BLOCKED", "reason": "UNSAFE_REDIRECT"}
                        if current != source_url:
                            return {"source_url": source_url, "extraction_status": "BLOCKED", "reason": "OFFER_MISMATCH"}
                        continue
                    if response.status_code == 401:
                        return {"source_url": source_url, "extraction_status": "AUTH_REQUIRED", "reason": "LOGIN_REQUIRED"}
                    if response.status_code in (403, 429):
                        return {"source_url": source_url, "extraction_status": "BLOCKED", "reason": "ACCESS_CHALLENGE"}
                    if response.status_code != 200:
                        status = "UNSUPPORTED_PAGE" if response.status_code in (404, 410) else "PARSE_FAILED"
                        return {"source_url": source_url, "extraction_status": status, "reason": "HTTP_ERROR"}
                    if "text/html" not in response.headers.get("content-type", "").lower():
                        return {"source_url": source_url, "extraction_status": "PARSE_FAILED", "reason": "NON_HTML"}
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        if clock() >= deadline:
                            return {"source_url": source_url, "extraction_status": "TIMEOUT", "reason": "HTTP_TIMEOUT"}
                        content.extend(chunk)
                        if len(content) > MAX_HTML_BYTES:
                            return {"source_url": source_url, "extraction_status": "PARSE_FAILED", "reason": "PAGE_TOO_LARGE"}
                    return parse_1688_page(content.decode(response.encoding or "utf-8", errors="replace"),
                                           source_url, analysis_mode=analysis_mode)
            except UnsafeDestination:
                return {"source_url": source_url, "extraction_status": "BLOCKED", "reason": "UNSAFE_DESTINATION"}
            except httpx.TimeoutException:
                return {"source_url": source_url, "extraction_status": "TIMEOUT", "reason": "HTTP_TIMEOUT"}
            except (httpx.HTTPError, UnicodeError):
                return {"source_url": source_url, "extraction_status": "PARSE_FAILED", "reason": "HTTP_ERROR"}
        return {"source_url": source_url, "extraction_status": "BLOCKED", "reason": "REDIRECT_LIMIT"}
    finally:
        if owns_client:
            client.close()
