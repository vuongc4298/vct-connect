import os
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import RLock
from uuid import UUID, uuid4

os.environ.setdefault("DEVELOPER_MODE", "true")
os.environ.setdefault("DATABASE_URL", "postgresql://unused")
os.environ["QUEUE_TRANSPORT"] = "local"

from fastapi.testclient import TestClient

from backend.app.auth import VerifiedIdentity
from backend.app.config import Settings
from backend.app.fixture import FIXTURE_URL, fixture_result
from backend.app.main import create_app
from backend.app.queue import AzureQueue
from backend.app.storage import LeaseLost, ResultConflict
from backend.worker.main import dispatch_outbox_once, process_azure_once, process_local_once


SETTINGS = Settings("postgresql://unused", "local", None, None, True)


class StaticVerifier:
    def verify(self, _request):
        return VerifiedIdentity("user_test")


class MemoryStore:
    def __init__(self):
        self.rows = {}
        self.local = {}
        self.outbox = {}
        self.results = {}
        self.users = {}
        self.complete_failure = False
        self.conflict_on_complete = False
        self.mark_publish_failure = False

    def resolve_user(self, clerk_user_id, email=None):
        return self.users.setdefault(
            clerk_user_id,
            {"id": uuid4(), "clerk_user_id": clerk_user_id, "email": email, "role": "CUSTOMER"},
        )

    def _submit(self, source_url, user_id):
        analysis_id = uuid4()
        self.rows[analysis_id] = {
            "id": analysis_id, "source_url": source_url, "status": "QUEUED",
            "created_at": "2026-09-27T00:00:00Z", "completed_at": None,
            "attempt_count": 0, "failure_code": None, "next_retry_at": None,
            "final_disposition": None, "result": None, "events": [{"status": "QUEUED"}],
            "user_id": user_id, "processing_token": None,
        }
        return analysis_id

    def submit_local(self, source_url, user_id=None):
        analysis_id = self._submit(source_url, user_id)
        self.local[analysis_id] = {"claim_token": None, "attempts": 0}
        return analysis_id

    def submit_azure(self, source_url, user_id=None):
        analysis_id = self._submit(source_url, user_id)
        self.outbox[analysis_id] = {"message_id": analysis_id, "attempts": 0, "token": None, "state": "PENDING"}
        return analysis_id

    def submit_customer(self, source_url, user_id, *, azure, customer_limit, window_seconds):
        return self.submit_azure(source_url, user_id) if azure else self.submit_local(source_url, user_id)

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

    def claim_outbox(self, _lease_seconds, max_attempts):
        for analysis_id, row in self.outbox.items():
            if row["state"] == "PENDING" and row["token"] is None:
                if row["attempts"] >= max_attempts:
                    row["state"] = "FAILED_FINAL"
                    if self.rows[analysis_id]["status"] == "QUEUED":
                        self.rows[analysis_id].update(status="FAILED_FINAL", failure_code="OUTBOX_PUBLISH_EXHAUSTED", final_disposition="PUBLICATION_FAILED")
                    return {"outcome": "exhausted", "analysis_id": analysis_id}
                row["token"] = uuid4()
                row["attempts"] += 1
                return {"outcome": "claimed", "analysis_id": analysis_id, "message_id": row["message_id"], "attempts": row["attempts"], "lease_token": row["token"]}
        return None

    def mark_outbox_published(self, analysis_id, token):
        if self.mark_publish_failure:
            raise RuntimeError("database unavailable")
        row = self.outbox[analysis_id]
        if row["token"] != token:
            raise LeaseLost
        row.update(state="PUBLISHED", token=None)

    def record_outbox_failure(self, analysis_id, token, *, max_attempts, **_):
        row = self.outbox[analysis_id]
        if row["token"] != token:
            raise LeaseLost
        row["token"] = None
        final = row["attempts"] >= max_attempts
        if final:
            row["state"] = "FAILED_FINAL"
            if self.rows[analysis_id]["status"] == "QUEUED":
                self.rows[analysis_id].update(status="FAILED_FINAL", failure_code="OUTBOX_PUBLISH_EXHAUSTED", final_disposition="PUBLICATION_FAILED")
        return final

    def observe_delivery(self, analysis_id):
        outbox = self.outbox.get(analysis_id)
        if outbox:
            outbox.update(state="PUBLISHED", token=None)
        row = self.rows.get(analysis_id)
        if row and row["status"] == "FAILED_FINAL" and row["failure_code"] == "OUTBOX_PUBLISH_EXHAUSTED":
            row.update(status="QUEUED", failure_code=None, final_disposition=None)
            row["events"].append({"status": "QUEUED", "attempt": row["attempt_count"]})

    def claim_local(self, _lease_seconds):
        for analysis_id, row in self.local.items():
            if row["claim_token"] is None:
                row["claim_token"] = uuid4()
                row["attempts"] += 1
                return {"analysis_id": analysis_id, "claim_token": row["claim_token"], "attempts": row["attempts"]}
        return None

    def claim_processing(self, analysis_id, _lease_seconds, max_attempts):
        row = self.rows.get(analysis_id)
        if row is None:
            return {"outcome": "unknown"}
        if row["status"] == "COMPLETED":
            return {"outcome": "completed"}
        if row["status"] == "FAILED_FINAL":
            return {"outcome": "final"}
        if row["processing_token"] is not None:
            return {
                "outcome": "busy",
                "available_at": datetime.now(timezone.utc) + timedelta(seconds=1),
            }
        if row["next_retry_at"] and row["next_retry_at"] > datetime.now(timezone.utc):
            return {"outcome": "waiting", "available_at": row["next_retry_at"]}
        if row["attempt_count"] >= max_attempts:
            row.update(status="FAILED_FINAL", failure_code="PROCESSING_ATTEMPTS_EXHAUSTED", final_disposition="DLQ_PENDING")
            row["events"].append({"status": "FAILED_FINAL", "attempt": row["attempt_count"], "failure_code": "PROCESSING_ATTEMPTS_EXHAUSTED"})
            return {"outcome": "final"}
        token = uuid4()
        attempt = row["attempt_count"] + 1
        row.update(status="PROCESSING", attempt_count=attempt, processing_token=token, next_retry_at=None)
        row["events"].append({"status": "PROCESSING", "attempt": attempt})
        return {"outcome": "acquired", "analysis_id": analysis_id, "source_url": row["source_url"], "attempt": attempt, "token": token}

    def complete_processing(self, analysis_id, token, payload):
        if self.complete_failure:
            raise RuntimeError("database unavailable")
        row = self.rows[analysis_id]
        if self.conflict_on_complete:
            original = fixture_result(FIXTURE_URL)
            self.results.setdefault(analysis_id, original)
            row.update(status="COMPLETED", result=original, processing_token=None)
            raise ResultConflict
        if row["status"] == "COMPLETED":
            if row["result"] == payload:
                return "replay"
            raise ResultConflict
        if row["processing_token"] != token:
            raise LeaseLost
        if analysis_id in self.results and self.results[analysis_id] != payload:
            raise ResultConflict
        self.results.setdefault(analysis_id, payload)
        row.update(status="COMPLETED", result=self.results[analysis_id], completed_at="2026-09-27T00:00:01Z", processing_token=None)
        row["events"].append({"status": "COMPLETED", "attempt": row["attempt_count"]})
        return "completed"

    def record_processing_failure(self, analysis_id, token, *, failure_code, max_attempts, local_claim_token=None, **_):
        row = self.rows[analysis_id]
        if row["processing_token"] != token:
            raise LeaseLost
        final = row["attempt_count"] >= max_attempts
        row.update(status="FAILED_FINAL" if final else "FAILED_RETRYABLE", failure_code=failure_code, processing_token=None, final_disposition="DLQ_PENDING" if final else None, next_retry_at=None if final else datetime.now(timezone.utc))
        row["events"].append({"status": row["status"], "attempt": row["attempt_count"], "failure_code": failure_code})
        if local_claim_token is not None:
            if self.local[analysis_id]["claim_token"] != local_claim_token:
                raise LeaseLost
            if final:
                del self.local[analysis_id]
            else:
                self.local[analysis_id]["claim_token"] = None
        return final

    def record_result_conflict(self, analysis_id):
        row = self.rows[analysis_id]
        row.update(status="COMPLETED", failure_code="RESULT_CONFLICT", processing_token=None)
        row["events"].append({"status": "COMPLETED", "attempt": row["attempt_count"], "failure_code": "RESULT_CONFLICT"})

    def finish_local(self, analysis_id, claim_token):
        if self.local[analysis_id]["claim_token"] != claim_token:
            raise LeaseLost
        del self.local[analysis_id]

    def release_local(self, analysis_id, claim_token, delay_seconds=2):
        if self.local[analysis_id]["claim_token"] != claim_token:
            raise LeaseLost
        self.local[analysis_id]["claim_token"] = None

    def mark_dead_lettered(self, analysis_id):
        row = self.rows[analysis_id]
        changed = row["final_disposition"] != "DEAD_LETTERED"
        row["final_disposition"] = "DEAD_LETTERED"
        return changed


