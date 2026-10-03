"""Taobao evidence from audited ICE product and g_config shop layouts.

Embedded JSON is data only. Full source models, user state and reviewer identities
are never retained. Display counts and shop metrics retain their original labels.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
import time
from urllib.parse import urlsplit, urlunsplit

from .contracts import (
    EVIDENCE_FIELDS, assemble_supplier_data, evidence_status, evidence_present as _present,
)
from .fetch import bounded_extract, _public_dns
from .evidence import (
    MalformedPage, field as _field, object as _object, string as _string,
    text as _text, validate_json_evidence as _validate_json_evidence,
)
from .dom import (
    tree as _tree, active as _active, scripts as _scripts, prune_dom as _prune_dom,
    login_page as _login_page,
)
from .urls import normalize_taobao_url, taobao_identity

EXTRACTOR_VERSION = "taobao-http.v1"


def _nodes(tree, prefix):
    return [node for node in tree.css("[class]")
            if _active(node) and any(token.startswith(prefix) for token in (node.attributes.get("class") or "").split())]


def _context_write(content):
    # Mask comments and quoted examples before looking for executable writes.
    # Retain the exact property-name literal needed by bracket/defineProperty.
    tokens = r'''//[^\r\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`'''
    interpolated_context = False
    def mask(match):
        nonlocal interpolated_context
        value = match[0]
        if value.startswith("`") and re.search(r"(?<!\\)\$\{[^}]*__ICE_APP_CONTEXT__", value):
            # Interpolations execute code. Their effective context cannot be
            # established without executing the template; reject ambiguity.
            interpolated_context = True
        return value if value in {'"__ICE_APP_CONTEXT__"', "'__ICE_APP_CONTEXT__'"} else " " * len(value)
    code = re.sub(tokens, mask, content)
    target = r"(?:window\s*\.\s*__ICE_APP_CONTEXT__|window\s*\[\s*['\"]__ICE_APP_CONTEXT__['\"]\s*\])"
    return (interpolated_context or re.search(target + r"\s*(?:(?:\|\||&&|\?\?)?=(?!=)|\.[A-Za-z_$][\w$]*\s*=(?!=)|\[[^\]]+\]\s*=(?!=))", code)
            or re.search(r"Object\.assign\s*\(\s*" + target + r"\s*,", code)
            or re.search(r"Object\.defineProperty\s*\(\s*window\s*,\s*['\"]__ICE_APP_CONTEXT__['\"]\s*,", code))


def _id(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not re.fullmatch(r"[1-9][0-9]{0,19}", str(value)):
        raise MalformedPage
    return str(value)


def _model(tree, kind):
    found = []
    for script in _scripts(tree):
        content = script.text()
        if kind == "item":
            match = re.match(r"\s*!\(function\s*\(\)\s*\{\s*var\s+a\s*=\s*window\.__ICE_APP_CONTEXT__\s*\|\|\s*\{\s*\}\s*;\s*var\s+b\s*=\s*", content)
        else:
            match = re.match(r"\s*window\.g_config\s*=\s*", content)
        if not match:
            # The audited wrapper copies any prior context over its JSON. Without
            # executing JavaScript that effective model cannot be established.
            if kind == "item" and _context_write(content):
                raise MalformedPage
            continue
        try:
            model, end = json.JSONDecoder().raw_decode(content[match.end():])
        except (ValueError, TypeError) as exc:
            raise MalformedPage from exc
        suffix = content[match.end() + end:]
        wrapper = (r"\s*;\s*for\s*\(var\s+k\s+in\s+a\)\s*\{\s*b\[k\]\s*=\s*a\[k\]\s*\}\s*window\.__ICE_APP_CONTEXT__\s*=\s*b\s*;\s*\}\)\(\);\s*"
                   if kind == "item" else r"\s*;?\s*(?:if\s*\(!window\.g_config\)\s*\{\s*window\.g_config\s*=\s*\{\s*\}\s*;\s*\}\s*)?")
        if not re.fullmatch(wrapper, suffix):
            raise MalformedPage
        found.append(_object(model))
    if len(found) > 1:
        raise MalformedPage
    return found[0] if found else {}


def _access(html, *, has_public_evidence=False, source_url=None):
    if source_url is not None:
        try:
            _parse(html, source_url, "ACCOUNT_PUBLIC", None, None)
            has_public_evidence = True
        except (MalformedPage, RecursionError, ValueError, TypeError):
            pass
    tree = _tree(html)
    # An observed small script-only TMD response redirects to its punishment
    # endpoint. A marker in a populated legitimate page is insufficient.
    scripts = "\n".join(s.text() for s in _scripts(tree))
    _prune_dom(tree)
    visible = _text(tree.css_first("body")) or ""
    title = (_text(tree.css_first("title")) or "").lower()
    challenge = ("_____tmd_____/punish" in scripts and "location" in scripts
                 or "_____tmd_____" in scripts and "login_jump" in scripts
                 and "window._config_" in scripts and "document.cookie" in scripts and "location" in scripts)
    if not has_public_evidence and (challenge or any(
                marker in title or marker in visible[:2000].lower()
                for marker in ("captcha", "verify you are human", "security verification", "access denied", "滑动验证", "安全验证", "请输入验证码", "访问受限"))):
        return "BLOCKED", "ACCESS_CHALLENGE"
    if not has_public_evidence and _login_page(tree):
        return "AUTH_REQUIRED", "LOGIN_REQUIRED"
    return None


def _shop_binding(seller, expected=None):
    shop_id = _id(seller.get("shopId"))
    if expected is not None and shop_id != expected:
        raise MalformedPage
    if seller.get("tmall") is not None and type(seller["tmall"]) is not bool:
        raise MalformedPage
    if seller.get("tmall") is True or seller.get("sellerType") in {"B", "TMALL", "tmall"}:
        raise MalformedPage
    url = _string(seller.get("pcShopUrl"))
    if url:
        if not shop_id:
            raise MalformedPage
        url = "https:" + url if url.startswith("//") else url
        if urlsplit(url).path == "":
            parsed = urlsplit(url)
            url = urlunsplit(parsed._replace(path="/"))
        try:
            if taobao_identity(url) != ("shop", shop_id):
                raise MalformedPage
        except ValueError as exc:
            raise MalformedPage from exc
    return shop_id


def parse_taobao_page(html, source_url, *, analysis_mode="ACCOUNT_PUBLIC", extracted_at=None, page_bytes=None,
                      extraction_method="PUBLIC_HTTP", uploaded_bytes=None):
    if extraction_method not in {"PUBLIC_HTTP", "USER_UPLOAD"} or analysis_mode not in {"GUEST_PUBLIC", "ACCOUNT_PUBLIC"}:
        raise ValueError("Invalid Taobao extraction provenance")
    if extraction_method == "USER_UPLOAD" and (analysis_mode != "ACCOUNT_PUBLIC" or uploaded_bytes is None):
        raise ValueError("Uploads require account provenance and original bytes")
    source_url = normalize_taobao_url(source_url)
    result, failure = None, None
    try:
        result = _parse(html, source_url, analysis_mode, extracted_at, page_bytes)
        if extraction_method == "USER_UPLOAD":
            result["supplier_data"].update(extraction_method="USER_UPLOAD", extractor_version="taobao-upload.v1")
            raw = result["raw_payload"]
            raw.update(captured_at=None, imported_at=result["supplier_data"]["extracted_at"],
                       html_sha256=sha256(uploaded_bytes).hexdigest(), provenance="USER_PROVIDED_SAVED_PAGE")
    except (MalformedPage, RecursionError, ValueError, TypeError) as exc:
        failure = "PARSER_LIMIT" if isinstance(exc, RecursionError) else "MALFORMED_PAGE"
    access = _access(html, has_public_evidence=result is not None)
    if access:
        return dict(source_url=source_url, extraction_status=access[0], reason=access[1])
    return result if result is not None else dict(source_url=source_url, extraction_status="PARSE_FAILED", reason=failure)


def _parse(html, source_url, mode, extracted_at, page_bytes):
    kind, identity = taobao_identity(source_url)
    tree = _tree(html)
    canonicals = [node for node in tree.css("link") if "canonical" in node.attributes.get("rel", "").lower().split()]
    if len(canonicals) > 1:
        raise MalformedPage
    if canonicals and taobao_identity(canonicals[0].attributes.get("href", "")) != (kind, identity):
        raise MalformedPage
    model = _model(tree, kind)
    # Selected DOM text excludes script/style and hidden descendants as well as
    # inactive selection roots. Source models have already been parsed in memory.
    _prune_dom(tree)
    evidence = dict.fromkeys(EVIDENCE_FIELDS)
    raw = {}
    reviews = []
    if kind == "item":
        data = _object(_field(model, "loaderData", "home", "data"))
        res = _object(data.get("res"))
        item = _object(res.get("item"))
        bound = [_id(data.get("ssrItemId")), _id(item.get("itemId"))]
        if not any(bound) or any(value is not None and value != identity for value in bound):
            raise MalformedPage
        seller = _object(res.get("seller"))
        if seller:
            _shop_binding(seller)
        title = _string(item.get("title"))
        raw_dom_title = None
        if not title:
            containers = _nodes(tree, "ItemTitle--")
            titles = [node.text() for region in containers for container in _nodes(region, "MainTitle--")
                      for node in _nodes(container, "mainTitle--") if _text(node)]
            if len(titles) > 1:
                raise MalformedPage
            title = _string(titles[0]) if titles else None
            raw_dom_title = titles[0] if titles else None
        evidence["products"] = [{"offer_id": identity, "title": title}] if title else None
        prices = _object(_field(res, "componentsVO", "priceVO"))
        raw_prices = {name: {key: _object(prices.get(name)).get(key)
                              for key in ("priceText", "priceTitle", "priceUnit", "priceDesc")}
                        for name in ("price", "extraPrice")}
        price_fields = {name: {key: _string(value) for key, value in values.items()} for name, values in raw_prices.items()}
        raw_starting = _field(res, "skuCore", "sku2info", "0", "subPrice", "priceText")
        starting = _string(raw_starting)
        price_evidence = {name: value for name, value in price_fields.items() if value["priceText"]}
        if starting:
            price_evidence["starting_price_text"] = starting
        evidence["price_information"] = price_evidence or None
        rate = _object(_field(res, "componentsVO", "rateVO"))
        raw_signals = {"sales_display_text": item.get("vagueSellCount"),
                       "review_count_display_text": rate.get("totalCount"),
                       "positive_review_rate_display_text": _field(rate, "favorableRate", "rateText")}
        signals = {key: _string(value) for key, value in raw_signals.items()}
        evidence["transaction_signals"] = {k: v for k, v in signals.items() if v} or None
        raw_reviews = []
        for section in _nodes(tree, "Comments--"):
            for card in _nodes(section, "Comment--"):
                for wrapper in _nodes(card, "contentWrapper--"):
                    for body in _nodes(wrapper, "content--"):
                        original = body.text()
                        text = original[:4096].strip()
                        review = {"text": text[:2000], "source_url": source_url} if text else None
                        if review and review not in reviews and len(reviews) < 20:
                            reviews.append(review)
                            raw_reviews.append({"text": original[:4096], "original_length": len(original),
                                                "retained_length": min(len(original), 4096), "truncated": len(original) > 4096,
                                                "normalized_limit": 2000, "source_url": source_url})
        # The observed shop container includes its name and contextual metrics.
        shop_metrics = []
        raw_shop_metrics = []
        for name in _nodes(tree, "shopName--"):
            container = name
            for _ in range(3):
                container = container.parent if container is not None else None
            if container is not None and _text(name) == _string(seller.get("shopName")):
                raw_shop_metrics = [n.text() for n in _nodes(container, "starNum--") + _nodes(container, "storeLabelItem--") if _text(n)]
                shop_metrics = [text.strip() for text in raw_shop_metrics]
                break
        if shop_metrics:
            evidence["transaction_signals"] = {**(evidence["transaction_signals"] or {}), "shop_metrics_display_text": shop_metrics}
            shipping = [text for text in shop_metrics if text and re.fullmatch(r"平均[0-9]+小时发货", text)]
            evidence["delivery_information"] = {"shop_shipping_display_text": shipping} if shipping else None
        evidence["reviews"] = reviews or None
        raw = {"item": {"itemId": item.get("itemId"), "title": item.get("title"), "vagueSellCount": item.get("vagueSellCount")},
               "ssrItemId": data.get("ssrItemId"), "prices": raw_prices, "starting_price_text": raw_starting,
               "rate": raw_signals, "reviews": raw_reviews, "shop_metrics_display_text": raw_shop_metrics,
               "dom_title": raw_dom_title}
    else:
        seller = _object(model.get("seller"))
        _shop_binding(seller, identity)
        raw_duration = seller.get("shopDuration")
        duration = _string(raw_duration)
        match = re.fullmatch(r"([0-9]{1,3})年老店", duration or "")
        evidence["years_active"] = int(match[1]) if match else None
        evaluates = seller.get("evaluates")
        if evaluates is not None and (not isinstance(evaluates, list) or not all(isinstance(v, dict) for v in evaluates)):
            raise MalformedPage
        raw_metrics = [{key: entry.get(key) for key in ("type", "title", "score", "levelText")}
                       for entry in evaluates or []]
        metrics = [{key: _string(value) for key, value in entry.items()} for entry in raw_metrics]
        metrics = [entry for entry in metrics if entry["title"] and entry["score"]]
        evidence["transaction_signals"] = {"shop_evaluations": metrics} if metrics else None
        products = []
        raw_products = []
        shelves = _nodes(tree, "shopProductShelfArea--")
        cards = [card for shelf in shelves for card in shelf.css(".shop-item-card")]
        for card in cards:
            for link in card.css("a[href]"):
                href = link.attributes["href"]
                try:
                    url = normalize_taobao_url("https:" + href if href.startswith("//") else href)
                    product_kind, product_id = taobao_identity(url)
                except ValueError:
                    continue
                if product_kind == "item" and all(p["offer_id"] != product_id for p in products):
                    title_node = next(iter(_nodes(card, "title--")), None)
                    raw_title = (title_node.attributes.get("title") or title_node.text()) if title_node else None
                    products.append({"offer_id": product_id, "title": _string(raw_title), "source_url": url})
                    raw_products.append({"offer_id": product_id, "title": raw_title, "source_url": url})
                    break
            if len(products) >= 20:
                break
        evidence["products"] = products or None
        raw = {"shopDuration": raw_duration, "evaluates": raw_metrics, "products": raw_products}
    evidence["supplier_name"] = _string(seller.get("shopName"))
    supplier_id = _id(seller.get("sellerId"))
    if not evidence["supplier_name"] and not evidence["products"]:
        raise MalformedPage
    raw["seller"] = {key: seller.get(key) for key in ("shopId", "sellerId", "shopName", "pcShopUrl", "sellerType", "tmall")}
    timestamp = (extracted_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    supplier_data = assemble_supplier_data(
        evidence, platform="TAOBAO", source_url=source_url,
        offer_id=identity if kind == "item" else None, platform_supplier_id=supplier_id,
        extracted_at=timestamp, extraction_method="PUBLIC_HTTP", analysis_mode=mode,
        extractor_version=EXTRACTOR_VERSION,
    )
    raw_payload = {"source_url": source_url, "captured_at": timestamp,
                   "html_sha256": sha256(page_bytes if page_bytes is not None else html.encode("utf-8")).hexdigest(),
                   "public_fields": raw}
    _validate_json_evidence(supplier_data)
    _validate_json_evidence(raw_payload)
    return dict(source_url=source_url, extraction_status=evidence_status(supplier_data),
                supplier_data=supplier_data, raw_payload=raw_payload, reviews=reviews)


def decode_taobao_html(content, mime_charsets=(), *, strict=False):
    """Only MIME and actual meta elements declare encoding; body text cannot."""
    declarations = list(mime_charsets)
    tree = _tree(content[:8192].decode("latin-1"))
    for meta in tree.css("meta"):
        if not _active(meta):
            continue
        charset = meta.attributes.get("charset")
        if charset:
            declarations.append(charset)
        elif meta.attributes.get("http-equiv", "").lower() == "content-type":
            match = re.search(r"charset\s*=\s*['\"]?([a-zA-Z0-9_-]+)", meta.attributes.get("content", ""), re.I)
            if match:
                declarations.append(match[1])
    aliases = {"utf-8": "utf-8-sig", "utf8": "utf-8-sig", "gbk": "gb18030", "gb2312": "gb18030", "gb18030": "gb18030"}
    encodings = set()
    for value in declarations:
        if not isinstance(value, str) or value.strip().lower() not in aliases:
            raise ValueError("Unsupported HTML encoding")
        encodings.add(aliases[value.strip().lower()])
    if len(encodings) > 1 or content.startswith(b"\xef\xbb\xbf") and "gb18030" in encodings:
        raise ValueError("Conflicting HTML encodings")
    encoding = next(iter(encodings), "utf-8-sig")
    # The audited GBK capture contains invalid legacy bytes. Preserve its
    # replacement decoding, while UTF-8 uploads must contain valid UTF-8.
    return content.decode(encoding, errors="strict" if strict and encoding == "utf-8-sig" else "replace")


def _decode(content, response):
    from email.message import Message
    media = Message()
    media["content-type"] = response.headers.get("content-type", "")
    charsets = [value for name, value in (media.get_params() or [])[1:] if name.lower() == "charset"]
    try:
        return decode_taobao_html(content, charsets)
    except ValueError as exc:
        raise UnicodeError("Unsupported HTML encoding") from exc


def _login_destination(url):
    parsed = urlsplit(url)
    return parsed.scheme == "https" and parsed.netloc == "login.taobao.com" and parsed.path == "/member/login.jhtml" and not parsed.fragment


def extract_taobao(source_url, *, analysis_mode="ACCOUNT_PUBLIC", client=None, dns_check=_public_dns,
                   clock=time.monotonic, sleep=time.sleep, browser_fallback=False, browser_renderer=None):
    try:
        canonical = normalize_taobao_url(source_url)
        kind, identity = taobao_identity(canonical)
    except ValueError:
        return dict(source_url=source_url, extraction_status="UNSUPPORTED_PAGE", reason="INVALID_URL")
    hosts = ("item.taobao.com",) if kind == "item" else (f"shop{identity}.taobao.com", f"shop{identity}.world.taobao.com")
    return bounded_extract(source_url, normalize=normalize_taobao_url, identity=taobao_identity,
                           parse=parse_taobao_page, classify_access=lambda html: _access(html, source_url=canonical), login_destination=_login_destination,
                           allowed_hosts=hosts, decode=_decode, mismatch_reason="SOURCE_MISMATCH",
                           analysis_mode=analysis_mode, client=client, dns_check=dns_check, clock=clock, sleep=sleep,
                           accept_cookies=False, browser_fallback=browser_fallback, browser_renderer=browser_renderer)
