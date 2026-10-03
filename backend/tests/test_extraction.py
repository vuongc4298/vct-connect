from datetime import datetime, timezone
from pathlib import Path
import json
import socket
import ssl
from uuid import uuid4

import httpcore
import httpx
import pytest

from backend.app.extraction import extract_1688, normalize_1688_url, parse_1688_page
from backend.app.extraction.offer1688 import (
    DeadlineStream, MAX_HTML_BYTES, PublicOnlyBackend,
    TemporaryDNSFailure, UnsafeDestination, _public_dns,
)
from backend.app.extraction.extension1688 import DomCapture, normalize_capture
from backend.app.extraction.renormalize import UnsupportedRawEvidence, renormalize_public_fields
from backend.app.extraction.contracts import EVIDENCE_FIELDS


URL = "https://detail.1688.com/offer/996518024136.html"
AT = datetime(2026, 9, 29, tzinfo=timezone.utc)


def test_selected_dom_capture_has_explicit_coverage_and_no_page_state():
    capture = DomCapture.model_validate({
        "source_url": URL,
        "canonical_url": URL,
        "offer_id": "996518024136",
        "fields": {"supplier_name": "  Visible supplier  ", "product_title": " Dress ",
                   "review_count": 12},
    })
    result = normalize_capture(capture)
    data = result["supplier_data"]
    assert result["extraction_status"] == "PARTIAL"
    assert data["extraction_method"] == "EXTENSION_DOM"
    assert data["analysis_mode"] == "EXTENSION_ENHANCED"
    assert data["supplier_name"] == "Visible supplier"
    assert data["products"][0]["title"] == "Dress"
    assert data["transaction_signals"] == {"review_count": 12}
    assert data["reviews"] is None and "reviews" in data["missing_fields"]
    assert result["reviews"] == []
    assert result["raw_payload"]["selected_fields"] == {
        "supplier_name": "Visible supplier", "product_title": "Dress", "review_count": 12,
    }
    assert set(result["raw_payload"]) == {"source_url", "captured_at", "provenance", "selected_fields"}


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


def test_saved_capture_has_upload_provenance_and_public_default_is_unchanged():
    capture = Path(__file__).parent / "fixtures" / "1688_offer_996518024136.html"
    html = capture.read_text(encoding="utf-8")
    uploaded = parse_1688_page(html, URL, extracted_at=AT, extraction_method="USER_UPLOAD")
    public = parse_1688_page(html, URL, extracted_at=AT)
    assert uploaded["supplier_data"]["extraction_method"] == "USER_UPLOAD"
    assert uploaded["supplier_data"]["extractor_version"] == "1688-user-upload.v1"
    assert uploaded["raw_payload"]["captured_at"] is None
    assert uploaded["raw_payload"]["imported_at"] == AT.isoformat()
    assert public["raw_payload"]["captured_at"] == AT.isoformat()
    assert "imported_at" not in public["raw_payload"]
    assert public["supplier_data"]["extraction_method"] == "PUBLIC_HTTP"
    assert uploaded["supplier_data"]["missing_fields"] == public["supplier_data"]["missing_fields"]
    wrong = parse_1688_page(html, "https://detail.1688.com/offer/111111111111.html",
                            extraction_method="USER_UPLOAD")
    assert wrong["extraction_status"] == "PARSE_FAILED"
    assert "supplier_data" not in wrong


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


@pytest.mark.parametrize("count", [0, 1, 25])
def test_saved_1688_review_volume_is_bounded_and_coverage_exact(count):
    cards = "".join(f'<div class="review-item">Review {i}</div>' for i in range(count))
    html = f'<link rel="canonical" href="{URL}"><div class="title-content"><h1>Dress</h1></div>{cards}'
    result = parse_1688_page(html, URL, extracted_at=AT)
    data = result["supplier_data"]
    assert result["extraction_status"] == "PARTIAL"
    assert len(result["reviews"]) == min(count, 20)
    assert data["reviews"] == (result["reviews"] or None)
    assert data["missing_fields"] == [field for field in EVIDENCE_FIELDS if data[field] is None]
    assert data["completeness"] == round((12 - len(data["missing_fields"])) / 12, 4)


