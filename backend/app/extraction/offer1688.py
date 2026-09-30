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

from .contracts import CONTRACT_VERSION, EVIDENCE_FIELDS
from .urls import normalize_1688_url, offer_id

EXTRACTOR_VERSION = "1688-http.v1"
UPLOAD_EXTRACTOR_VERSION = "1688-user-upload.v1"
MAX_HTML_BYTES = 2_000_000
MAX_REDIRECTS = 3
FETCH_BUDGET_SECONDS = 25
RETRY_DELAYS = (0.5, 1.0)
TRANSIENT_HTTP_STATUSES = {500, 502, 503, 504}


class UnsafeDestination(OSError):
    """DNS did not resolve only to public addresses for the approved host."""


class TemporaryDNSFailure(OSError):
    """A resolver failure that may recover within the extraction budget."""


class DNSResolutionFailed(OSError):
    """A permanent resolver failure, without exposing resolver details."""


def _public_addresses(host, port):
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        if exc.errno == socket.EAI_AGAIN:
            raise TemporaryDNSFailure("Temporary DNS failure") from exc
        raise DNSResolutionFailed("DNS resolution failed") from exc
    except TimeoutError as exc:
        raise httpx.ConnectTimeout("DNS timeout") from exc
    except OSError as exc:
        raise TemporaryDNSFailure("Temporary DNS failure") from exc
    try:
        if not addresses or not all(ipaddress.ip_address(address).is_global for address in addresses):
            raise UnsafeDestination("Destination must have only public addresses")
    except ValueError as exc:
        raise UnsafeDestination("Invalid DNS address") from exc
    return addresses


class DeadlineStream(httpcore.NetworkStream):
    """Clamp every socket operation, including later body reads, to one deadline."""

    def __init__(self, stream, deadline, clock):
        self.stream, self.deadline, self.clock = stream, deadline, clock

    def _timeout(self, timeout, error):
        remaining = self.deadline - self.clock()
        if remaining <= 0:
            raise error("Extraction deadline elapsed")
        return min(timeout, remaining) if timeout is not None else remaining

    def read(self, max_bytes, timeout=None):
        return self.stream.read(max_bytes, timeout=self._timeout(timeout, httpcore.ReadTimeout))

    def write(self, buffer, timeout=None):
        return self.stream.write(buffer, timeout=self._timeout(timeout, httpcore.WriteTimeout))

    def start_tls(self, ssl_context, server_hostname=None, timeout=None):
        stream = self.stream.start_tls(ssl_context, server_hostname=server_hostname,
                                       timeout=self._timeout(timeout, httpcore.ConnectTimeout))
        return DeadlineStream(stream, self.deadline, self.clock)

    def close(self):
        self.stream.close()

    def get_extra_info(self, info):
        return self.stream.get_extra_info(info)


class PublicOnlyBackend(httpcore.SyncBackend):
    def __init__(self, *, deadline=None, clock=time.monotonic):
        self.deadline, self.clock = deadline, clock

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        if host != "detail.1688.com" or port != 443:
            raise UnsafeDestination("Unapproved connection destination")
        started = self.clock()
        addresses = _public_addresses(host, port)
        # OS DNS resolution cannot be forcibly cancelled here. Recheck the
        # budget before connecting, and debit its elapsed time from connect.
        if timeout is not None:
            timeout -= self.clock() - started
        if self.deadline is not None:
            remaining = self.deadline - self.clock()
            timeout = min(timeout, remaining) if timeout is not None else remaining
        if timeout is not None and timeout <= 0:
            raise httpcore.ConnectTimeout("Extraction deadline elapsed")
        # Connect to the checked literal IP. The HTTP origin stays the hostname,
        # so TLS still verifies detail.1688.com and sends the correct SNI.
        stream = super().connect_tcp(sorted(addresses)[0], port, timeout, local_address, socket_options)
        return DeadlineStream(stream, self.deadline, self.clock) if self.deadline is not None else stream


