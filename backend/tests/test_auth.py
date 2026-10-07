import os
import base64
from hashlib import sha256
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from clerk_backend_api.security.types import AuthStatus, RequestState, TokenVerificationErrorReason
from fastapi.testclient import TestClient

os.environ.setdefault("DEVELOPER_MODE", "true")
os.environ.setdefault("DATABASE_URL", "postgresql://unused")
os.environ["QUEUE_TRANSPORT"] = "local"

from backend.app.auth import ClerkTokenVerifier
from backend.app.config import Settings, _issuer_from_publishable_key
from backend.app.fixture import FIXTURE_URL
from backend.app.main import create_app
from backend.app.storage import AdmissionDenied


ISSUER = "https://vct-test.clerk.accounts.dev"
AUDIENCE = "vct-connect-api"
PARTY = "http://127.0.0.1:3000"


def test_alibaba_url_submission_and_unsupported_recovery(signing_keys):
    private, public = signing_keys
    client, store = client_and_store(public)
    headers = auth_header(token(private, "alibaba_owner"))
    source = "https://dgxuandele.en.alibaba.com/company_profile.html"
    submitted = client.post("/api/v1/analyses", json={"source_url": source + "?spm=tracking"}, headers=headers)
    assert submitted.status_code == 202
    row = client.get("/api/v1/analyses/" + submitted.json()["id"], headers=headers).json()
    assert row["source_url"] == source
    before = len(store.rows)
    imported = client.post("/api/v1/analyses/import", params={"source_url": source}, content=b"public html", headers={**headers, "content-type": "text/html"})
    assert imported.status_code == 422 and imported.json()["detail"] == "Alibaba saved-page import is not supported"
    captured = client.post("/api/v1/analyses/capture", json={"source_url": source, "fields": {}}, headers=headers)
    assert captured.status_code == 422 and captured.json()["detail"] == "Alibaba browser capture is not supported"
    assert len(store.rows) == before
    assert client.get("/api/v1/analyses/" + submitted.json()["id"], headers=auth_header(token(private, "alibaba_other"))).status_code == 404


@pytest.mark.parametrize("shop", [False, True])
def test_taobao_upload_original_bytes_owner_and_encoding(signing_keys, shop):
    private, public = signing_keys
    client, store = client_and_store(public)
    url = "https://shop159450000.world.taobao.com/category.htm" if shop else "https://item.taobao.com/item.htm?id=1076425861755"
    filename = "taobao_shop_159450000.html" if shop else "taobao_item_1076425861755.html"
    page = (Path(__file__).parent / "fixtures" / filename).read_text(encoding="utf-8")
    body = page.replace('charset="utf-8"', 'charset="GBK"').encode("gb18030") if shop else page.encode()
    endpoint = "/api/v1/analyses/import?source_url=" + url
    headers = {**auth_header(token(private, "taobao_upload_owner")), "content-type": "text/html"}
    assert client.post(endpoint, content=body, headers={"content-type": "text/html"}).status_code == 401
    response = client.post(endpoint, content=body, headers=headers)
    assert response.status_code == 201
    analysis_id = response.json()["id"]
    row = client.get("/api/v1/analyses/" + analysis_id, headers=headers).json()
    assert row["supplier_data"]["platform"] == "TAOBAO"
    assert row["supplier_data"]["analysis_mode"] == "ACCOUNT_PUBLIC"
    assert row["supplier_data"]["extraction_method"] == "USER_UPLOAD"
    assert row["raw_evidence"]["html_sha256"] == sha256(body).hexdigest()
    assert row["raw_evidence"]["captured_at"] is None
    assert row["raw_evidence"]["imported_at"] == row["supplier_data"]["extracted_at"]
    assert client.get("/api/v1/analyses/" + analysis_id, headers=auth_header(token(private, "taobao_other"))).status_code == 404
    before = len(store.rows)
    assert client.post(endpoint, content=body, headers={**headers, "content-type": 'text/html; charset="utf-16"'}).status_code == 415
    if shop:
        assert client.post(endpoint, content=body, headers={**headers, "content-type": "text/html; charset=utf-8"}).status_code == 415
    assert len(store.rows) == before