def test_1688_raw_replay_requires_retained_offer_binding():
    html = (Path(__file__).parent / "fixtures" / "1688_offer_996518024136.html").read_text(encoding="utf-8")
    result = parse_1688_page(html, URL, extracted_at=AT)
    data = result["supplier_data"]
    replay = renormalize_public_fields(raw_payload=result["raw_payload"], source_url=URL,
        extraction_method="PUBLIC_HTTP", analysis_mode="ACCOUNT_PUBLIC", extracted_at=data["extracted_at"],
        source_snapshot_id=uuid4(), source_extractor_version=data["extractor_version"])
    assert replay["supplier_data"]["extractor_version"] == "1688-raw.v2"
    assert replay["supplier_data"]["completeness"] == data["completeness"]
    assert replay["supplier_data"]["missing_fields"] == data["missing_fields"]
    assert {key: replay["supplier_data"][key] for key in EVIDENCE_FIELDS} == {
        key: data[key] for key in EVIDENCE_FIELDS
    }
    result["raw_payload"]["public_fields"]["offer_base"]["offerId"] = "111111111111"
    with pytest.raises(UnsupportedRawEvidence):
        renormalize_public_fields(raw_payload=result["raw_payload"], source_url=URL,
            extraction_method="PUBLIC_HTTP", analysis_mode="ACCOUNT_PUBLIC", extracted_at=data["extracted_at"],
            source_snapshot_id=uuid4(), source_extractor_version=data["extractor_version"])


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
        result = extract_1688(URL, client=client, dns_check=lambda _: True, sleep=lambda _: None)
    assert result["extraction_status"] == "TIMEOUT"


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.delays = []

    def __call__(self):
        return self.now

    def sleep(self, delay):
        self.delays.append(delay)
        self.now += delay


def offer_html():
    return f'<link rel="canonical" href="{URL}"><div class="title-content"><h1>Dress</h1></div>'


def html_response(html=None):
    return httpx.Response(200, headers={"content-type": "text/html"}, text=html or offer_html())


@pytest.mark.parametrize("value", ["bad", "https://127.0.0.1/private", "https://detail.1688.com/login"])
def test_direct_invalid_extraction_is_classified_before_dns_or_fetch(value):
    with httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail("must not fetch"))) as client:
        result = extract_1688(value, client=client, dns_check=lambda _: pytest.fail("must not resolve"))
    assert result == {"source_url": value, "extraction_status": "UNSUPPORTED_PAGE", "reason": "INVALID_URL"}


@pytest.mark.parametrize(("html", "status", "reason"), [
    ("<title>Login required</title><body>Please sign in</body>", "AUTH_REQUIRED", "LOGIN_REQUIRED"),
    ("<body>请登录后查看</body>", "AUTH_REQUIRED", "LOGIN_REQUIRED"),
    ("<title>Login</title><body>Captcha 请登录</body>", "BLOCKED", "ACCESS_CHALLENGE"),
    ("<title>登录</title><script>sessionStorage.x5referer = 1</script>", "BLOCKED", "ACCESS_CHALLENGE"),
])
def test_access_page_classification_precedence_has_no_snapshot(html, status, reason):
    result = parse_1688_page(html, URL)
    assert result == {"source_url": URL, "extraction_status": status, "reason": reason}


@pytest.mark.parametrize("location", [
    "https://login.1688.com/member/signin.htm",
    "https://login.1688.com/member/signin.htm?Done=https%3A%2F%2Fdetail.1688.com",
])
def test_exact_login_redirect_is_classified_without_following(location):
    requests = []

    def respond(request):
        requests.append(str(request.url))
        return httpx.Response(302, headers={"location": location})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = extract_1688(URL, client=client, dns_check=lambda _: True)
    assert result == {"source_url": URL, "extraction_status": "AUTH_REQUIRED", "reason": "LOGIN_REQUIRED"}
    assert requests == [URL]


@pytest.mark.parametrize("location", [
    "https://login.1688.com.evil.test/member/signin.htm",
    "https://login.1688.com@127.0.0.1/member/signin.htm",
    "http://login.1688.com/member/signin.htm",
    "https://login.1688.com:443/member/signin.htm",
    "https://login.1688.com/other",
])
def test_login_lookalikes_remain_unsafe_redirects(location):
    with httpx.Client(transport=httpx.MockTransport(
        lambda _: httpx.Response(302, headers={"location": location})
    )) as client:
        result = extract_1688(URL, client=client, dns_check=lambda _: True)
    assert result["reason"] == "UNSAFE_REDIRECT"


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_temporary_http_failure_recovers_with_exact_backoff(status):
    clock = FakeClock()
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(status) if len(calls) < 3 else html_response()

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = extract_1688(URL, client=client, dns_check=lambda _: True, clock=clock, sleep=clock.sleep)
    assert len(calls) == 3
    assert clock.delays == [0.5, 1.0]
    assert result["extraction_status"] == "PARTIAL"
    assert result["supplier_data"]["supplier_name"] is None
    assert "supplier_name" in result["supplier_data"]["missing_fields"]


