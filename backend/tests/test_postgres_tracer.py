import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DEVELOPER_MODE", "true")
os.environ.setdefault("DATABASE_URL", "postgresql://unused")
os.environ["QUEUE_TRANSPORT"] = "local"

from backend.app.auth import InvalidIdentity, VerifiedIdentity
from backend.app.config import Settings
from backend.app.fixture import FIXTURE_URL, fixture_result
from backend.app.extraction import parse_1688_page
from backend.app.main import create_app
from backend.app.queue import AzureQueue
from backend.app.storage import AdmissionDenied, LeaseLost, ResultConflict, Store
from backend.worker.main import dispatch_outbox_once, process_azure_once, process_local_once


class StaticVerifier:
    def __init__(self, subject=None):
        self.subject = subject or f"user_postgres_{uuid4().hex}"

    def verify(self, _request):
        return VerifiedIdentity(self.subject)


class HeaderSubjectVerifier:
    def verify(self, request):
        value = request.headers.get("authorization", "")
        if not value.startswith("Bearer subject:"):
            raise InvalidIdentity
        return VerifiedIdentity(value.removeprefix("Bearer subject:"))


@pytest.fixture
def store():
    url = os.getenv("VCT_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set VCT_TEST_DATABASE_URL for PostgreSQL integration checks")
    instance = Store(url)
    instance.initialize()
    yield instance


def remove(store: Store, analysis_id: UUID):
    with store.connect() as conn:
        linked = conn.execute(
            "SELECT supplier_id FROM supplier_snapshots WHERE analysis_id = %s", (analysis_id,)
        ).fetchone()
        conn.execute("DELETE FROM local_queue WHERE analysis_id = %s", (analysis_id,))
        conn.execute("DELETE FROM analysis_results WHERE analysis_id = %s", (analysis_id,))
        conn.execute("UPDATE analyses SET supplier_snapshot_id = NULL WHERE id = %s", (analysis_id,))
        conn.execute("DELETE FROM supplier_snapshots WHERE analysis_id = %s", (analysis_id,))
        conn.execute("DELETE FROM analyses WHERE id = %s", (analysis_id,))
        if linked:
            conn.execute(
                "DELETE FROM suppliers WHERE id = %s AND NOT EXISTS "
                "(SELECT 1 FROM supplier_snapshots WHERE supplier_id = %s)",
                (linked["supplier_id"], linked["supplier_id"]),
            )


def remove_user(store: Store, clerk_user_id: str):
    with store.connect() as conn:
        conn.execute(
            """DELETE FROM users u WHERE u.clerk_user_id = %s
               AND NOT EXISTS (SELECT 1 FROM analyses a WHERE a.user_id = u.id)""",
            (clerk_user_id,),
        )


def test_azure_submission_atomically_creates_initial_event_and_outbox(store):
    analysis_id = store.submit_azure(FIXTURE_URL)
    try:
        row = store.get(analysis_id)
        assert row["status"] == "QUEUED"
        assert [event["status"] for event in row["events"]] == ["QUEUED"]
        with store.connect() as conn:
            outbox = conn.execute(
                "SELECT message_id, state, attempts FROM analysis_outbox WHERE analysis_id = %s",
                (analysis_id,),
            ).fetchone()
        assert outbox == {"message_id": analysis_id, "state": "PENDING", "attempts": 0}
    finally:
        remove(store, analysis_id)


def test_postgres_exact_replay_preserves_first_result(store):
    analysis_id = store.submit_local(FIXTURE_URL)
    try:
        assert process_local_once(store)
        first = store.get(analysis_id)
        assert first["status"] == "COMPLETED"
        assert first["result"] == fixture_result(FIXTURE_URL)
        assert store.complete_processing(analysis_id, uuid4(), fixture_result(FIXTURE_URL)) == "replay"
        with pytest.raises(ResultConflict):
            store.complete_processing(analysis_id, uuid4(), {"fixture": True, "source_url": "conflict"})
        store.record_result_conflict(analysis_id)
        with store.connect() as conn:
            count = conn.execute(
                "SELECT count(*) AS total FROM analysis_results WHERE analysis_id = %s",
                (analysis_id,),
            ).fetchone()["total"]
        assert count == 1
        assert store.get(analysis_id)["result"] == first["result"]
        assert store.get(analysis_id)["status"] == "COMPLETED"
        assert store.get(analysis_id)["events"][-1]["failure_code"] == "RESULT_CONFLICT"
    finally:
        remove(store, analysis_id)