def test_taobao_upload_admission_errors_and_pollable_wrong_identity(signing_keys):
    private, public = signing_keys
    client, store = client_and_store(public)
    url = "https://item.taobao.com/item.htm?id=1076425861755"
    endpoint = "/api/v1/analyses/import?source_url=" + url
    headers = {**auth_header(token(private)), "content-type": "text/html"}
    assert client.post(endpoint, content=b"\xff", headers=headers).status_code == 415
    assert client.post(endpoint, content=b"x"*2_000_001, headers=headers).status_code == 413
    assert client.post(endpoint, content=b"", headers=headers).status_code == 422
    assert client.post(endpoint, content='<meta charset="ascii">', headers=headers).status_code == 415
    assert client.post(endpoint.replace("item.taobao.com", "detail.tmall.com"), content="html", headers=headers).status_code == 422
    assert store.rows == {}
    html = (Path(__file__).parent / "fixtures" / "taobao_item_1076425861755.html").read_text(encoding="utf-8")
    response = client.post(endpoint, content=html.replace("1076425861755", "123456789"), headers=headers)
    assert response.status_code == 201
    row = store.rows[UUID(response.json()["id"])]
    assert row["result"]["extraction_status"] == "PARSE_FAILED" and row["supplier_data"] is None
    store.deny_import = True
    assert client.post(endpoint, content=html, headers=headers).status_code == 429


@pytest.mark.parametrize("shop", [False, True])
def test_taobao_capture_selected_evidence_owner_and_strict_schema(signing_keys, shop):
    import json
    private, public = signing_keys
    client, store = client_and_store(public)
    body = {"source_url": "https://shop159450000.world.taobao.com/category.htm" if shop else "https://item.taobao.com/item.htm?id=1076425861755",
            "source_kind": "shop" if shop else "item", "source_id": "159450000" if shop else "1076425861755",
            "fields": {"supplier_name": "  Selected shop  "}}
    if shop:
        body["fields"]["products"] = [{"source_url": "https://item.taobao.com/item.htm?id=1076425861755", "title": "Selected item"}]
    else:
        body["fields"].update(product_title="Selected item", reviews=[{"text": " Review ", "original_length": 8}])
    endpoint = "/api/v1/analyses/capture"
    headers = auth_header(token(private, "taobao_capture_owner"))
    assert client.post(endpoint, json=body).status_code == 401
    response = client.post(endpoint, json=body, headers=headers)
    assert response.status_code == 201
    row = client.get(endpoint.rsplit("/", 1)[0] + "/" + response.json()["id"], headers=headers).json()
    assert row["supplier_data"]["analysis_mode"] == "EXTENSION_ENHANCED"
    assert row["supplier_data"]["extraction_method"] == "EXTENSION_DOM"
    assert row["raw_evidence"]["provenance"] == "USER_PROVIDED_BROWSER_EVIDENCE"
    assert row["raw_evidence"]["selected_fields"]["supplier_name"] == "  Selected shop  "
    if not shop:
        expected = [{"text": "Review", "source_url": body["source_url"]}]
        assert row["supplier_data"]["reviews"] == expected
        assert row["reviews"] == expected
        assert row["raw_evidence"]["selected_fields"]["reviews"] == [{"text": " Review ", "original_length": 8}]
    assert client.get("/api/v1/analyses/" + response.json()["id"], headers=auth_header(token(private, "taobao_foreign"))).status_code == 404
    before = len(store.rows)
    for mutation in [{**body, "cookies": "PRIVATE_SENTINEL"}, {**body, "source_id": "1"},
                     {**body, "canonical_url": "https://item.taobao.com/item.htm?id=1"},
                     {**body, "fields": {**body["fields"], "token": "PRIVATE_SENTINEL"}}]:
        assert client.post(endpoint, json=mutation, headers=headers).status_code == 422
    forbidden = [{"product_title": "Wrong kind"}, {"reviews": [{"text": "Review", "original_length": 6}]}, {"shop_metrics": ["4.9"]}] if shop else [
        {"products": [{"source_url": body["source_url"], "title": "Collection not allowed"}]}]
    for field in forbidden:
        assert client.post(endpoint, json={**body, "fields": {**body["fields"], **field}}, headers=headers).status_code == 422
        assert len(store.rows) == before
    assert client.post(endpoint, content=json.dumps(body) + " "*16_384, headers={**headers, "content-type": "application/json"}).status_code == 413
    assert len(store.rows) == before
    store.users["taobao_capture_owner"]["role"] = "INTERNAL_REVIEWER"
    assert client.post(endpoint, json=body, headers=headers).status_code == 403