@pytest.mark.parametrize(("failure", "status", "reason"), [
    (httpx.ReadTimeout("secret"), "TIMEOUT", "HTTP_TIMEOUT"),
    (httpx.ConnectTimeout("secret"), "TIMEOUT", "HTTP_TIMEOUT"),
    (httpx.ConnectError("secret"), "PARSE_FAILED", "HTTP_ERROR"),
    (httpx.ReadError("secret"), "PARSE_FAILED", "HTTP_ERROR"),
    (httpx.RemoteProtocolError("secret"), "PARSE_FAILED", "HTTP_ERROR"),
    (TemporaryDNSFailure("secret"), "PARSE_FAILED", "DNS_ERROR"),
    (503, "PARSE_FAILED", "UPSTREAM_UNAVAILABLE"),
])
def test_exhausted_transient_failures_store_one_sanitized_outcome(failure, status, reason):
    clock = FakeClock()
    calls = []

    def respond(request):
        calls.append(request)
        if isinstance(failure, Exception):
            raise failure
        return httpx.Response(failure)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = extract_1688(URL, client=client, dns_check=lambda _: True, clock=clock, sleep=clock.sleep)
    assert len(calls) == 3 and clock.delays == [0.5, 1.0]
    assert result == {"source_url": URL, "extraction_status": status, "reason": reason}
    assert "secret" not in str(result)


@pytest.mark.parametrize(("response", "status", "reason"), [
    (httpx.Response(401), "AUTH_REQUIRED", "LOGIN_REQUIRED"),
    (httpx.Response(403), "BLOCKED", "ACCESS_CHALLENGE"),
    (httpx.Response(429), "BLOCKED", "ACCESS_CHALLENGE"),
    (httpx.Response(404), "UNSUPPORTED_PAGE", "HTTP_ERROR"),
    (httpx.Response(410), "UNSUPPORTED_PAGE", "HTTP_ERROR"),
    (httpx.Response(501), "PARSE_FAILED", "HTTP_ERROR"),
    (httpx.Response(200, headers={"content-type": "text/htmlish"}), "PARSE_FAILED", "NON_HTML"),
    (html_response("<title>Login required</title>"), "AUTH_REQUIRED", "LOGIN_REQUIRED"),
    (html_response("<title>Captcha</title>"), "BLOCKED", "ACCESS_CHALLENGE"),
    (html_response("<html></html>"), "PARSE_FAILED", "UNVERIFIED_OFFER"),
    (html_response(offer_html().replace("996518024136", "111111111111")), "PARSE_FAILED", "OFFER_MISMATCH"),
    (html_response("x" * (MAX_HTML_BYTES + 1)), "PARSE_FAILED", "PAGE_TOO_LARGE"),
])
def test_terminal_source_failures_are_never_retried(response, status, reason):
    calls = []
    clock = FakeClock()

    def respond(request):
        calls.append(request)
        return response

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = extract_1688(URL, client=client, dns_check=lambda _: True, clock=clock, sleep=clock.sleep)
    assert result == {"source_url": URL, "extraction_status": status, "reason": reason}
    assert len(calls) == 1 and clock.delays == []


def test_request_timeouts_shrink_after_dns_and_retry_elapsed_time():
    clock = FakeClock()
    timeouts = []

    def dns(_):
        clock.now += 2
        return True

    def respond(request):
        timeouts.append(request.extensions["timeout"])
        if len(timeouts) == 1:
            clock.now += 17
            return httpx.Response(503)
        return html_response()

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = extract_1688(URL, client=client, dns_check=dns, clock=clock, sleep=clock.sleep)
    assert result["extraction_status"] == "PARTIAL"
    assert timeouts[0] == {"connect": 5, "read": 10, "write": 10, "pool": 10}
    assert timeouts[1] == {"connect": 3.5, "read": 3.5, "write": 3.5, "pool": 3.5}


