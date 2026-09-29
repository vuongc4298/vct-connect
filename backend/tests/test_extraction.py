from datetime import datetime, timezone
from pathlib import Path
import socket

import httpcore
import httpx
import pytest

from backend.app.extraction import extract_1688, normalize_1688_url, parse_1688_page
from backend.app.extraction.offer1688 import PublicOnlyBackend, UnsafeDestination


URL = "https://detail.1688.com/offer/996518024136.html"
AT = datetime(2026, 9, 29, tzinfo=timezone.utc)


def test_supplied_1688_capture_yields_auditable_supplier_data():
    capture = Path(__file__).parent / "fixtures" / "1688_offer_996518024136.html"
    result = parse_1688_page(capture.read_text(encoding="utf-8"), URL, extracted_at=AT)
    assert result["extraction_status"] == "PARTIAL"
    data = result["supplier_data"]
    assert data["contract_version"] == "supplierdata.v1"
    assert data["platform"] == "1688" and data["source_url"] == URL
    assert data["extraction_method"] == "PUBLIC_HTTP" and data["analysis_mode"] == "ACCOUNT_PUBLIC"
    assert data["extractor_version"] and data["extracted_at"] == AT.isoformat()
    assert data["supplier_name"] == "广州衣秀缘服饰商行(个人独资)"
    assert data["transaction_signals"]["review_count"] == 267
    assert data["products"][0]["title"].startswith("Women's Autumn and Winter")
    assert data["price_information"]["minimum"] == "37.00"
    assert data["price_information"]["maximum"] == "39.00"
    assert data["price_information"]["minimum_order_quantity"] == 1
    assert "reviews" in data["missing_fields"] and data["reviews"] is None
    assert "delivery_information" in data["missing_fields"]
    assert "years_active" in data["missing_fields"]
    assert data["completeness"] == round(
        (len(data["completeness_denominator"]) - len(data["missing_fields"]))
        / len(data["completeness_denominator"]), 4)
    assert result["reviews"] == []
    assert len(result["raw_payload"]["html_sha256"]) == 64
    assert result["raw_payload"]["public_fields"]["rate_info"]["goodsGrade"] == 4.9


def test_sparse_offer_preserves_missing_fields_without_risk_claim():
    html = '<html><head><link rel="canonical" href="' + URL + '"></head><body>' \
           '<div class="title-content"><h1>Dress</h1></div></body></html>'
    result = parse_1688_page(html, URL, extracted_at=AT)
    assert result["extraction_status"] == "PARTIAL"
    data = result["supplier_data"]
    assert data["products"] == [{"offer_id": "996518024136", "title": "Dress"}]
    assert data["supplier_name"] is None
    assert "supplier_name" in data["missing_fields"]
    assert data["completeness"] < 1
    assert "risk" not in result and "risk" not in data


def test_accessible_review_text_is_preserved():
    html = '<html><head><link rel="canonical" href="' + URL + '"></head><body>' \
           '<div class="title-content"><h1>Dress</h1></div>' \
           '<div class="review-item">Good fabric</div></body></html>'
    result = parse_1688_page(html, URL, extracted_at=AT)
    assert result["reviews"] == [{"text": "Good fabric", "source_url": URL}]
    assert result["supplier_data"]["reviews"] == result["reviews"]
    assert "reviews" not in result["supplier_data"]["missing_fields"]


@pytest.mark.parametrize("value", [
    "http://detail.1688.com/offer/996518024136.html",
    "https://detail.1688.com.evil.test/offer/996518024136.html",
    "https://127.0.0.1/offer/996518024136.html",
    "https://detail.1688.com:444/offer/996518024136.html",
    "https://detail.1688.com@127.0.0.1/offer/996518024136.html",
    "https://detail.1688.com/login",
])
def test_unsafe_offer_url_is_rejected(value):
    with pytest.raises(ValueError):
        normalize_1688_url(value)


def test_tracking_query_is_dropped_before_fetch():
    assert normalize_1688_url(URL + "?spm=tracking") == URL


def test_off_platform_redirect_stops_before_second_request():
    requests = []

    def respond(request):
        requests.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = extract_1688(URL, client=client, dns_check=lambda _: True)
    assert result["extraction_status"] == "BLOCKED"
    assert result["reason"] == "UNSAFE_REDIRECT"
    assert requests == [URL]