def test_live_snapshot_transaction_linkage_owner_scope_and_replay(store):
    url = "https://detail.1688.com/offer/996518024136.html"
    owner = store.resolve_user(f"owner_{uuid4().hex}")
    other = store.resolve_user(f"other_{uuid4().hex}")
    analysis_id = store.submit_local(url, owner["id"])
    html = '<html><head><link rel="canonical" href="' + url + '"></head><body>' \
           '<div class="title-content"><h1>Dress</h1></div>' \
           '<div class="review-item">Accessible review</div></body></html>'
    payload = parse_1688_page(html, url)
    try:
        assert process_local_once(store, compute=lambda _: payload)
        client = TestClient(create_app(
            store=store,
            settings=Settings(store.database_url, "local", None, None, True),
            verifier=HeaderSubjectVerifier(),
        ))
        endpoint = f"/api/v1/analyses/{analysis_id}"
        first_response = client.get(endpoint, headers={"authorization": f"Bearer subject:{owner['clerk_user_id']}"})
        assert first_response.status_code == 200
        first = first_response.json()
        assert first["status"] == "COMPLETED"
        assert first["result"]["extraction_status"] == "PARTIAL"
        assert first["supplier_snapshot_id"]
        assert first["supplier_data"]["products"][0]["title"] == "Dress"
        assert first["supplier_data"]["source_url"] == url
        assert first["supplier_data"]["extraction_method"] == "PUBLIC_HTTP"
        assert first["supplier_data"]["analysis_mode"] == "ACCOUNT_PUBLIC"
        assert first["supplier_data"]["extractor_version"]
        assert first["supplier_data"]["extracted_at"]
        assert 0 < first["supplier_data"]["completeness"] < 1
        assert "supplier_name" in first["supplier_data"]["missing_fields"]
        assert first["raw_evidence"]["public_fields"]["title"] == "Dress"
        assert first["reviews"] == [{"text": "Accessible review", "source_url": url}]
        assert client.get(endpoint, headers={"authorization": f"Bearer subject:{other['clerk_user_id']}"}).status_code == 404
        assert store.complete_processing(analysis_id, uuid4(), payload) == "replay"
        changed_evidence = {**payload, "supplier_data": {**payload["supplier_data"], "supplier_name": "Changed"}}
        with pytest.raises(ResultConflict):
            store.complete_processing(analysis_id, uuid4(), changed_evidence)
        with store.connect() as conn:
            snapshot_count = conn.execute(
                "SELECT count(*) AS total FROM supplier_snapshots WHERE analysis_id = %s", (analysis_id,)
            ).fetchone()["total"]
            review_count = conn.execute(
                "SELECT count(*) AS total FROM supplier_reviews WHERE snapshot_id = %s",
                (first["supplier_snapshot_id"],),
            ).fetchone()["total"]
        assert (snapshot_count, review_count) == (1, 1)
        assert not process_local_once(store)
    finally:
        remove(store, analysis_id)
        remove_user(store, owner["clerk_user_id"])
        remove_user(store, other["clerk_user_id"])


def test_saved_page_import_is_atomic_owner_scoped_and_quota_limited(store):
    url = "https://detail.1688.com/offer/996518024136.html"
    owner = store.resolve_user(f"import_owner_{uuid4().hex}")
    other = store.resolve_user(f"import_other_{uuid4().hex}")
    html = (f'<link rel="canonical" href="{url}">'
            '<div class="title-content"><h1>Dress</h1></div>'
            '<div class="review-item">Accessible review</div>')
    payload = parse_1688_page(html, url, extraction_method="USER_UPLOAD")
    seller_id = f"seller_{uuid4().hex}"
    supplier_id = uuid4()
    original_url = "https://detail.1688.com/offer/111111111111.html"
    payload["supplier_data"]["platform_supplier_id"] = seller_id
    payload["supplier_data"]["supplier_name"] = "Uploaded name"
    with store.connect() as conn:
        conn.execute(
            """INSERT INTO suppliers (id, platform, platform_supplier_id, name, source_url)
               VALUES (%s, '1688', %s, %s, %s)""",
            (supplier_id, seller_id, "Existing name", original_url),
        )
    analysis_id = None
    try:
        invalid = {**payload, "supplier_data": {**payload["supplier_data"], "source_url": "wrong"}}
        with pytest.raises(ValueError):
            store.import_customer_page(url, owner["id"], invalid,
                                       customer_limit=1, window_seconds=86400)
        with store.connect() as conn:
            assert conn.execute(
                "SELECT used FROM admission_counters WHERE scope = 'CUSTOMER' AND subject = %s",
                (str(owner["id"]),),
            ).fetchone() is None
        analysis_id = store.import_customer_page(url, owner["id"], payload,
                                                 customer_limit=1, window_seconds=86400)
        row = store.get_for_user(analysis_id, owner["id"])
        assert row["status"] == "COMPLETED"
        assert row["extraction_method"] == "USER_UPLOAD"
        assert row["supplier_data"]["extraction_method"] == "USER_UPLOAD"
        assert row["supplier_data"]["supplier_name"] == "Uploaded name"
        assert row["reviews"] == [{"text": "Accessible review", "source_url": url}]
        assert html not in str(row["raw_evidence"])
        assert store.get_for_user(analysis_id, other["id"]) is None
        assert [event["status"] for event in row["events"]] == ["QUEUED", "PROCESSING", "COMPLETED"]
        with store.connect() as conn:
            shared = conn.execute(
                "SELECT name, source_url FROM suppliers WHERE id = %s", (supplier_id,),
            ).fetchone()
            assert shared == {"name": "Existing name", "source_url": original_url}
            assert conn.execute("SELECT 1 FROM local_queue WHERE analysis_id = %s", (analysis_id,)).fetchone() is None
            assert conn.execute("SELECT 1 FROM analysis_outbox WHERE analysis_id = %s", (analysis_id,)).fetchone() is None
        with pytest.raises(AdmissionDenied):
            store.import_customer_page(url, owner["id"], payload,
                                       customer_limit=1, window_seconds=86400)
    finally:
        if analysis_id:
            remove(store, analysis_id)
        with store.connect() as conn:
            conn.execute("DELETE FROM suppliers WHERE id = %s", (supplier_id,))
            conn.execute("DELETE FROM admission_counters WHERE scope = 'CUSTOMER' AND subject = %s",
                         (str(owner["id"]),))
        remove_user(store, owner["clerk_user_id"])
        remove_user(store, other["clerk_user_id"])