@pytest.mark.parametrize("elapsed", [24.5, 25, 26])
def test_backoff_cannot_start_another_attempt_without_budget(elapsed):
    clock = FakeClock()
    calls = []

    def respond(request):
        calls.append(request)
        clock.now = elapsed
        return httpx.Response(503)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = extract_1688(URL, client=client, dns_check=lambda _: True, clock=clock, sleep=clock.sleep)
    assert result["extraction_status"] == "TIMEOUT"
    assert len(calls) == 1 and clock.delays == []


def test_slow_dns_consumes_budget_before_request():
    clock = FakeClock()

    def dns(_):
        clock.now = 26
        return True

    with httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail("must not fetch"))) as client:
        result = extract_1688(URL, client=client, dns_check=dns, clock=clock)
    assert result["extraction_status"] == "TIMEOUT"


def test_temporary_dns_is_retried_but_private_answer_is_terminal(monkeypatch):
    clock = FakeClock()
    answers = iter([socket.gaierror(socket.EAI_AGAIN, "secret"), "127.0.0.1"])
    calls = []

    def resolve(*_, **__):
        answer = next(answers)
        calls.append(answer)
        if isinstance(answer, Exception):
            raise answer
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (answer, 443))]

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    with httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail("must not fetch"))) as client:
        result = extract_1688(URL, client=client, clock=clock, sleep=clock.sleep)
    assert result == {"source_url": URL, "extraction_status": "BLOCKED", "reason": "UNSAFE_DESTINATION"}
    assert len(calls) == 2 and clock.delays == [0.5]


def test_temporary_dns_can_recover_to_a_public_address(monkeypatch):
    clock = FakeClock()
    calls = []

    def resolve(*_, **__):
        calls.append(1)
        if len(calls) == 1:
            raise socket.gaierror(socket.EAI_AGAIN, "secret")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    with httpx.Client(transport=httpx.MockTransport(lambda _: html_response())) as client:
        result = extract_1688(URL, client=client, clock=clock, sleep=clock.sleep)
    assert result["extraction_status"] == "PARTIAL" and clock.delays == [0.5]


def test_permanent_dns_failure_has_no_retry(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs:
                        (_ for _ in ()).throw(socket.gaierror(socket.EAI_NONAME, "secret")))
    clock = FakeClock()
    with httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail("must not fetch"))) as client:
        result = extract_1688(URL, client=client, clock=clock, sleep=clock.sleep)
    assert result == {"source_url": URL, "extraction_status": "PARSE_FAILED", "reason": "DNS_ERROR"}
    assert clock.delays == []


def test_connection_rechecks_dns_after_public_preflight(monkeypatch):
    addresses = iter(["93.184.216.34", "127.0.0.1"])
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (next(addresses), 443)),
    ])
    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", lambda *_args: pytest.fail("must not connect"))
    assert _public_dns("detail.1688.com")
    with pytest.raises(UnsafeDestination):
        PublicOnlyBackend().connect_tcp("detail.1688.com", 443)


def test_retry_budget_does_not_repeat_a_normalized_redirect():
    clock = FakeClock()
    statuses = iter([503, 502, 302])
    calls = []

    def respond(request):
        calls.append(request)
        status = next(statuses)
        return httpx.Response(status, headers={"location": URL + f"?hop={len(calls)}"})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = extract_1688(URL, client=client, dns_check=lambda _: True, clock=clock, sleep=clock.sleep)
    assert result["reason"] == "REDIRECT_LOOP"
    assert len(calls) == 3 and clock.delays == [0.5, 1.0]
    assert all(str(request.url) == URL for request in calls)


@pytest.mark.parametrize(("location", "reason"), [
    (URL, "REDIRECT_LOOP"),
    ("https://detail.1688.com/offer/111111111111.html", "OFFER_MISMATCH"),
])
def test_redirect_loop_and_cross_offer_never_fetch_rejected_target(location, reason):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(302, headers={"location": location})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = extract_1688(URL, client=client, dns_check=lambda _: True)
    assert result["reason"] == reason and len(calls) == 1


class FailingStream(httpx.SyncByteStream):
    def __init__(self, clock=None, *, fail=True):
        self.closed = False
        self.clock = clock
        self.fail = fail

    def __iter__(self):
        yield offer_html().encode()
        if self.clock:
            self.clock.now += 26
        if self.fail:
            raise httpx.ReadTimeout("secret partial body")
        yield b"end"

    def close(self):
        self.closed = True