class Receiver:
    def __init__(self, message_id, delivery_count=1, complete_failures=0, dead_letter_failures=0):
        self.message = type("Message", (), {"message_id": message_id, "delivery_count": delivery_count})()
        self.completed = 0
        self.abandoned = 0
        self.dead_letters = []
        self.complete_failures = complete_failures
        self.dead_letter_failures = dead_letter_failures

    def __enter__(self): return self
    def __exit__(self, *_): pass
    def receive_messages(self, **_): return [self.message]
    def complete_message(self, _):
        if self.complete_failures:
            self.complete_failures -= 1
            raise RuntimeError("settlement unavailable")
        self.completed += 1
    def abandon_message(self, _): self.abandoned += 1
    def dead_letter_message(self, _, **kwargs):
        if self.dead_letter_failures:
            self.dead_letter_failures -= 1
            raise RuntimeError("dead-letter unavailable")
        self.dead_letters.append(kwargs)


class Queue:
    def __init__(self, receiver=None):
        self.receiver = receiver
        self.published = []
        self.fail_publish = False
        self.renewals = 0

    def receive(self): return self.receiver
    @contextmanager
    def renew_lock(self, _receiver, _message, _max_seconds):
        self.renewals += 1
        yield
    def publish(self, analysis_id):
        self.published.append(analysis_id)
        if self.fail_publish:
            raise RuntimeError("ambiguous acknowledgement")