def test_blocked_offer_completes_without_a_snapshot(store):
    url = "https://detail.1688.com/offer/996518024136.html"
    analysis_id = store.submit_local(url)
    blocked = {"source_url": url, "extraction_status": "BLOCKED", "reason": "ACCESS_CHALLENGE"}
    try:
        assert process_local_once(store, compute=lambda _: blocked)
        result = store.get(analysis_id)
        assert result["status"] == "COMPLETED"
        assert result["result"] == blocked
        assert result["supplier_snapshot_id"] is None
        assert result["supplier_data"] is None
        assert result["raw_evidence"] is None
        assert result["reviews"] == []
    finally:
        remove(store, analysis_id)


def test_success_without_supplier_evidence_cannot_complete(store):
    url = "https://detail.1688.com/offer/996518024136.html"
    analysis_id = store.submit_local(url)
    try:
        claim = store.claim_processing(analysis_id, 300, 5)
        with pytest.raises(ValueError, match="missing matching supplier evidence"):
            store.complete_processing(
                analysis_id, claim["token"],
                {"source_url": url, "extraction_status": "SUCCESS"},
            )
        assert store.get(analysis_id)["result"] is None
        with store.connect() as conn:
            count = conn.execute(
                "SELECT count(*) AS total FROM supplier_snapshots WHERE analysis_id = %s",
                (analysis_id,),
            ).fetchone()["total"]
        assert count == 0
    finally:
        remove(store, analysis_id)


def test_stale_local_claim_cannot_mutate_newer_lease(store):
    analysis_id = store.submit_local(FIXTURE_URL)
    try:
        old = store.claim_local(10)
        with store.connect() as conn:
            conn.execute(
                "UPDATE local_queue SET claimed_until = now() - interval '1 second' WHERE analysis_id = %s",
                (analysis_id,),
            )
        newer = store.claim_local(10)
        with pytest.raises(LeaseLost):
            store.release_local(analysis_id, old["claim_token"])
        with store.connect() as conn:
            current = conn.execute(
                "SELECT claim_token FROM local_queue WHERE analysis_id = %s", (analysis_id,)
            ).fetchone()["claim_token"]
        assert current == newer["claim_token"]
    finally:
        remove(store, analysis_id)


def test_retry_and_final_transitions_are_ordered_and_sanitized(store):
    analysis_id = store.submit_azure(FIXTURE_URL)
    try:
        first = store.claim_processing(analysis_id, 60, 2)
        assert not store.record_processing_failure(
            analysis_id, first["token"], failure_code="PROCESSING_ERROR",
            max_attempts=2, retry_delay_seconds=0,
        )
        second = store.claim_processing(analysis_id, 60, 2)
        assert store.record_processing_failure(
            analysis_id, second["token"], failure_code="PROCESSING_ERROR",
            max_attempts=2, retry_delay_seconds=0,
        )
        row = store.get(analysis_id)
        assert row["status"] == "FAILED_FINAL"
        assert row["final_disposition"] == "DLQ_PENDING"
        assert [event["status"] for event in row["events"]] == [
            "QUEUED", "PROCESSING", "FAILED_RETRYABLE", "PROCESSING", "FAILED_FINAL"
        ]
        assert all(event["failure_code"] in {None, "PROCESSING_ERROR"} for event in row["events"])
    finally:
        remove(store, analysis_id)


