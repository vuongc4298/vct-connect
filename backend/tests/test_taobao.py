from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

os.environ.setdefault("DEVELOPER_MODE", "true")
os.environ.setdefault("DATABASE_URL", "postgresql://unused")

from backend.app.extraction.taobao import extract_taobao, parse_taobao_page, _model
from backend.app.extraction.renormalize import UnsupportedRawEvidence, renormalize_public_fields
from backend.app.extraction.contracts import EVIDENCE_FIELDS
from backend.app.extraction.urls import normalize_taobao_url, source_platform, taobao_identity
from backend.app.extraction.fetch import MAX_HTML_BYTES, PublicOnlyBackend, UnsafeDestination
from backend.app.main import Submission
from backend.worker.main import _compute_claim
from selectolax.parser import HTMLParser

ITEM = "https://item.taobao.com/item.htm?id=1076425861755"
SHOP = "https://shop159450000.world.taobao.com/category.htm"
AT = datetime(2026, 9, 30, tzinfo=timezone.utc)


def capture(shop=False):
    name = "taobao_shop_159450000.html" if shop else "taobao_item_1076425861755.html"
    return (Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("shop", [False, True])
def test_saved_taobao_shapes_replay_from_selected_fields(shop):
    url = SHOP if shop else ITEM
    original = parse_taobao_page(capture(shop), url, extracted_at=AT)
    data = original["supplier_data"]
    replay = renormalize_public_fields(raw_payload=original["raw_payload"], source_url=url,
        extraction_method="PUBLIC_HTTP", analysis_mode="ACCOUNT_PUBLIC", extracted_at=data["extracted_at"],
        source_snapshot_id=uuid4(), source_extractor_version=data["extractor_version"])
    assert replay["supplier_data"]["extractor_version"] == "taobao-raw.v2"
    assert replay["supplier_data"]["missing_fields"] == data["missing_fields"]
    assert replay["reviews"] == original["reviews"]
    assert {key: replay["supplier_data"][key] for key in EVIDENCE_FIELDS} == {
        key: data[key] for key in EVIDENCE_FIELDS
    }
    original["raw_payload"]["public_fields"]["seller"]["shopId"] = "1" if shop else "159450000"
    if shop:
        with pytest.raises(UnsupportedRawEvidence):
            renormalize_public_fields(raw_payload=original["raw_payload"], source_url=url,
                extraction_method="PUBLIC_HTTP", analysis_mode="ACCOUNT_PUBLIC", extracted_at=data["extracted_at"],
                source_snapshot_id=uuid4(), source_extractor_version=data["extractor_version"])


def test_taobao_more_than_twenty_reviews_are_stable_and_scoped():
    card = '<div class="Comment--H5QmJwe9"><div class="contentWrapper--cSa5gEtn"><div class="content--uonoOhaz">Review {}</div></div></div>'
    html = capture().replace('<div class="Comments--eCO6Uz4o">',
                             '<div class="Comments--eCO6Uz4o">' + ''.join(card.format(i) for i in range(25)))
    result = parse_taobao_page(html, ITEM, extracted_at=AT)
    assert result["extraction_status"] == "PARTIAL"
    assert len(result["reviews"]) == 20
    assert len(result["raw_payload"]["public_fields"]["reviews"]) == 20
    assert len({item["text"] for item in result["reviews"]}) == 20
    assert result["supplier_data"]["completeness"] == 0.5


def model_page(model, shop=False):
    script = "window.g_config = " + json.dumps(model) + ";" if shop else (
        "!(function () {var a = window.__ICE_APP_CONTEXT__ || {};var b = " + json.dumps(model)
        + ";for (var k in a) {b[k] = a[k]}window.__ICE_APP_CONTEXT__=b;})();")
    return "<script>" + script + "</script>"


@pytest.mark.parametrize("url", [ITEM, ITEM + "&spm=track&skuId=123", SHOP, SHOP + "?spm=track",
    "https://shop159450000.taobao.com/", "https://shop159450000.taobao.com/index.htm"])
def test_audited_forms_are_admitted_and_canonical(url):
    assert Submission(source_url=url).source_url == normalize_taobao_url(url)
    assert source_platform(url) == "TAOBAO"


@pytest.mark.parametrize("url", [
    ITEM + "&id=1076425861755", ITEM + "&id=1", ITEM + "#frag", ITEM.replace("https", "http"),
    ITEM.replace("item.taobao.com", "item.taobao.com:443"), ITEM.replace("item.taobao.com", "user@item.taobao.com"),
    ITEM.replace("1076425861755", ""), ITEM.replace("1076425861755", "-1"), ITEM.replace("1076425861755", "1e12"),
    "https://item.taobao.com/item.htm?itemId=1076425861755", "https://taobao.com/item.htm?id=1076425861755",
    "https://detail.tmall.com/item.htm?id=1076425861755", "https://e.tb.cn/test", "https://foo.taobao.com/",
    "https://shop159450000.world.taobao.com/other.htm", "https://shop159450000.taobao.com:443/",
    "https://shop159450000.taobao.com.evil.test/", "https://shop0.taobao.com/", " " + ITEM,
    ITEM.replace("item.taobao.com", "item.taobao.com\n"),
])
def test_unsafe_or_ambiguous_forms_are_rejected(url):
    with pytest.raises(ValueError):
        normalize_taobao_url(url)


@pytest.mark.parametrize("shop,coverage", [(False, 0.5), (True, 0.3333)])
def test_audited_snapshots_have_bound_public_evidence(shop, coverage):
    html = capture(shop)
    result = parse_taobao_page(html, SHOP if shop else ITEM, extracted_at=AT)
    data = result["supplier_data"]
    assert result["extraction_status"] == "PARTIAL"
    assert data["platform"] == "TAOBAO" and data["platform_supplier_id"] == "2895982467"
    assert data["supplier_name"] == "心相印维达生活馆"
    assert data["extracted_at"] == AT.isoformat() and data["extractor_version"] == "taobao-http.v1"
    assert data["completeness"] == coverage and len(data["completeness_denominator"]) == 12
    assert data["company_information"] is None and data["rating"] is None
    assert result["raw_payload"]["html_sha256"] == sha256(html.encode()).hexdigest()
    raw = json.dumps(result, ensure_ascii=False)
    for forbidden in ["userName", "headPic", "userFlag", "cookie", "session", "cart", "feedId"]:
        assert forbidden not in raw
    if shop:
        assert data["years_active"] == 10 and len(data["products"]) == 20
        assert data["reviews"] is None
        assert [x["score"] for x in data["transaction_signals"]["shop_evaluations"]] == ["4.8", "4.9", "4.9"]
    else:
        assert data["price_information"]["price"]["priceText"] == "3.35"
        assert data["price_information"]["extraPrice"]["priceText"] == "2.01"
        assert data["price_information"]["starting_price_text"] == "2.01起"
        assert data["transaction_signals"]["review_count_display_text"] == "2万+"
        assert data["transaction_signals"]["sales_display_text"] == "3万+"
        assert len(result["reviews"]) == 2


@pytest.mark.parametrize("shop", [False, True])
def test_model_and_page_identity_must_match(shop):
    html = capture(shop).replace("159450000" if shop else "1076425861755", "123456789")
    assert parse_taobao_page(html, SHOP if shop else ITEM)["extraction_status"] == "PARSE_FAILED"


def test_missing_fields_remain_unknown_and_reviews_are_scoped():
    model = _model(HTMLParser(capture()), "item")
    res = model["loaderData"]["home"]["data"]["res"]
    res.pop("componentsVO"); res.pop("skuCore")
    result = parse_taobao_page(model_page(model) + '<div class="content--fake">unrelated</div>', ITEM)
    data = result["supplier_data"]
    assert data["price_information"] is None and data["reviews"] is None and result["reviews"] == []
    assert data["completeness"] == 0.25  # supplier, product, displayed sales


@pytest.mark.parametrize("path,value", [("ssrItemId", None), ("item", []), ("item", {"itemId": "123"}),
    ("seller", {"shopId": "159450000", "sellerType": "B"}),
    ("seller", {"shopId": "159450000", "pcShopUrl": "//shop1.taobao.com"})])
def test_malformed_or_conflicting_models_have_no_snapshot(path, value):
    model = _model(HTMLParser(capture()), "item")
    data = model["loaderData"]["home"]["data"]
    if path == "ssrItemId":
        data[path] = value; data["res"]["item"].pop("itemId")
    else:
        data["res"][path] = value
    result = parse_taobao_page(model_page(model), ITEM)
    assert result["extraction_status"] == "PARSE_FAILED" and "supplier_data" not in result


@pytest.mark.parametrize("value", [float("nan"), "\x00", "\ud800", []])
def test_invalid_source_values_cannot_reach_jsonb(value):
    model = _model(HTMLParser(capture()), "item")
    model["loaderData"]["home"]["data"]["res"]["item"]["title"] = value
    assert parse_taobao_page(model_page(model), ITEM)["extraction_status"] == "PARSE_FAILED"


@pytest.mark.parametrize("html,status", [("<title>Login required</title>", "AUTH_REQUIRED"),
    ("<title>Captcha</title>", "BLOCKED"),
    ('<script>window.location.href="/_____tmd_____/punish";</script>', "BLOCKED"),
    ('<body><script>window._config_={};document.cookie="";var jump="%2F_____tmd_____%2Fpage%2Flogin_jump";window.location.href=jump;</script></body>', "BLOCKED"),
    ("<html></html>", "PARSE_FAILED"),
    ('<script>window.__ICE_APP_CONTEXT__= {"itemId":"1076425861755"};</script>', "PARSE_FAILED")])
def test_barriers_and_unbound_evidence_are_terminal(html, status):
    result = parse_taobao_page(html, ITEM)
    assert result["extraction_status"] == status and "supplier_data" not in result


def test_marker_and_navigation_prompt_do_not_hide_populated_page():
    html = capture().replace("<body>", '<body><nav>请登录</nav>') + '<script>var marker="_____tmd_____";</script>'
    assert parse_taobao_page(html, ITEM)["extraction_status"] == "PARTIAL"


def test_absent_seller_identifiers_and_changed_dom_keep_explicit_unknowns():
    model = _model(HTMLParser(capture()), "item")
    model["loaderData"]["home"]["data"]["res"]["seller"] = {"shopName": "Shop"}
    result = parse_taobao_page('<span class="shopName--changed">Shop</span>' + model_page(model), ITEM)
    assert result["extraction_status"] == "PARTIAL"
    assert result["supplier_data"]["platform_supplier_id"] is None
    assert result["supplier_data"]["delivery_information"] is None


@pytest.mark.parametrize("location,status,reason", [
    ("https://shop159450000.taobao.com/index.htm", "PARTIAL", None),
    ("https://shop1.taobao.com/", "BLOCKED", "SOURCE_MISMATCH"),
    (ITEM, "BLOCKED", "SOURCE_MISMATCH"),
    ("https://login.taobao.com/member/login.jhtml?redirect=1", "AUTH_REQUIRED", "LOGIN_REQUIRED"),
    ("https://login.taobao.com:443/member/login.jhtml", "BLOCKED", "UNSAFE_REDIRECT"),
    ("https://foo.taobao.com/", "BLOCKED", "UNSAFE_REDIRECT"),
    (SHOP, "BLOCKED", "REDIRECT_LOOP"),
])
def test_redirects_follow_only_same_audited_identity(location, status, reason):
    calls = []
    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(302, headers={"location": location}) if len(calls) == 1 else httpx.Response(200, headers={"content-type": "text/html"}, text=capture(True))
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = extract_taobao(SHOP, client=client, dns_check=lambda _: True)
    assert result["extraction_status"] == status
    if reason:
        assert result["reason"] == reason and len(calls) == 1


@pytest.mark.parametrize("response,status", [(httpx.Response(403), "BLOCKED"), (httpx.Response(401), "AUTH_REQUIRED"),
    (httpx.Response(404), "UNSUPPORTED_PAGE"), (httpx.Response(200, text="not html"), "PARSE_FAILED"),
    (httpx.Response(200, headers={"content-type": "text/html"}, content=b"x" * (MAX_HTML_BYTES + 1)), "PARSE_FAILED")])
def test_terminal_fetch_failures_are_not_retried(response, status):
    calls = []
    with httpx.Client(transport=httpx.MockTransport(lambda r: calls.append(r) or response)) as client:
        result = extract_taobao(ITEM, client=client, dns_check=lambda _: True)
    assert result["extraction_status"] == status and len(calls) == 1


def test_transient_retry_recovers_and_original_gbk_bytes_are_hashed():
    calls, delays = [], []
    body = capture(True).replace('charset="utf-8"', 'charset="GBK"').encode("gb18030")
    def respond(request):
        calls.append(request)
        return httpx.Response(503) if len(calls) < 3 else httpx.Response(200, headers={"content-type": "text/html"}, content=body)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = extract_taobao(SHOP, client=client, dns_check=lambda _: True, sleep=delays.append, analysis_mode="GUEST_PUBLIC")
    assert len(calls) == 3 and delays == [0.5, 1.0]
    assert result["supplier_data"]["analysis_mode"] == "GUEST_PUBLIC"
    assert result["supplier_data"]["supplier_name"] == "心相印维达生活馆"
    assert result["raw_payload"]["html_sha256"] == sha256(body).hexdigest()


def test_transport_rejects_hosts_outside_identity_before_resolving():
    with pytest.raises(UnsafeDestination):
        PublicOnlyBackend(allowed_hosts=("item.taobao.com",)).connect_tcp("shop159450000.taobao.com", 443)


def test_worker_dispatch_preserves_guest_mode(monkeypatch):
    seen = []
    monkeypatch.setattr("backend.worker.main.extract_taobao", lambda url, **kw: seen.append((url, kw)) or {})
    assert _compute_claim({"source_url": ITEM, "mode": "GUEST_PUBLIC"}, None) == {}
    assert seen == [(ITEM, {"analysis_mode": "GUEST_PUBLIC"})]


@pytest.mark.parametrize("prefix,suffix", [("/*", "*/"), ("//", ""), ("'", "'"), ('"', '"'), ("var text = '", "';")])
def test_commented_or_quoted_shop_assignments_are_not_models(prefix, suffix):
    model = _model(HTMLParser(capture(True)), "shop")
    assignment = "window.g_config = " + json.dumps(model) + ";"
    result = parse_taobao_page("<script>" + prefix + assignment + suffix + "</script>", SHOP)
    assert result["extraction_status"] == "PARSE_FAILED"
    assert "supplier_data" not in result


def test_challenge_words_inside_bound_useful_evidence_are_not_access_walls():
    model = _model(HTMLParser(capture()), "item")
    model["loaderData"]["home"]["data"]["res"]["item"]["title"] = "Captcha security verification accessory"
    html = model_page(model) + '<body><div class="Comments--test"><div class="Comment--test"><div class="contentWrapper--test"><div class="content--test">Access denied 请登录 滑动验证</div></div></div></div></body>'
    result = parse_taobao_page(html, ITEM)
    assert result["extraction_status"] == "PARTIAL"
    assert result["reviews"][0]["text"] == "Access denied 请登录 滑动验证"


@pytest.mark.parametrize("script", ['var ancillary = {"seller": {}};', 'var ssrItemId = "1076425861755";', 'window.g_config = {"seller": {}};'])
@pytest.mark.parametrize("body,status", [("请登录后查看 Please sign in", "AUTH_REQUIRED"), ("Security verification 请输入验证码", "BLOCKED")])
def test_ancillary_script_markers_do_not_hide_real_access_walls(script, body, status):
    result = parse_taobao_page("<body>" + body + "<script>" + script + "</script></body>", ITEM)
    assert result["extraction_status"] == status and "supplier_data" not in result


def test_conflicting_ssr_item_id_is_rejected_independently():
    model = _model(HTMLParser(capture()), "item")
    data = model["loaderData"]["home"]["data"]
    assert data["res"]["item"]["itemId"] == "1076425861755"
    data["ssrItemId"] = "123456789"
    result = parse_taobao_page(model_page(model), ITEM)
    assert result["extraction_status"] == "PARSE_FAILED" and "supplier_data" not in result


def test_shop_products_are_scoped_and_keep_observed_titles_and_canonical_links():
    html = capture(True).replace('<body>', '<body><a class="shop-item-card" href="https://item.taobao.com/item.htm?id=123456"><div class="title--other" title="Unrelated item">Unrelated item</div></a>')
    result = parse_taobao_page(html, SHOP)
    products = result["supplier_data"]["products"]
    assert len(products) == 20 and all(product["title"] for product in products)
    assert products[0]["title"].startswith("洁柔")
    assert all(product["source_url"] == ITEM if product["offer_id"] == "1076425861755" else product["source_url"] == "https://item.taobao.com/item.htm?id=" + product["offer_id"] for product in products)
    assert "Unrelated item" not in json.dumps(result)
    # With the shelf absent, global cards cannot count as product evidence.
    unscoped = capture(True).replace("shopProductShelfArea--Z6GzvxkU", "otherArea--test")
    result = parse_taobao_page(unscoped, SHOP)
    assert result["supplier_data"]["products"] is None
    assert "products" in result["supplier_data"]["missing_fields"]


@pytest.mark.parametrize("entries", [[{}], [{"title": " ", "score": "4.9"}], [{"title": "描述相符"}], [{"type": "desc", "levelText": "高于36.33%"}]])
def test_empty_or_unlabeled_evaluations_do_not_inflate_coverage(entries):
    model = _model(HTMLParser(capture(True)), "shop")
    model["seller"]["evaluates"] = entries
    result = parse_taobao_page(model_page(model, True), SHOP)
    assert result["supplier_data"]["transaction_signals"] is None
    assert "transaction_signals" in result["supplier_data"]["missing_fields"]


def test_selected_product_raw_values_preserve_whitespace_separately_from_normalization():
    model = _model(HTMLParser(capture()), "item")
    res = model["loaderData"]["home"]["data"]["res"]
    price = res["componentsVO"]["priceVO"]["price"]
    price.update(priceText=" 3.35 ", priceTitle=" 优惠前 ")
    res["skuCore"]["sku2info"]["0"]["subPrice"]["priceText"] = " 2.01起 "
    res["componentsVO"]["rateVO"]["totalCount"] = " 2万+ "
    res["componentsVO"]["rateVO"]["favorableRate"]["rateText"] = " 近3个月好评率高达100.0% "
    result = parse_taobao_page(model_page(model), ITEM)
    raw = result["raw_payload"]["public_fields"]
    normalized = result["supplier_data"]
    assert raw["prices"]["price"]["priceText"] == " 3.35 "
    assert raw["prices"]["price"]["priceTitle"] == " 优惠前 "
    assert raw["starting_price_text"] == " 2.01起 "
    assert raw["rate"]["review_count_display_text"] == " 2万+ "
    assert raw["rate"]["positive_review_rate_display_text"] == " 近3个月好评率高达100.0% "
    assert normalized["price_information"]["price"]["priceText"] == "3.35"
    assert normalized["transaction_signals"]["review_count_display_text"] == "2万+"


def test_selected_shop_raw_values_preserve_whitespace_and_untransformed_duration():
    model = _model(HTMLParser(capture(True)), "shop")
    model["seller"]["shopDuration"] = " 10年老店 "
    model["seller"]["evaluates"][0].update(title=" 描述相符 ", score=" 4.8 ", levelText=" 高于36.33% ")
    result = parse_taobao_page(model_page(model, True), SHOP)
    raw = result["raw_payload"]["public_fields"]
    assert raw["shopDuration"] == " 10年老店 "
    assert raw["evaluates"][0]["score"] == " 4.8 "
    assert raw["evaluates"][0]["title"] == " 描述相符 "
    assert result["supplier_data"]["years_active"] == 10
    assert result["supplier_data"]["transaction_signals"]["shop_evaluations"][0]["score"] == "4.8"


@pytest.mark.parametrize("shop", [False, True])
def test_injected_private_model_and_reviewer_state_never_survives(shop):
    model = _model(HTMLParser(capture(shop)), "shop" if shop else "item")
    private = {"user": "PRIVATE_USER_SENTINEL", "sessionToken": "PRIVATE_SESSION_SENTINEL", "cart": "PRIVATE_CART_SENTINEL"}
    model.update(private)
    seller = model["seller"] if shop else model["loaderData"]["home"]["data"]["res"]["seller"]
    seller.update(private)
    if shop:
        seller["evaluates"][0].update(private)
    else:
        res = model["loaderData"]["home"]["data"]["res"]
        res["item"].update(private)
        res["componentsVO"]["priceVO"]["price"].update(private)
        res["componentsVO"]["rateVO"].update(private)
        res["componentsVO"]["rateVO"]["favorableRate"].update(private)
    html = model_page(model, shop) + '<div class="Comments--test"><div class="Comment--test"><div class="header--test"><span>PRIVATE_REVIEWER_SENTINEL</span></div><div class="contentWrapper--test"><div class="content--test">Public review body</div></div></div></div>'
    result = parse_taobao_page(html, SHOP if shop else ITEM)
    assert result["extraction_status"] == "PARTIAL"
    serialized = json.dumps(result)
    for sentinel in [*private.values(), "PRIVATE_REVIEWER_SENTINEL"]:
        assert sentinel not in serialized
    if not shop:
        assert result["reviews"] == [{"text": "Public review body", "source_url": ITEM}]


@pytest.mark.parametrize("shop", [False, True])
@pytest.mark.parametrize("opening,closing", [
    ('<script type="text/plain">', '</script>'), ('<script src="external.js">', '</script>'),
    ('<script src="">', '</script>'), ('<template><script>', '</script></template>'),
    ('<noscript><script>', '</script></noscript>'),
])
def test_inactive_assignments_cannot_supply_evidence(shop, opening, closing):
    model = _model(HTMLParser(capture(shop)), "shop" if shop else "item")
    html = model_page(model, shop).replace("<script>", opening).replace("</script>", closing)
    assert parse_taobao_page(html, SHOP if shop else ITEM)["extraction_status"] == "PARSE_FAILED"


@pytest.mark.parametrize("assignment", [
    'window.__ICE_APP_CONTEXT__ = {"loaderData": {"other": "item"}};',
    'window["__ICE_APP_CONTEXT__"] = {"loaderData": {}};',
    'window.__ICE_APP_CONTEXT__.loaderData = {};',
    'window.__ICE_APP_CONTEXT__ ||= {"loaderData": {}};',
    'Object.assign(window.__ICE_APP_CONTEXT__, {"loaderData": {}});',
])
def test_earlier_context_override_is_rejected(assignment):
    result = parse_taobao_page("<script>" + assignment + "</script>" + capture(), ITEM)
    assert result["extraction_status"] == "PARSE_FAILED" and "supplier_data" not in result


def test_bound_evidence_survives_login_title_and_real_waiting_challenge_is_blocked():
    assert parse_taobao_page(capture().replace("<head>", "<head><title>Please sign in</title>"), ITEM)["extraction_status"] == "PARTIAL"
    html = '<body>Please wait<script>window._config_={};document.cookie="challenge";location="login_jump/_____tmd_____";</script></body>'
    result = parse_taobao_page(html, ITEM)
    assert result["extraction_status"] == "BLOCKED" and "supplier_data" not in result


def test_title_fallback_is_scoped_and_ambiguous_titles_are_rejected():
    model = _model(HTMLParser(capture()), "item")
    del model["loaderData"]["home"]["data"]["res"]["item"]["title"]
    main = '<div class="MainTitle--test"><span class="mainTitle--test">  Audited title  </span></div>'
    assert parse_taobao_page(model_page(model) + main, ITEM)["supplier_data"]["products"] is None
    scoped = '<div class="ItemTitle--test">' + main + '</div>'
    assert parse_taobao_page(model_page(model) + scoped, ITEM)["supplier_data"]["products"][0]["title"] == "Audited title"
    assert parse_taobao_page(model_page(model) + scoped + scoped, ITEM)["extraction_status"] == "PARSE_FAILED"


@pytest.mark.parametrize("opening,closing", [('<template>', '</template>'), ('<noscript>', '</noscript>'),
    ('<div hidden>', '</div>'), ('<div style="display: none">', '</div>'), ('<div aria-hidden="true">', '</div>')])
def test_inactive_reviews_and_metrics_are_not_retained(opening, closing):
    extra = '<div class="Comments--test"><div class="Comment--test"><div class="contentWrapper--test"><div class="content--test">INACTIVE_REVIEW</div></div></div></div>'
    result = parse_taobao_page(capture().replace("<body>", "<body>" + opening + extra + closing), ITEM)
    assert len(result["reviews"]) == 2 and "INACTIVE_REVIEW" not in json.dumps(result)


def test_raw_review_extent_and_dom_metrics_preserve_original_selected_text():
    original = "  " + "x" * 4500 + "  "
    html = capture().replace("质量特别好，一直都用的这款抽纸", original).replace("平均23小时发货", "  平均23小时发货  ")
    result = parse_taobao_page(html, ITEM)
    raw = result["raw_payload"]["public_fields"]
    review = raw["reviews"][0]
    assert review["text"] == original[:4096] and review["original_length"] == len(original)
    assert review["truncated"] and review["retained_length"] == 4096
    assert result["reviews"][0]["text"] == review["text"].strip()[:2000]
    assert "  平均23小时发货  " in raw["shop_metrics_display_text"]
    assert "平均23小时发货" in result["supplier_data"]["transaction_signals"]["shop_metrics_display_text"]


def test_hidden_and_script_descendants_are_excluded_from_selected_review_text():
    html = capture().replace("质量特别好，一直都用的这款抽纸", 'Public body<span hidden>PRIVATE_HIDDEN_SENTINEL</span><script>var token="PRIVATE_SCRIPT_SENTINEL"</script>')
    result = parse_taobao_page(html, ITEM)
    assert result["reviews"][0]["text"] == "Public body"
    assert "PRIVATE_" not in json.dumps(result)


def test_empty_shop_dom_metrics_do_not_inflate_coverage():
    model = _model(HTMLParser(capture()), "item")
    res = model["loaderData"]["home"]["data"]["res"]
    res["item"].pop("vagueSellCount")
    res["componentsVO"].pop("rateVO")
    html = model_page(model) + '<div><div><div><span class="shopName--test">心相印维达生活馆</span></div></div><span class="starNum--test"> </span></div>'
    result = parse_taobao_page(html, ITEM)
    assert result["supplier_data"]["transaction_signals"] is None


@pytest.mark.parametrize("shop", [False, True])
def test_embedded_pathless_tracked_shop_url_keeps_shop_binding(shop):
    html = capture(shop).replace('//shop159450000.taobao.com', '//shop159450000.taobao.com?spm=track')
    assert parse_taobao_page(html, SHOP if shop else ITEM)["extraction_status"] == "PARTIAL"


@pytest.mark.parametrize("hint", [ITEM.replace("1076425861755", "1"), SHOP, "https://evil.example/", ITEM + "&id=1"])
def test_imported_canonical_hint_cannot_reassign_identity(hint):
    result = parse_taobao_page(capture().replace("<head>", '<head><link rel="canonical" href="' + hint + '">'), ITEM)
    assert result["extraction_status"] == "PARSE_FAILED" and "supplier_data" not in result


def test_body_charset_text_is_not_an_encoding_declaration():
    from backend.app.extraction.taobao import _decode
    body = capture().replace("<body>", "<body>ordinary charset=ascii")
    assert _decode(body.encode(), httpx.Response(200)) == body


@pytest.mark.parametrize("shop", [False, True])
def test_bound_transient_html_retries_instead_of_becoming_access_failure(shop):
    body = capture(shop).replace("<head>", "<head><title>Captcha Please sign in</title>")
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(503 if len(calls) == 1 else 200, headers={"content-type": "text/html"}, text=body)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = extract_taobao(SHOP if shop else ITEM, client=client, dns_check=lambda _: True, sleep=lambda _: None)
    assert len(calls) == 2 and result["extraction_status"] == "PARTIAL"


@pytest.mark.parametrize("shop", [False, True])
def test_default_taobao_transport_pins_public_ip_and_preserves_tls_host(monkeypatch, shop):
    import socket
    import httpcore
    body = capture(shop).encode()
    calls = []
    class Socket:
        response = b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: " + str(len(body)).encode() + b"\r\nConnection: close\r\n\r\n" + body
        def read(self, maximum, timeout=None):
            data, self.response = self.response[:maximum], self.response[maximum:]
            return data
        def write(self, data, timeout=None):
            calls.append(("request", data))
        def start_tls(self, context, server_hostname=None, timeout=None):
            calls.append(("tls", server_hostname))
            return self
        def get_extra_info(self, info):
            return None
        def close(self):
            pass
    def connect(_self, host, port, *_args, **_kwargs):
        calls.append(("connect", host, port))
        return Socket()
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))])
    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", connect)
    source = SHOP if shop else ITEM
    result = extract_taobao(source)
    assert result["extraction_status"] == "PARTIAL"
    assert ("connect", "93.184.216.34", 443) in calls
    assert ("tls", "shop159450000.world.taobao.com" if shop else "item.taobao.com") in calls