def test_azure_adapter_sets_real_service_bus_message_id():
    sent = []

    class Sender:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def send_messages(self, message): sent.append(message)

    class Client:
        def get_queue_sender(self, *_args, **_kwargs): return Sender()

    queue = object.__new__(AzureQueue)
    queue.connection_string = "unused"
    queue.queue_name = "analyses"
    queue.socket_timeout = 5.0
    queue.retry_total = 0
    queue._lock = RLock()
    queue.client = Client()
    analysis_id = uuid4()

    queue.publish(analysis_id)

    assert len(sent) == 1
    assert sent[0].message_id == str(analysis_id)


def test_local_queue_happy_path_and_exactly_one_result():
    store = MemoryStore()
    client = TestClient(create_app(store=store, settings=SETTINGS, verifier=StaticVerifier()))
    submitted = client.post("/api/v1/analyses", json={"source_url": FIXTURE_URL})
    analysis_id = UUID(submitted.json()["id"])
    assert submitted.status_code == 202
    assert process_local_once(store)
    assert store.rows[analysis_id]["status"] == "COMPLETED"
    assert store.rows[analysis_id]["result"] == fixture_result(FIXTURE_URL)
    assert len(store.results) == 1
    assert not process_local_once(store)


def test_live_offer_uses_queued_worker_path_and_exposes_blocked_outcome(monkeypatch):
    live_url = "https://detail.1688.com/offer/996518024136.html"
    seen = []

    def blocked(url, *, analysis_mode):
        seen.append((url, analysis_mode))
        return {"source_url": url, "extraction_status": "BLOCKED", "reason": "ACCESS_CHALLENGE"}

    monkeypatch.setattr("backend.worker.main.extract_1688", blocked)
    store = MemoryStore()
    client = TestClient(create_app(store=store, settings=SETTINGS, verifier=StaticVerifier()))
    submitted = client.post("/api/v1/analyses", json={"source_url": live_url + "?spm=track"})
    assert submitted.status_code == 202
    analysis_id = UUID(submitted.json()["id"])
    assert process_local_once(store)
    assert seen == [(live_url, "ACCOUNT_PUBLIC")]
    status = client.get(f"/api/v1/analyses/{analysis_id}")
    assert status.status_code == 200
    assert status.json()["result"] == {
        "source_url": live_url, "extraction_status": "BLOCKED", "reason": "ACCESS_CHALLENGE"
    }
    assert not process_local_once(store)