def test_capture_rejects_jsonb_unsafe_text_and_deep_nesting_before_admission(signing_keys):
    import json
    private, public = signing_keys
    client, store = client_and_store(public)
    headers = auth_header(token(private))
    body = {"source_url": "https://item.taobao.com/item.htm?id=1076425861755", "source_kind": "item",
            "source_id": "1076425861755", "fields": {"supplier_name": "Shop\x00name"}}
    assert client.post("/api/v1/analyses/capture", json=body, headers=headers).status_code == 422
    body["fields"]["supplier_name"] = "Shop"
    body["fields"]["product_title"] = "Invalid\ud800"
    assert client.post("/api/v1/analyses/capture", content=json.dumps(body),
                       headers={**headers, "content-type": "application/json"}).status_code == 422
    deep = '[' * 1100 + '0' + ']' * 1100
    assert client.post("/api/v1/analyses/capture", content=deep,
                       headers={**headers, "content-type": "application/json"}).status_code == 422
    assert store.rows == {}


@pytest.fixture(scope="module")
def signing_keys():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private, public


class AuthStore:
    def __init__(self):
        self.users = {}
        self.rows = {}
        self.reports = {}
        self.outbox = []

    def resolve_user(self, clerk_user_id, email=None):
        row = self.users.get(clerk_user_id)
        if row is None:
            row = {
                "id": uuid4(),
                "clerk_user_id": clerk_user_id,
                "email": email,
                "role": "CUSTOMER",
            }
            self.users[clerk_user_id] = row
        elif email:
            row["email"] = email
        return row.copy()

    def submit_local(self, source_url, user_id=None):
        analysis_id = uuid4()
        self.rows[analysis_id] = {
            "id": analysis_id,
            "source_url": source_url,
            "status": "QUEUED",
            "created_at": "2026-09-28T00:00:00Z",
            "completed_at": None,
            "result": None,
            "user_id": user_id,
        }
        return analysis_id

    def submit_azure(self, source_url, user_id=None):
        analysis_id = uuid4()
        self.outbox.append(analysis_id)
        self.rows[analysis_id] = {
            "id": analysis_id,
            "source_url": source_url,
            "status": "QUEUED",
            "created_at": "2026-09-28T00:00:00Z",
            "completed_at": None,
            "result": None,
            "user_id": user_id,
        }
        return analysis_id

    def submit_customer(self, source_url, user_id, *, azure, customer_limit, window_seconds):
        return self.submit_azure(source_url, user_id) if azure else self.submit_local(source_url, user_id)

    def import_customer_page(self, source_url, user_id, payload, *, customer_limit, window_seconds):
        if getattr(self, "deny_import", False):
            raise AdmissionDenied("limit")
        analysis_id = uuid4()
        self.rows[analysis_id] = {
            "id": analysis_id, "source_url": source_url, "status": "COMPLETED",
            "user_id": user_id, "result": {key: value for key, value in payload.items()
                                          if key not in {"supplier_data", "raw_payload", "reviews"}},
            "supplier_data": payload.get("supplier_data"),
            "raw_evidence": payload.get("raw_payload"),
            "reviews": payload.get("reviews", []),
        }
        return analysis_id

    def capture_customer_page(self, source_url, user_id, payload, *, customer_limit, window_seconds):
        return self.import_customer_page(
            source_url, user_id, payload,
            customer_limit=customer_limit, window_seconds=window_seconds,
        )

    def submit_guest(self, source_url, guest_key, *, azure, browser_limit, global_limit, window_seconds):
        analysis_id = self.submit_azure(source_url) if azure else self.submit_local(source_url)
        self.rows[analysis_id]["guest_key"] = guest_key
        return analysis_id

    def get_for_guest(self, analysis_id, guest_key):
        row = self.rows.get(analysis_id)
        return row if row and row.get("guest_key") == guest_key else None

    def get(self, analysis_id):
        return self.rows.get(analysis_id)

    def get_for_user(self, analysis_id, user_id):
        row = self.rows.get(analysis_id)
        return row if row and row["user_id"] == user_id else None

    def get_report_for_user(self, analysis_id, user_id):
        row = self.rows.get(analysis_id)
        if (
            row is None
            or row.get("user_id") != user_id
            or row.get("status") != "COMPLETED"
        ):
            return None
        payload = self.reports.get(analysis_id)
        return {"payload": payload, "created_at": "2026-10-07T00:00:00Z"} if payload else None