def test_login_challenge_produces_no_snapshot():
    challenge = '<html><head><title>Security verification</title></head><body>Captcha</body></html>'
    with httpx.Client(transport=httpx.MockTransport(
        lambda _: httpx.Response(200, headers={"content-type": "text/html"}, text=challenge)
    )) as client:
        result = extract_1688(URL, client=client, dns_check=lambda _: True)
    assert result == {"source_url": URL, "extraction_status": "BLOCKED", "reason": "ACCESS_CHALLENGE"}


def test_javascript_only_1688_challenge_is_blocked():
    result = parse_1688_page(
        '<script>sessionStorage.x5referer = window.location.href; '
        'window.location.href = "/_____tmd_____/punish";</script>', URL,
    )
    assert result["extraction_status"] == "BLOCKED"
    assert "supplier_data" not in result


def test_unverified_page_cannot_be_attributed_to_the_offer():
    result = parse_1688_page('<div class="title-content"><h1>Unrelated product</h1></div>', URL)
    assert result == {"source_url": URL, "extraction_status": "PARSE_FAILED", "reason": "UNVERIFIED_OFFER"}


def test_bad_embedded_model_does_not_hide_a_later_valid_model():
    capture = (Path(__file__).parent / "fixtures" / "1688_offer_996518024136.html").read_text(encoding="utf-8")
    html = '<script>})(window.contextPath,{invalid})</script>' + capture
    assert parse_1688_page(html, URL)["supplier_data"]["supplier_name"] == "广州衣秀缘服饰商行(个人独资)"


def test_nontext_title_cannot_reach_supplier_data():
    html = '<link rel="canonical" href="' + URL + '">' \
           '<script>})(window.contextPath,{"result":{"data":{"productTitle":{"fields":' \
           '{"title":{"bad":"value"}}}}}})</script>'
    result = parse_1688_page(html, URL)
    assert result["extraction_status"] == "PARSE_FAILED"
    assert "supplier_data" not in result


def test_accessible_http_response_reaches_the_parser():
    capture = (Path(__file__).parent / "fixtures" / "1688_offer_996518024136.html").read_text(encoding="utf-8")
    with httpx.Client(transport=httpx.MockTransport(
        lambda _: httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text=capture)
    )) as client:
        result = extract_1688(URL, client=client, dns_check=lambda _: True)
    assert result["extraction_status"] == "PARTIAL"
    assert result["supplier_data"]["supplier_name"] == "广州衣秀缘服饰商行(个人独资)"


def test_fetch_has_an_absolute_deadline():
    ticks = iter((0, 1, 26))
    with httpx.Client(transport=httpx.MockTransport(
        lambda _: httpx.Response(200, headers={"content-type": "text/html"}, text="<html></html>")
    )) as client:
        result = extract_1688(URL, client=client, dns_check=lambda _: True, clock=lambda: next(ticks))
    assert result["extraction_status"] == "TIMEOUT"


def test_connection_uses_the_checked_public_ip(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
    ])
    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", lambda _self, host, *_args: host)
    assert PublicOnlyBackend().connect_tcp("detail.1688.com", 443) == "93.184.216.34"


def test_private_dns_answer_is_rejected_before_connect(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
    ])
    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", lambda *_args: pytest.fail("must not connect"))
    with pytest.raises(UnsafeDestination):
        PublicOnlyBackend().connect_tcp("detail.1688.com", 443)


@pytest.mark.parametrize(("http_status", "outcome"), [
    (401, "AUTH_REQUIRED"), (403, "BLOCKED"), (404, "UNSUPPORTED_PAGE"),
])
def test_http_access_statuses_keep_the_shared_vocabulary(http_status, outcome):
    with httpx.Client(transport=httpx.MockTransport(
        lambda _: httpx.Response(http_status)
    )) as client:
        result = extract_1688(URL, client=client, dns_check=lambda _: True)
    assert result["extraction_status"] == outcome
    assert "supplier_data" not in result


def test_http_timeout_keeps_the_shared_vocabulary():
    def timeout(_request):
        raise httpx.ReadTimeout("timed out")

    with httpx.Client(transport=httpx.MockTransport(timeout)) as client:
        result = extract_1688(URL, client=client, dns_check=lambda _: True)
    assert result["extraction_status"] == "TIMEOUT"
