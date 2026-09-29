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
from backend.app.main import create_app
from backend.app.queue import AzureQueue
from backend.app.storage import LeaseLost, ResultConflict, Store
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
        conn.execute("DELETE FROM local_queue WHERE analysis_id = %s", (analysis_id,))
        conn.execute("DELETE FROM analysis_results WHERE analysis_id = %s", (analysis_id,))
        conn.execute("DELETE FROM analyses WHERE id = %s", (analysis_id,))


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