def settings(public_key):
    return Settings(
        "postgresql://unused",
        "local",
        None,
        None,
        True,
        clerk_jwt_key=public_key,
        clerk_issuer=ISSUER,
        clerk_audience=AUDIENCE,
        clerk_authorized_parties=(PARTY,),
    )


def token(private_key, subject="user_customer", *, omit=(), **overrides):
    now = datetime.now(timezone.utc)
    claims = {
        "sub": subject,
        "sid": "sess_test",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "azp": PARTY,
        "iat": now,
        "nbf": now - timedelta(seconds=1),
        "exp": now + timedelta(minutes=1),
    }
    claims.update(overrides)
    for claim in omit:
        claims.pop(claim, None)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test"})


def auth_header(value):
    return {"Authorization": f"Bearer {value}"}


def client_and_store(public_key):
    store = AuthStore()
    configured = settings(public_key)
    verifier = ClerkTokenVerifier(configured)
    return TestClient(create_app(store=store, settings=configured, verifier=verifier)), store


def test_missing_or_malformed_identity_creates_nothing(signing_keys):
    _, public = signing_keys
    client, store = client_and_store(public)
    missing = client.post("/api/v1/analyses", json={"source_url": FIXTURE_URL})
    malformed = client.post(
        "/api/v1/analyses",
        headers=auth_header("not-a-jwt"),
        json={"source_url": FIXTURE_URL},
    )
    assert missing.status_code == 401
    assert malformed.status_code == 401
    assert missing.json() == {"detail": "Unauthorized"}
    assert malformed.json() == {"detail": "Unauthorized"}
    assert store.users == {}
    assert store.rows == {}