def test_partial_timeout_body_is_discarded_and_closed_before_backoff():
    stream = FailingStream()
    clock = FakeClock()
    calls = []

    def respond(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(200, headers={"content-type": "text/html"}, stream=stream)
        return html_response("<html></html>")

    def sleep(delay):
        assert stream.closed
        clock.sleep(delay)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = extract_1688(URL, client=client, dns_check=lambda _: True, clock=clock, sleep=sleep)
    assert result["reason"] == "UNVERIFIED_OFFER"
    assert len(calls) == 2 and clock.delays == [0.5]
    assert "supplier_data" not in result


@pytest.mark.parametrize("fail", [True, False])
def test_slow_stream_never_parses_partial_evidence(fail):
    clock = FakeClock()
    stream = FailingStream(clock, fail=fail)
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, headers={"content-type": "text/html"}, stream=stream)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = extract_1688(URL, client=client, dns_check=lambda _: True, clock=clock, sleep=clock.sleep)
    assert result == {"source_url": URL, "extraction_status": "TIMEOUT", "reason": "HTTP_TIMEOUT"}
    assert len(calls) == 1 and stream.closed and clock.delays == []


def test_socket_read_write_and_tls_timeouts_decrease_with_remaining_budget():
    clock = FakeClock()
    calls = []

    class Stream:
        def read(self, _max_bytes, timeout):
            calls.append(("read", timeout))
            return b"data"

        def write(self, _buffer, timeout):
            calls.append(("write", timeout))

        def start_tls(self, _context, server_hostname, timeout):
            calls.append((server_hostname, timeout))
            return self

    stream = DeadlineStream(Stream(), 25, clock)
    clock.now = 20
    stream.read(100, timeout=10)
    clock.now = 23
    stream.write(b"data", timeout=10)
    clock.now = 24
    secured = stream.start_tls(None, server_hostname="detail.1688.com", timeout=5)
    clock.now = 25
    with pytest.raises(httpcore.ReadTimeout):
        secured.read(100, timeout=10)
    assert calls == [("read", 5), ("write", 2), ("detail.1688.com", 1)]


@pytest.mark.parametrize("model", [
    [], 7, None, {"result": []}, {"result": {"data": 7}},
    {"result": {"data": {"productTitle": {"fields": {"shopInfo": []}}}}},
    {"result": {"data": {"productTitle": {"fields": {"rateInfo": {"commonTagNodeList": 7}}}}}},
    {"result": {"data": {"productTitle": {"fields": {"rateInfo": {"commonTagNodeList": [7]}}}}}},
    {"result": {"data": {"productTitle": {"fields": {"rateInfo": {"goodsGrade": {"bad": 1}}}}}}},
    {"result": {"data": {"Root": {"fields": {"dataJson": {"offerBaseInfo": {"offerId": []}}}}}}},
])
def test_malformed_embedded_structures_are_fixed_parser_failures(model):
    html = offer_html() + '<script>})(window.contextPath,' + json.dumps(model) + ')</script>'
    result = parse_1688_page(html, URL)
    assert result == {"source_url": URL, "extraction_status": "PARSE_FAILED", "reason": "MALFORMED_PAGE"}


def test_malformed_json_and_deep_nesting_have_fixed_parser_failures():
    malformed = offer_html() + '<script>})(window.contextPath,{broken})</script>'
    assert parse_1688_page(malformed, URL)["reason"] == "MALFORMED_PAGE"
    deeply_nested = offer_html() + '<script>})(window.contextPath,' + '[' * 2000 + '0' + ']' * 2000 + ')</script>'
    result = parse_1688_page(deeply_nested, URL)
    # Decoder recursion thresholds differ across Python versions. If decoding
    # succeeds, the nested array is still an invalid source model.
    assert result["source_url"] == URL
    assert result["extraction_status"] == "PARSE_FAILED"
    assert result["reason"] in {"PARSER_LIMIT", "MALFORMED_PAGE"}
    assert "supplier_data" not in result


def test_decoder_recursion_is_reported_as_parser_limit(monkeypatch):
    def exhausted_decoder(*_args, **_kwargs):
        raise RecursionError("decoder limit")
    monkeypatch.setattr(json.JSONDecoder, "raw_decode", exhausted_decoder)
    result = parse_1688_page(offer_html() + '<script>})(window.contextPath,{})</script>', URL)
    assert result == {"source_url": URL, "extraction_status": "PARSE_FAILED", "reason": "PARSER_LIMIT"}