@pytest.mark.parametrize("example", [
    'const example = "window.__ICE_APP_CONTEXT__ = {}";',
    "const example = 'window[\"__ICE_APP_CONTEXT__\"] = {}';",
    'const example = `Object.assign(window.__ICE_APP_CONTEXT__, {});`;',
    '// window.__ICE_APP_CONTEXT__ = {};\nconst harmless = 1;',
    '/* window["__ICE_APP_CONTEXT__"] = {}; Object.assign(window.__ICE_APP_CONTEXT__, {}); */',
])
def test_nonexecutable_context_write_examples_do_not_reject_bound_pages(example):
    assert parse_taobao_page('<script>' + example + '</script>' + capture(), ITEM)["extraction_status"] == "PARTIAL"


@pytest.mark.parametrize("write", [
    'window.__ICE_APP_CONTEXT__ = {loaderData:{}};',
    'window["__ICE_APP_CONTEXT__"] = {loaderData:{}};',
    'Object.assign(window.__ICE_APP_CONTEXT__, {loaderData:{}});',
    'const value = `${window.__ICE_APP_CONTEXT__ = {loaderData:{}}}`;',
])
def test_executable_context_writes_still_reject_bound_pages(write):
    assert parse_taobao_page('<script>' + write + '</script>' + capture(), ITEM)["extraction_status"] == "PARSE_FAILED"