def _public_transport(*, deadline, clock) -> httpx.HTTPTransport:
    transport = httpx.HTTPTransport(trust_env=False)
    transport._pool.close()
    transport._pool = httpcore.ConnectionPool(
        ssl_context=ssl.create_default_context(cafile=certifi.where()),
        network_backend=PublicOnlyBackend(deadline=deadline, clock=clock),
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


class MalformedPage(ValueError):
    """An observed embedded structure cannot safely supply evidence."""


def _validate_json_evidence(value):
    """Reject source values that PostgreSQL JSONB cannot retain."""
    if isinstance(value, str):
        if "\x00" in value:
            raise MalformedPage
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise MalformedPage from exc
    elif isinstance(value, float) and not math.isfinite(value):
        raise MalformedPage
    elif isinstance(value, dict):
        for key, item in value.items():
            _validate_json_evidence(key)
            _validate_json_evidence(item)
    elif isinstance(value, list):
        for item in value:
            _validate_json_evidence(item)


def _field(model: dict, *path):
    value = model
    for key in path:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise MalformedPage
        value = value.get(key)
    return value


def _object(value) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise MalformedPage
    return value


def _string(value) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if value is not None:
        raise MalformedPage
    return None


def _present(value) -> bool:
    return value is not None and value != "" and value != []


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


def _login_page(tree: HTMLParser, *, has_public_evidence=False) -> bool:
    title = (_text(tree.css_first("title")) or "").lower()
    body = (_text(tree.css_first("body")) or "")[:2000].lower()
    markers = ("login required", "please log in", "please sign in", "登录后", "请登录")
    return (any(marker in title for marker in markers)
            or title.strip() in {"login", "sign in", "登录", "用户登录", "会员登录", "1688登录"}
            or not has_public_evidence and any(marker in body for marker in markers))


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
    _validate_json_evidence(supplier_data)
    _validate_json_evidence(raw_evidence)
    return {
        "source_url": source_url,
        "extraction_status": "PARTIAL" if missing else "SUCCESS",
        "supplier_data": supplier_data,
        "raw_payload": raw_evidence,
        "reviews": reviews,
    }


def _public_dns(host: str) -> bool:
    _public_addresses(host, 443)
    return True


def _login_destination(value: str) -> bool:
    try:
        target = urlsplit(value)
        return (target.scheme == "https" and target.netloc == "login.1688.com"
                and target.path == "/member/signin.htm" and not target.fragment)
    except ValueError:
        return False


def _certificate_failure(exc: Exception) -> bool:
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc, ssl.SSLCertVerificationError):
            return True
        exc = exc.__cause__ or exc.__context__
    return False