def test_azure_outbox_ambiguous_publish_reuses_message_id_and_preserves_result():
    store = MemoryStore()
    analysis_id = store.submit_azure(FIXTURE_URL)
    queue = Queue()
    queue.fail_publish = True
    assert dispatch_outbox_once(store, queue, SETTINGS)
    queue.fail_publish = False
    assert dispatch_outbox_once(store, queue, SETTINGS)
    assert queue.published == [analysis_id, analysis_id]

    receiver = Receiver(str(analysis_id))
    processing_queue = Queue(receiver)
    assert process_azure_once(store, processing_queue, SETTINGS)
    assert receiver.completed == 1
    assert processing_queue.renewals == 1
    duplicate = Receiver(str(analysis_id), 2)
    calls = 0
    def should_not_compute(_):
        nonlocal calls
        calls += 1
        raise AssertionError
    assert process_azure_once(store, Queue(duplicate), SETTINGS, compute=should_not_compute)
    assert duplicate.completed == 1
    assert calls == 0
    assert len(store.results) == 1


def test_marking_published_database_failure_leaves_safe_replayable_outbox_claim():
    store = MemoryStore()
    analysis_id = store.submit_azure(FIXTURE_URL)
    store.mark_publish_failure = True
    queue = Queue()
    try:
        dispatch_outbox_once(store, queue, SETTINGS)
        assert False, "Expected database failure"
    except RuntimeError:
        pass
    assert queue.published == [analysis_id]
    assert store.outbox[analysis_id]["state"] == "PENDING"


def test_transient_failures_record_retry_then_final_and_dead_letter():
    store = MemoryStore()
    analysis_id = store.submit_azure(FIXTURE_URL)
    settings = replace(SETTINGS, processing_max_attempts=2)
    def fail(_): raise RuntimeError("supplier detail must never become public")

    receiver = Receiver(str(analysis_id), 9)
    assert process_azure_once(store, Queue(receiver), settings, compute=fail, sleep=lambda _: None)
    assert receiver.abandoned == 0
    assert receiver.dead_letters[0]["reason"] == "PROCESSING_ERROR"
    assert "supplier" not in receiver.dead_letters[0]["error_description"]
    assert store.rows[analysis_id]["status"] == "FAILED_FINAL"
    assert store.rows[analysis_id]["attempt_count"] == 2
    assert store.rows[analysis_id]["final_disposition"] == "DEAD_LETTERED"
    assert [event["status"] for event in store.rows[analysis_id]["events"]] == [
        "QUEUED", "PROCESSING", "FAILED_RETRYABLE", "PROCESSING", "FAILED_FINAL"
    ]


def test_busy_delivery_keeps_same_lock_until_durable_claim_is_available():
    store = MemoryStore()
    analysis_id = store.submit_azure(FIXTURE_URL)
    store.rows[analysis_id]["processing_token"] = uuid4()
    receiver = Receiver(str(analysis_id), 8)

    def release_durable_claim(_seconds):
        store.rows[analysis_id]["processing_token"] = None

    assert process_azure_once(
        store, Queue(receiver), SETTINGS, sleep=release_durable_claim
    )
    assert receiver.abandoned == 0
    assert receiver.completed == 1
    assert store.rows[analysis_id]["attempt_count"] == 1