def test_postgres_outbox_backoff_exhaustion_and_observed_delivery_recovery(store):
    analysis_id = store.submit_azure(FIXTURE_URL)
    try:
        first = store.claim_outbox(60, 2)
        assert first["attempts"] == 1
        assert not store.record_outbox_failure(
            analysis_id,
            first["lease_token"],
            max_attempts=2,
            base_backoff_seconds=2,
            max_backoff_seconds=60,
        )
        with store.connect() as conn:
            retry = conn.execute(
                """SELECT state, attempts, lease_token, leased_until,
                          last_error_code, next_attempt_at > now() AS backed_off
                   FROM analysis_outbox WHERE analysis_id = %s""",
                (analysis_id,),
            ).fetchone()
            conn.execute(
                "UPDATE analysis_outbox SET next_attempt_at = now() WHERE analysis_id = %s",
                (analysis_id,),
            )
        assert retry == {
            "state": "PENDING", "attempts": 1, "lease_token": None,
            "leased_until": None, "last_error_code": "OUTBOX_PUBLISH_RETRY",
            "backed_off": True,
        }

        second = store.claim_outbox(60, 2)
        assert second["attempts"] == 2
        assert store.record_outbox_failure(
            analysis_id,
            second["lease_token"],
            max_attempts=2,
            base_backoff_seconds=2,
            max_backoff_seconds=60,
        )
        row = store.get(analysis_id)
        assert row["status"] == "FAILED_FINAL"
        assert row["failure_code"] == "OUTBOX_PUBLISH_EXHAUSTED"
        assert row["final_disposition"] == "PUBLICATION_FAILED"

        store.observe_delivery(analysis_id)
        recovered = store.get(analysis_id)
        assert recovered["status"] == "QUEUED"
        assert recovered["failure_code"] is None
        assert recovered["final_disposition"] is None
        with store.connect() as conn:
            outbox = conn.execute(
                "SELECT state, last_error_code FROM analysis_outbox WHERE analysis_id = %s",
                (analysis_id,),
            ).fetchone()
        assert outbox == {"state": "PUBLISHED", "last_error_code": None}
    finally:
        remove(store, analysis_id)


def test_postgres_subject_mapping_role_reload_and_customer_ownership(store):
    settings = Settings(store.database_url, "local", None, None, True)
    client = TestClient(create_app(store=store, settings=settings, verifier=HeaderSubjectVerifier()))
    subject_one = f"user_{uuid4().hex}"
    subject_two = f"user_{uuid4().hex}"
    one = {"Authorization": f"Bearer subject:{subject_one}"}
    two = {"Authorization": f"Bearer subject:{subject_two}"}
    submitted = client.post("/api/v1/analyses", headers=one, json={"source_url": FIXTURE_URL})
    analysis_id = UUID(submitted.json()["id"])
    try:
        assert client.get(f"/api/v1/analyses/{analysis_id}", headers=two).status_code == 404
        with store.connect() as conn:
            second = conn.execute(
                "SELECT id FROM users WHERE clerk_user_id = %s", (subject_two,)
            ).fetchone()
            conn.execute("UPDATE users SET role = 'INTERNAL_REVIEWER' WHERE id = %s", (second["id"],))
        assert client.get(f"/api/v1/analyses/{analysis_id}", headers=two).status_code == 200
        assert client.post("/api/v1/analyses", headers=two, json={"source_url": FIXTURE_URL}).status_code == 403
    finally:
        remove(store, analysis_id)
        with store.connect() as conn:
            conn.execute("DELETE FROM users WHERE clerk_user_id IN (%s, %s)", (subject_one, subject_two))


def test_configured_azure_service_bus_round_trip(store):
    if os.getenv("VCT_TEST_AZURE") != "true":
        pytest.skip("Set VCT_TEST_AZURE=true and Service Bus settings for live Azure check")
    connection = os.environ["AZURE_SERVICE_BUS_CONNECTION_STRING"]
    name = os.environ["AZURE_SERVICE_BUS_QUEUE"]
    queue = AzureQueue(connection, name)
    settings = Settings(store.database_url, "azure", connection, name, True)
    verifier = StaticVerifier()
    client = TestClient(create_app(store=store, settings=settings, verifier=verifier))
    response = client.post("/api/v1/analyses", json={"source_url": FIXTURE_URL})
    analysis_id = UUID(response.json()["id"])
    try:
        dispatch_outbox_once(store, queue, settings)
        for _ in range(10):
            process_azure_once(store, queue, settings)
            if store.get(analysis_id)["status"] == "COMPLETED":
                break
        assert store.get(analysis_id)["status"] == "COMPLETED"
        assert client.get(f"/api/v1/analyses/{analysis_id}").json()["result"] == fixture_result(FIXTURE_URL)
    finally:
        remove(store, analysis_id)
        remove_user(store, verifier.subject)
