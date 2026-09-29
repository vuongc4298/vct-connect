import os
import base64
from datetime import datetime, timedelta, timezone
from uuid import uuid4

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


ISSUER = "https://vct-test.clerk.accounts.dev"
AUDIENCE = "vct-connect-api"
PARTY = "http://127.0.0.1:3000"


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

    def get(self, analysis_id):
        return self.rows.get(analysis_id)

    def get_for_user(self, analysis_id, user_id):
        row = self.rows.get(analysis_id)
        return row if row and row["user_id"] == user_id else None


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