@pytest.mark.parametrize("embedded", [False, True])
def test_navigation_login_prompt_does_not_hide_available_public_evidence(embedded):
    html = ((Path(__file__).parent / "fixtures" / "1688_offer_996518024136.html").read_text(encoding="utf-8")
            if embedded else '<html><body>' + offer_html() + '</body></html>')
    body_start = html.index('>', html.index('<body')) + 1
    html = html[:body_start] + '<nav>请登录 Please sign in</nav>' + html[body_start:]
    assert parse_1688_page(html, URL)["extraction_status"] == "PARTIAL"


@pytest.mark.parametrize("location", [
    "https://foo[bar]/", "https://[", "https://detail.1688.com:bad/offer/996518024136.html",
])
def test_malformed_redirect_is_terminal_before_another_fetch(location):
    calls, clock = [], FakeClock()
    def respond(request):
        calls.append(request)
        return httpx.Response(302, headers={"location": location})
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = extract_1688(URL, client=client, dns_check=lambda _: True, clock=clock, sleep=clock.sleep)
    assert result == {"source_url": URL, "extraction_status": "BLOCKED", "reason": "UNSAFE_REDIRECT"}
    assert len(calls) == 1 and clock.delays == []


def test_embedded_json_whitespace_keeps_verified_evidence():
    html = offer_html() + '<script>})(window.contextPath, \n\t{})</script>'
    assert parse_1688_page(html, URL)["extraction_status"] == "PARTIAL"


@pytest.mark.parametrize("extra", [
    '<script>})(window.contextPath,[])</script>',
    '<link rel="canonical" href="https://login.1688.com/member/signin.htm">',
])
def test_body_login_takes_precedence_over_malformed_or_login_canonical(extra):
    result = parse_1688_page('<body>请登录后查看' + extra + '</body>', URL)
    assert result == {"source_url": URL, "extraction_status": "AUTH_REQUIRED", "reason": "LOGIN_REQUIRED"}


@pytest.mark.parametrize("value", [float("nan"), float("inf"), "\ud800", "\x00"])
def test_unpersistable_nested_raw_values_are_terminal_parser_failures(value):
    model = {"result": {"data": {"productTitle": {"fields": {"rateInfo": {
        "commonTagNodeList": [{"name": "全部", "count": value}],
    }}}}}}
    html = offer_html() + '<script>})(window.contextPath,' + json.dumps(model) + ')</script>'
    result = parse_1688_page(html, URL)
    assert result == {"source_url": URL, "extraction_status": "PARSE_FAILED", "reason": "MALFORMED_PAGE"}


@pytest.mark.parametrize("title", ["\ud800", "\x00"])
def test_unpersistable_normalized_title_is_terminal_parser_failure(title):
    model = {"result": {"data": {"productTitle": {"fields": {"title": title}}}}}
    html = offer_html() + '<script>})(window.contextPath,' + json.dumps(model) + ')</script>'
    assert parse_1688_page(html, URL)["reason"] == "MALFORMED_PAGE"


@pytest.mark.parametrize(("html", "status", "reason"), [
    ("<title>Captcha</title>", "BLOCKED", "ACCESS_CHALLENGE"),
    ("<body>Please sign in</body>", "AUTH_REQUIRED", "LOGIN_REQUIRED"),
])
def test_transient_http_access_page_is_not_retried(html, status, reason):
    calls, clock = [], FakeClock()
    def respond(request):
        calls.append(request)
        return httpx.Response(503, headers={"content-type": "text/html"}, text=html)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = extract_1688(URL, client=client, dns_check=lambda _: True, clock=clock, sleep=clock.sleep)
    assert result == {"source_url": URL, "extraction_status": status, "reason": reason}
    assert len(calls) == 1 and clock.delays == []


def test_certificate_verification_failure_is_not_retried():
    calls, clock = [], FakeClock()
    def respond(request):
        calls.append(request)
        raise httpx.ConnectError("certificate verification failed") from ssl.SSLCertVerificationError("bad certificate")
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = extract_1688(URL, client=client, dns_check=lambda _: True, clock=clock, sleep=clock.sleep)
    assert result == {"source_url": URL, "extraction_status": "PARSE_FAILED", "reason": "HTTP_ERROR"}
    assert len(calls) == 1 and clock.delays == []