def test_completion_settlement_failure_replays_without_recomputation():
    store = MemoryStore()
    analysis_id = store.submit_azure(FIXTURE_URL)
    first = Receiver(str(analysis_id), complete_failures=1)
    try:
        process_azure_once(store, Queue(first), SETTINGS)
        assert False, "Expected settlement failure"
    except RuntimeError:
        pass
    assert store.rows[analysis_id]["status"] == "COMPLETED"

    calls = 0
    def should_not_compute(_):
        nonlocal calls
        calls += 1
        raise AssertionError
    replay = Receiver(str(analysis_id), delivery_count=2)
    assert process_azure_once(store, Queue(replay), SETTINGS, compute=should_not_compute)
    assert replay.completed == 1
    assert calls == 0
    assert len(store.results) == 1


def test_conflicting_duplicate_is_dead_lettered_and_first_result_is_preserved():
    store = MemoryStore()
    analysis_id = store.submit_azure(FIXTURE_URL)
    store.conflict_on_complete = True
    conflicting = {**fixture_result(FIXTURE_URL), "supplier_name": "Conflicting Supplier"}
    receiver = Receiver(str(analysis_id))
    assert process_azure_once(
        store, Queue(receiver), SETTINGS, compute=lambda _: conflicting
    )
    assert receiver.dead_letters[0]["reason"] == "RESULT_CONFLICT"
    assert store.rows[analysis_id]["status"] == "COMPLETED"
    assert store.rows[analysis_id]["result"] == fixture_result(FIXTURE_URL)
    assert store.rows[analysis_id]["failure_code"] == "RESULT_CONFLICT"
    assert store.rows[analysis_id]["events"][-1]["failure_code"] == "RESULT_CONFLICT"


def test_observed_delivery_recovers_ambiguous_publication_exhaustion():
    store = MemoryStore()
    analysis_id = store.submit_azure(FIXTURE_URL)
    settings = replace(SETTINGS, outbox_max_attempts=1)
    queue = Queue()
    queue.fail_publish = True
    assert dispatch_outbox_once(store, queue, settings)
    assert store.rows[analysis_id]["final_disposition"] == "PUBLICATION_FAILED"

    receiver = Receiver(str(analysis_id))
    assert process_azure_once(store, Queue(receiver), settings)
    assert receiver.completed == 1
    assert store.outbox[analysis_id]["state"] == "PUBLISHED"
    assert store.rows[analysis_id]["status"] == "COMPLETED"


def test_outbox_exhaustion_does_not_regress_active_processing():
    store = MemoryStore()
    analysis_id = store.submit_azure(FIXTURE_URL)
    active_token = uuid4()
    store.rows[analysis_id].update(
        status="PROCESSING", processing_token=active_token, attempt_count=1
    )
    settings = replace(SETTINGS, outbox_max_attempts=1)
    queue = Queue()
    queue.fail_publish = True

    assert dispatch_outbox_once(store, queue, settings)

    assert store.outbox[analysis_id]["state"] == "FAILED_FINAL"
    assert store.rows[analysis_id]["status"] == "PROCESSING"
    assert store.rows[analysis_id]["processing_token"] == active_token


def test_expired_outbox_claim_at_bound_is_finalized_without_another_publish():
    store = MemoryStore()
    analysis_id = store.submit_azure(FIXTURE_URL)
    store.outbox[analysis_id]["attempts"] = 2
    settings = replace(SETTINGS, outbox_max_attempts=2)
    queue = Queue()

    assert dispatch_outbox_once(store, queue, settings)

    assert queue.published == []
    assert store.outbox[analysis_id]["attempts"] == 2
    assert store.rows[analysis_id]["final_disposition"] == "PUBLICATION_FAILED"