@pytest.mark.parametrize(
    "claim_overrides",
    [
        {"exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        {"iat": datetime.now(timezone.utc) + timedelta(minutes=1)},
        {"nbf": datetime.now(timezone.utc) + timedelta(minutes=1)},
        {"iss": "https://other.clerk.accounts.dev"},
        {"aud": "some-other-api"},
        {"azp": "https://untrusted.example"},
    ],
    ids=["expired", "future-iat", "future-nbf", "wrong-issuer", "wrong-audience", "wrong-party"],
)
def test_invalid_claims_create_nothing(signing_keys, claim_overrides):
    private, public = signing_keys
    client, store = client_and_store(public)
    response = client.post(
        "/api/v1/analyses",
        headers=auth_header(token(private, **claim_overrides)),
        json={"source_url": FIXTURE_URL},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}
    assert store.users == {}
    assert store.rows == {}


def test_valid_unknown_subject_is_customer_and_owns_analysis(signing_keys):
    private, public = signing_keys
    client, store = client_and_store(public)
    customer = auth_header(token(private, "user_one"))
    submitted = client.post(
        "/api/v1/analyses", headers=customer, json={"source_url": FIXTURE_URL}
    )
    assert submitted.status_code == 202
    analysis_id = submitted.json()["id"]
    assert store.users["user_one"]["role"] == "CUSTOMER"
    assert client.get(f"/api/v1/analyses/{analysis_id}", headers=customer).status_code == 200

    other = auth_header(token(private, "user_two"))
    hidden = client.get(f"/api/v1/analyses/{analysis_id}", headers=other)
    assert hidden.status_code == 404
    assert hidden.json() == {"detail": "Analysis not found"}
    store.users["user_two"]["role"] = "ADMIN"
    assert client.get(f"/api/v1/analyses/{analysis_id}", headers=other).status_code == 200
    assert client.post(
        "/api/v1/analyses", headers=other, json={"source_url": FIXTURE_URL}
    ).status_code == 403


def test_database_roles_are_reloaded_for_each_request(signing_keys):
    private, public = signing_keys
    client, store = client_and_store(public)
    customer = auth_header(token(private, "user_role_change"))
    first = client.post(
        "/api/v1/analyses", headers=customer, json={"source_url": FIXTURE_URL}
    )
    assert first.status_code == 202
    analysis_id = first.json()["id"]

    store.users["user_role_change"]["role"] = "INTERNAL_REVIEWER"
    denied = client.post(
        "/api/v1/analyses", headers=customer, json={"source_url": FIXTURE_URL}
    )
    assert denied.status_code == 403
    assert client.get(f"/api/v1/analyses/{analysis_id}", headers=customer).status_code == 200

    store.users["user_role_change"]["role"] = "ADMIN"
    assert client.get(f"/api/v1/analyses/{analysis_id}", headers=customer).status_code == 200


def test_invalid_signature_is_unauthorized(signing_keys):
    _, public = signing_keys
    other_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    client, store = client_and_store(public)
    response = client.post(
        "/api/v1/analyses",
        headers=auth_header(token(other_private)),
        json={"source_url": FIXTURE_URL},
    )
    assert response.status_code == 401
    assert store.users == {}


def test_signed_non_session_jwt_is_unauthorized(signing_keys):
    private, public = signing_keys
    client, store = client_and_store(public)
    response = client.post(
        "/api/v1/analyses",
        headers=auth_header(token(private, omit=("sid",))),
        json={"source_url": FIXTURE_URL},
    )
    assert response.status_code == 401
    assert store.users == {}


def test_azure_api_submission_preserves_customer_ownership(signing_keys):
    private, public = signing_keys
    store = AuthStore()
    configured = Settings(
        "postgresql://unused",
        "azure",
        "Endpoint=unused",
        "analyses",
        True,
        clerk_jwt_key=public,
        clerk_issuer=ISSUER,
        clerk_audience=AUDIENCE,
        clerk_authorized_parties=(PARTY,),
    )

    class Queue:
        def __init__(self):
            self.published = []

        def publish(self, analysis_id):
            self.published.append(analysis_id)

    queue = Queue()
    client = TestClient(
        create_app(
            store=store,
            settings=configured,
            azure_queue=queue,
            verifier=ClerkTokenVerifier(configured),
        )
    )
    customer = auth_header(token(private, "user_azure_owner"))
    submitted = client.post(
        "/api/v1/analyses", headers=customer, json={"source_url": FIXTURE_URL}
    )
    assert submitted.status_code == 202
    analysis_id = submitted.json()["id"]
    assert queue.published == []
    assert [str(value) for value in store.outbox] == [analysis_id]
    assert store.rows[store.outbox[0]]["user_id"] == store.users["user_azure_owner"]["id"]
    assert client.get(f"/api/v1/analyses/{analysis_id}", headers=customer).status_code == 200
    store.rows[store.outbox[0]]["status"] = "COMPLETED"
    other = auth_header(token(private, "user_azure_other"))
    assert client.get(f"/api/v1/analyses/{analysis_id}", headers=other).status_code == 404


def test_publishable_key_issuer_fallback():
    encoded = base64.urlsafe_b64encode(b"vct-test.clerk.accounts.dev$").decode().rstrip("=")
    assert _issuer_from_publishable_key(f"pk_test_{encoded}") == ISSUER
    assert _issuer_from_publishable_key("malformed") is None
    assert _issuer_from_publishable_key(None) is None


def test_saved_page_import_requires_customer_and_owner(signing_keys):
    private, public = signing_keys
    client, store = client_and_store(public)
    url = "https://detail.1688.com/offer/996518024136.html"
    page = f'<link rel="canonical" href="{url}"><div class="title-content"><h1>Dress</h1></div>'
    endpoint = f"/api/v1/analyses/import?source_url={url}"
    assert client.post(endpoint, content=page, headers={"content-type": "text/html"}).status_code == 401
    owner = auth_header(token(private, "saved_page_owner"))
    submitted = client.post(endpoint, content=page, headers={**owner, "content-type": "text/html"})
    assert submitted.status_code == 201
    analysis_id = submitted.json()["id"]
    row = client.get(f"/api/v1/analyses/{analysis_id}", headers=owner).json()
    assert row["result"]["extraction_status"] == "PARTIAL"
    assert row["supplier_data"]["extraction_method"] == "USER_UPLOAD"
    assert row["supplier_data"]["missing_fields"]
    assert page not in str(row["raw_evidence"])
    other = auth_header(token(private, "saved_page_other"))
    assert client.get(f"/api/v1/analyses/{analysis_id}", headers=other).status_code == 404
    store.users["saved_page_owner"]["role"] = "ADMIN"
    assert client.post(endpoint, content=page, headers={**owner, "content-type": "text/html"}).status_code == 403


def test_saved_page_import_safe_outcomes_and_validation(signing_keys):
    private, public = signing_keys
    client, store = client_and_store(public)
    url = "https://detail.1688.com/offer/996518024136.html"
    endpoint = f"/api/v1/analyses/import?source_url={url}"
    headers = {**auth_header(token(private)), "content-type": "text/html; charset=utf-8"}
    challenge = client.post(endpoint, content="<title>Security verification</title>", headers=headers)
    assert challenge.status_code == 201
    blocked = store.rows[UUID(challenge.json()["id"])]
    assert blocked["result"]["extraction_status"] == "BLOCKED"
    assert blocked["supplier_data"] is None
    wrong = client.post(
        endpoint,
        content='<link rel="canonical" href="https://detail.1688.com/offer/111111111111.html"><h1>Wrong</h1>',
        headers=headers,
    )
    assert wrong.status_code == 201
    mismatch = store.rows[UUID(wrong.json()["id"])]
    assert mismatch["result"]["reason"] == "OFFER_MISMATCH"
    assert mismatch["supplier_data"] is None
    before = len(store.rows)
    assert client.post(endpoint, content="x" * 2_000_001, headers=headers).status_code == 413
    assert client.post(endpoint, content="<html></html>", headers={**headers, "content-type": "application/json"}).status_code == 415
    assert client.post(endpoint, content=b"\xff", headers=headers).status_code == 415
    assert len(store.rows) == before
    store.deny_import = True
    assert client.post(endpoint, content="<title>Captcha</title>", headers=headers).status_code == 429


def test_saved_page_import_checks_quoted_charsets_and_hashes_original_bytes(signing_keys):
    private, public = signing_keys
    client, store = client_and_store(public)
    url = "https://detail.1688.com/offer/996518024136.html"
    endpoint = f"/api/v1/analyses/import?source_url={url}"
    auth = auth_header(token(private))
    page = (f'<link rel="canonical" href="{url}">'
            '<div class="title-content"><h1>Dress</h1></div>').encode()
    for charset in ('text/html; charset = "gbk"', 'text/html; charset= "utf-16"'):
        assert client.post(endpoint, content=page, headers={**auth, "content-type": charset}).status_code == 415
    assert store.rows == {}
    uploaded = b"\xef\xbb\xbf" + page
    response = client.post(endpoint, content=uploaded,
                           headers={**auth, "content-type": 'text/html; charset = "utf-8"'})
    assert response.status_code == 201
    row = store.rows[UUID(response.json()["id"])]
    assert row["raw_evidence"]["html_sha256"] == sha256(uploaded).hexdigest()
    assert row["raw_evidence"]["captured_at"] is None
    assert row["raw_evidence"]["imported_at"] == row["supplier_data"]["extracted_at"]


def test_parser_recursion_error_is_a_pollable_failure_without_snapshot(signing_keys, monkeypatch):
    private, public = signing_keys
    client, store = client_and_store(public)
    url = "https://detail.1688.com/offer/996518024136.html"
    endpoint = f"/api/v1/analyses/import?source_url={url}"

    def nested_page(*_args, **_kwargs):
        raise RecursionError("deep page")

    monkeypatch.setattr("backend.app.main.parse_1688_page", nested_page)
    response = client.post(endpoint, content="<html></html>", headers={
        **auth_header(token(private)), "content-type": "text/html",
    })
    assert response.status_code == 201
    row = store.rows[UUID(response.json()["id"])]
    assert row["result"] == {"source_url": url, "extraction_status": "PARSE_FAILED", "reason": "PARSER_LIMIT"}
    assert row["supplier_data"] is None


@pytest.mark.parametrize("party,expected_status", [
    ("chrome-extension://klggcepemjjbphjclpiabgpfgdbgiljj", 201),
    ("chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", 401),
])
def test_capture_verifies_exact_configured_extension_origin(signing_keys, party, expected_status):
    private, public = signing_keys
    extension = "chrome-extension://klggcepemjjbphjclpiabgpfgdbgiljj"
    configured = replace(settings(public), clerk_authorized_parties=(PARTY, extension))
    store = AuthStore()
    client = TestClient(create_app(store=store, settings=configured, verifier=ClerkTokenVerifier(configured)))
    response = client.post("/api/v1/analyses/capture", headers=auth_header(token(private, azp=party)), json={
        "source_url": "https://detail.1688.com/offer/996518024136.html",
        "offer_id": "996518024136",
        "fields": {"product_title": "Visible product"},
    })
    assert response.status_code == expected_status
    assert len(store.rows) == (1 if expected_status == 201 else 0)


def test_extension_capture_requires_customer_and_preserves_owner_scope(signing_keys):
    private, public = signing_keys
    client, store = client_and_store(public)
    url = "https://detail.1688.com/offer/996518024136.html"
    capture = {
        "source_url": url,
        "canonical_url": url,
        "offer_id": "996518024136",
        "fields": {"product_title": "Visible dress", "supplier_name": "Visible supplier"},
    }
    route = "/api/v1/analyses/capture"
    assert client.post(route, json=capture).status_code == 401
    owner = auth_header(token(private, "extension_owner"))
    response = client.post(route, json=capture, headers=owner)
    assert response.status_code == 201
    analysis_id = UUID(response.json()["id"])
    row = store.rows[analysis_id]
    assert row["supplier_data"]["extraction_method"] == "EXTENSION_DOM"
    assert row["supplier_data"]["analysis_mode"] == "EXTENSION_ENHANCED"
    assert row["supplier_data"]["products"] == [{"offer_id": "996518024136", "title": "Visible dress"}]
    assert row["raw_evidence"]["selected_fields"] == capture["fields"]
    assert client.get(f"/api/v1/analyses/{analysis_id}", headers=owner).status_code == 200
    other = auth_header(token(private, "extension_other"))
    assert client.get(f"/api/v1/analyses/{analysis_id}", headers=other).status_code == 404
    store.users["extension_owner"]["role"] = "ADMIN"
    assert client.post(route, json=capture, headers=owner).status_code == 403


def test_extension_capture_rejects_extra_or_mismatched_evidence_and_sparse_page(signing_keys):
    private, public = signing_keys
    client, store = client_and_store(public)
    url = "https://detail.1688.com/offer/996518024136.html"
    headers = auth_header(token(private))
    route = "/api/v1/analyses/capture"
    base = {"source_url": url, "offer_id": "996518024136", "fields": {"product_title": "Dress"}}
    assert client.post(route, json={**base, "cookie": "should never be accepted"}, headers=headers).status_code == 422
    assert client.post(route, json={**base, "offer_id": "111111111111"}, headers=headers).status_code == 422
    assert client.post(route, json={**base, "canonical_url": "https://detail.1688.com/offer/111111111111.html"}, headers=headers).status_code == 422
    assert client.post(route, json={**base, "fields": {"product_title": "x" * 501}}, headers=headers).status_code == 422
    assert client.post(route, content=b"x" * 16_385, headers={**headers, "content-type": "application/json"}).status_code == 413
    assert not store.rows
    sparse = client.post(route, json={**base, "fields": {}}, headers=headers)
    assert sparse.status_code == 201
    row = store.rows[UUID(sparse.json()["id"])]
    assert row["result"]["reason"] == "NO_SELECTED_EVIDENCE"
    assert row["supplier_data"] is None
    store.deny_import = True
    assert client.post(route, json=base, headers=headers).status_code == 429


def test_jwks_outage_returns_service_unavailable(signing_keys, monkeypatch):
    private, public = signing_keys
    client, store = client_and_store(public)
    monkeypatch.setattr(
        "backend.app.auth.authenticate_request",
        lambda *_args, **_kwargs: RequestState(
            status=AuthStatus.SIGNED_OUT,
            reason=TokenVerificationErrorReason.JWK_FAILED_TO_LOAD,
        ),
    )
    response = client.post(
        "/api/v1/analyses",
        headers=auth_header(token(private)),
        json={"source_url": FIXTURE_URL},
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication unavailable"}
    assert store.users == {}


def test_guest_is_anonymous_and_only_own_key_can_read(signing_keys):
    _, public = signing_keys
    client, store = client_and_store(public)
    key = "a" * 64
    submitted = client.post(
        "/api/v1/guest-analyses",
        headers={"x-vct-guest-key": key},
        json={"source_url": FIXTURE_URL},
    )
    assert submitted.status_code == 202
    analysis_id = submitted.json()["id"]
    assert store.users == {}
    assert store.rows[next(iter(store.rows))]["user_id"] is None
    assert client.get(
        f"/api/v1/guest-analyses/{analysis_id}", headers={"x-vct-guest-key": key}
    ).status_code == 200
    assert client.get(
        f"/api/v1/guest-analyses/{analysis_id}", headers={"x-vct-guest-key": "b" * 64}
    ).status_code == 404
    assert client.get(f"/api/v1/guest-analyses/{analysis_id}").status_code == 404
    assert client.get(f"/api/v1/analyses/{analysis_id}").status_code == 401
    assert store.users == {}


def test_guest_fixture_validation_precedes_admission(signing_keys):
    _, public = signing_keys
    client, store = client_and_store(public)
    response = client.post(
        "/api/v1/guest-analyses",
        headers={"x-vct-guest-key": "a" * 64},
        json={"source_url": "https://example.org/other"},
    )
    assert response.status_code == 422
    assert store.rows == {}


def test_admission_denial_returns_stable_429_without_queueing(signing_keys):
    private, public = signing_keys
    client, store = client_and_store(public)

    def deny(*_args, **_kwargs):
        raise AdmissionDenied("Submission limit reached")

    store.submit_guest = deny
    store.submit_customer = deny
    guest = client.post(
        "/api/v1/guest-analyses", headers={"x-vct-guest-key": "a" * 64},
        json={"source_url": FIXTURE_URL},
    )
    customer = client.post(
        "/api/v1/analyses", headers=auth_header(token(private)),
        json={"source_url": FIXTURE_URL},
    )
    assert guest.status_code == customer.status_code == 429
    assert guest.json() == customer.json() == {"detail": "Submission limit reached"}
    assert store.rows == {}
    assert store.outbox == []


def test_full_report_endpoint_is_owner_only_and_not_public(signing_keys):
    private, public = signing_keys
    client, store = client_and_store(public)

    owner_headers = auth_header(token(private, "report_owner"))
    submitted = client.post(
        "/api/v1/analyses",
        headers=owner_headers,
        json={"source_url": FIXTURE_URL},
    )
    assert submitted.status_code == 202
    analysis_id = UUID(submitted.json()["id"])
    store.rows[analysis_id]["status"] = "COMPLETED"
    store.reports[analysis_id] = {
        "schema_version": "report.v1",
        "language": "vi",
        "analysis_id": str(analysis_id),
        "risk": {
            "overall_risk": 55,
            "label": "MODERATE",
            "confidence": 0.8,
            "coverage": 0.75,
            "scoring_version": "v0.1.0",
            "dimensions": [],
        },
    }

    url = f"/api/v1/analyses/{analysis_id}/report"
    assert client.get(url).status_code == 401
    owner = client.get(url, headers=owner_headers)
    assert owner.status_code == 200
    assert owner.json()["schema_version"] == "report.v1"
    assert owner.json()["risk"]["scoring_version"] == "v0.1.0"

    other_headers = auth_header(token(private, "report_other"))
    hidden = client.get(url, headers=other_headers)
    assert hidden.status_code == 404
    assert hidden.json() == {"detail": "Report not found"}

    store.users["report_other"]["role"] = "ADMIN"
    admin = client.get(url, headers=other_headers)
    assert admin.status_code == 403
    assert admin.json() == {"detail": "Forbidden"}