def extract_1688(source_url: str, *, analysis_mode: str = "ACCOUNT_PUBLIC",
                 client: httpx.Client | None = None, dns_check=_public_dns,
                 clock=time.monotonic, sleep=time.sleep) -> dict:
    try:
        source_url = normalize_1688_url(source_url)
    except ValueError:
        return {"source_url": source_url, "extraction_status": "UNSUPPORTED_PAGE", "reason": "INVALID_URL"}
    deadline = clock() + FETCH_BUDGET_SECONDS

    def outcome(status, reason):
        return {"source_url": source_url, "extraction_status": status, "reason": reason}

    owns_client = client is None
    if client is None:
        client = httpx.Client(transport=_public_transport(deadline=deadline, clock=clock),
                              follow_redirects=False, trust_env=False,
                              timeout=httpx.Timeout(10.0, connect=5.0),
                              headers={"User-Agent": "VCTConnectPublicEvidence/1.0", "Accept": "text/html"})
    try:
        current = source_url
        redirects = retries = 0
        seen_redirects = {source_url}
        while True:
            transient = None
            try:
                if clock() >= deadline:
                    return outcome("TIMEOUT", "HTTP_TIMEOUT")
                if not dns_check("detail.1688.com"):
                    return outcome("BLOCKED", "UNSAFE_DESTINATION")
                remaining = deadline - clock()
                if remaining <= 0:
                    return outcome("TIMEOUT", "HTTP_TIMEOUT")
                timeout = httpx.Timeout(min(10.0, remaining), connect=min(5.0, remaining))
                with client.stream("GET", current, follow_redirects=False, timeout=timeout) as response:
                    if clock() >= deadline:
                        return outcome("TIMEOUT", "HTTP_TIMEOUT")
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("location", "")
                        try:
                            target = urljoin(current, location)
                            if _login_destination(target):
                                return outcome("AUTH_REQUIRED", "LOGIN_REQUIRED")
                            destination = normalize_1688_url(target)
                        except ValueError:
                            return outcome("BLOCKED", "UNSAFE_REDIRECT")
                        if destination != source_url:
                            return outcome("BLOCKED", "OFFER_MISMATCH")
                        if destination in seen_redirects:
                            return outcome("BLOCKED", "REDIRECT_LOOP")
                        if redirects >= MAX_REDIRECTS:
                            return outcome("BLOCKED", "REDIRECT_LIMIT")
                        redirects += 1
                        seen_redirects.add(destination)
                        current = destination
                        continue
                    if response.status_code == 401:
                        return outcome("AUTH_REQUIRED", "LOGIN_REQUIRED")
                    if response.status_code in (403, 429):
                        return outcome("BLOCKED", "ACCESS_CHALLENGE")
                    is_transient = response.status_code in TRANSIENT_HTTP_STATUSES
                    if response.status_code != 200 and not is_transient:
                        status = "UNSUPPORTED_PAGE" if response.status_code in (404, 410) else "PARSE_FAILED"
                        return outcome(status, "HTTP_ERROR")
                    is_html = response.headers.get("content-type", "").split(";", 1)[0].strip().lower() == "text/html"
                    if not is_html:
                        if not is_transient:
                            return outcome("PARSE_FAILED", "NON_HTML")
                        transient = ("PARSE_FAILED", "UPSTREAM_UNAVAILABLE")
                    else:
                        content = bytearray()
                        chunks = iter(response.iter_bytes())
                        while True:
                            if clock() >= deadline:
                                return outcome("TIMEOUT", "HTTP_TIMEOUT")
                            try:
                                chunk = next(chunks)
                            except StopIteration:
                                break
                            if clock() >= deadline:
                                return outcome("TIMEOUT", "HTTP_TIMEOUT")
                            if len(chunk) > MAX_HTML_BYTES - len(content):
                                return outcome("PARSE_FAILED", "PAGE_TOO_LARGE")
                            content.extend(chunk)
                        if clock() >= deadline:
                            return outcome("TIMEOUT", "HTTP_TIMEOUT")
                        html = content.decode(response.encoding or "utf-8", errors="replace")
                        if is_transient:
                            tree = HTMLParser(html)
                            if _blocked_page(tree):
                                return outcome("BLOCKED", "ACCESS_CHALLENGE")
                            if _login_page(tree):
                                return outcome("AUTH_REQUIRED", "LOGIN_REQUIRED")
                            transient = ("PARSE_FAILED", "UPSTREAM_UNAVAILABLE")
                        else:
                            result = parse_1688_page(html, source_url, analysis_mode=analysis_mode)
                            return outcome("TIMEOUT", "HTTP_TIMEOUT") if clock() >= deadline else result
            except UnsafeDestination:
                return outcome("BLOCKED", "UNSAFE_DESTINATION")
            except DNSResolutionFailed:
                return outcome("PARSE_FAILED", "DNS_ERROR")
            except httpx.TimeoutException:
                transient = ("TIMEOUT", "HTTP_TIMEOUT")
            except TemporaryDNSFailure:
                transient = ("PARSE_FAILED", "DNS_ERROR")
            except httpx.RemoteProtocolError as exc:
                if str(exc).startswith("Invalid URL in location header:"):
                    return outcome("BLOCKED", "UNSAFE_REDIRECT")
                transient = ("PARSE_FAILED", "HTTP_ERROR")
            except httpx.NetworkError as exc:
                if _certificate_failure(exc):
                    return outcome("PARSE_FAILED", "HTTP_ERROR")
                transient = ("PARSE_FAILED", "HTTP_ERROR")
            except (httpx.HTTPError, UnicodeError, LookupError):
                return outcome("PARSE_FAILED", "HTTP_ERROR")
            # The response context has closed before a retry or backoff. Each
            # attempt starts with a fresh body; failed stream bytes are discarded.
            remaining = deadline - clock()
            if remaining <= 0:
                return outcome("TIMEOUT", "HTTP_TIMEOUT")
            if retries >= len(RETRY_DELAYS):
                return outcome(*transient)
            delay = RETRY_DELAYS[retries]
            if remaining <= delay:
                return outcome("TIMEOUT", "HTTP_TIMEOUT")
            sleep(delay)
            retries += 1
    finally:
        if owns_client:
            client.close()