def test_final_redelivery_only_retries_dead_letter_disposition():
    store = MemoryStore()
    analysis_id = store.submit_azure(FIXTURE_URL)
    store.rows[analysis_id].update(status="FAILED_FINAL", final_disposition="DLQ_PENDING")
    receiver = Receiver(str(analysis_id), 9)
    assert process_azure_once(store, Queue(receiver), SETTINGS, compute=lambda _: (_ for _ in ()).throw(AssertionError()))
    assert receiver.dead_letters[0]["reason"] == "AnalysisFailedFinal"
    assert store.rows[analysis_id]["final_disposition"] == "DEAD_LETTERED"


def test_failed_final_settlement_stays_pending_and_redelivery_does_not_recompute():
    store = MemoryStore()
    analysis_id = store.submit_azure(FIXTURE_URL)
    settings = replace(SETTINGS, processing_max_attempts=1)
    receiver = Receiver(str(analysis_id), dead_letter_failures=1)
    try:
        process_azure_once(
            store,
            Queue(receiver),
            settings,
            compute=lambda _: (_ for _ in ()).throw(RuntimeError("failure")),
        )
        assert False, "Expected dead-letter settlement failure"
    except RuntimeError:
        pass
    assert store.rows[analysis_id]["status"] == "FAILED_FINAL"
    assert store.rows[analysis_id]["final_disposition"] == "DLQ_PENDING"

    replay = Receiver(str(analysis_id), delivery_count=2)
    assert process_azure_once(
        store,
        Queue(replay),
        settings,
        compute=lambda _: (_ for _ in ()).throw(AssertionError("must not recompute")),
    )
    assert replay.dead_letters[0]["reason"] == "AnalysisFailedFinal"
    assert store.rows[analysis_id]["final_disposition"] == "DEAD_LETTERED"


def test_bad_messages_are_dead_lettered_without_inventing_rows():
    store = MemoryStore()
    malformed = Receiver("not-a-uuid")
    assert process_azure_once(store, Queue(malformed), SETTINGS)
    assert malformed.dead_letters[0]["reason"] == "InvalidMessageId"
    unknown_id = uuid4()
    unknown = Receiver(str(unknown_id))
    assert process_azure_once(store, Queue(unknown), SETTINGS)
    assert unknown.dead_letters[0]["reason"] == "UnknownAnalysis"
    assert unknown_id not in store.rows


def test_stale_local_claim_cannot_release_or_finish_newer_claim():
    store = MemoryStore()
    analysis_id = store.submit_local(FIXTURE_URL)
    old = store.claim_local(300)
    store.local[analysis_id]["claim_token"] = None
    newer = store.claim_local(300)
    for operation in (store.release_local, store.finish_local):
        try:
            operation(analysis_id, old["claim_token"])
            assert False, "Expected stale lease rejection"
        except LeaseLost:
            pass
    assert store.local[analysis_id]["claim_token"] == newer["claim_token"]


def test_invalid_url_and_remote_client_create_no_work():
    store = MemoryStore()
    client = TestClient(create_app(store=store, settings=SETTINGS, verifier=StaticVerifier()))
    assert client.post("/api/v1/analyses", json={"source_url": "https://evil.test"}).status_code == 422
    remote = TestClient(create_app(store=store, settings=SETTINGS, verifier=StaticVerifier()), client=("198.51.100.7", 12345))
    assert remote.post("/api/v1/analyses", json={"source_url": FIXTURE_URL}).status_code == 403
    assert store.rows == {}


def test_processing_limits_are_validated(monkeypatch):
    for value in ("0", "11"):
        monkeypatch.setenv("PROCESSING_MAX_ATTEMPTS", value)
        try:
            Settings.from_env()
            assert False, "Expected bounded configuration failure"
        except ValueError as error:
            assert "PROCESSING_MAX_ATTEMPTS" in str(error)


def test_processing_lease_must_cover_azure_lock_renewal(monkeypatch):
    monkeypatch.setenv("PROCESSING_MAX_ATTEMPTS", "5")
    monkeypatch.setenv("PROCESSING_LEASE_SECONDS", "60")
    monkeypatch.setenv("AZURE_LOCK_RENEWAL_SECONDS", "61")
    try:
        Settings.from_env()
        assert False, "Expected lease/renewal validation failure"
    except ValueError as error:
        assert "PROCESSING_LEASE_SECONDS" in str(error)