@pytest.mark.parametrize("opening,closing", [
    ('<script hidden>', '</script>'), ('<div hidden><script>', '</script></div>'),
    ('<script style="display:none">', '</script>'), ('<script aria-hidden="true">', '</script>'),
])
def test_hidden_inline_context_writes_are_executable_and_rejected(opening, closing):
    html = opening + 'window.__ICE_APP_CONTEXT__ = {loaderData:{}};' + closing + capture()
    assert parse_taobao_page(html, ITEM)["extraction_status"] == "PARSE_FAILED"


@pytest.mark.parametrize("style", ["opacity:0", "opacity: 0.0 !important", "visibility:collapse"])
def test_invisible_descendants_do_not_survive_selected_raw_review_text(style):
    html = capture().replace("质量特别好，一直都用的这款抽纸", 'Public review<span style="' + style + '">PRIVATE_INVISIBLE</span>')
    result = parse_taobao_page(html, ITEM)
    assert result["reviews"][0]["text"] == "Public review"
    assert result["raw_payload"]["public_fields"]["reviews"][0]["text"] == "Public review"
    assert "PRIVATE_INVISIBLE" not in json.dumps(result)


@pytest.mark.parametrize("attribute", ['hidden', 'aria-hidden="true"', 'style="display:none"', 'style="visibility:collapse"', 'style="opacity:0"'])
@pytest.mark.parametrize("marker", ["captcha", "Please sign in"])
def test_sparse_pages_are_not_access_walls_due_to_hidden_text(attribute, marker):
    result = parse_taobao_page('<body>Unavailable<span ' + attribute + '>' + marker + '</span></body>', ITEM)
    assert result["extraction_status"] == "PARSE_FAILED"


def test_hidden_executable_structured_challenge_is_still_classified():
    html = '<body>Waiting<script hidden>window._config_={};document.cookie="challenge";location="login_jump/_____tmd_____";</script></body>'
    assert parse_taobao_page(html, ITEM)["extraction_status"] == "BLOCKED"


def test_hidden_canonical_metadata_still_binds_imported_identity():
    html = capture().replace("<head>", '<head><link hidden rel="canonical" href="https://item.taobao.com/item.htm?id=1">')
    assert parse_taobao_page(html, ITEM)["extraction_status"] == "PARSE_FAILED"
