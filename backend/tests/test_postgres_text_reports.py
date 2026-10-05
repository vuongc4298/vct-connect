"""Disposable PostgreSQL integration rehearsal; never invokes a live provider."""
from decimal import Decimal
import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.tests.test_migrations import isolated_database_url
from backend.tests.test_postgres_tracer import HeaderSubjectVerifier
from backend.tests.test_text_reports import configured, FakeProvider, content
from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.storage import Store, LeaseLost
from backend.app.interpretation.service import process_report_once
from backend.app.extraction import parse_1688_page, parse_taobao_page
from backend.app.migrations import migration_status


@pytest.fixture
def report_store(isolated_database_url):
    store = Store(isolated_database_url)
    store.initialize()
    return store


def saved(store):
    owner = store.resolve_user("report-owner-" + uuid4().hex)
    source = "https://detail.1688.com/offer/996518024136.html"
    html = (Path(__file__).parent / "fixtures/1688_offer_996518024136.html").read_text(encoding="utf-8")
    payload = parse_1688_page(html, source, extraction_method="USER_UPLOAD")
    analysis_id = store.import_customer_page(source, owner["id"], payload, customer_limit=20, window_seconds=86400)
    return owner, analysis_id


def test_migration_owned_saved_evidence_progress_report_reopen_and_citations(report_store):
    store = report_store
    assert migration_status(store.database_url)[-1] == ("0010_text_reports", True)
    owner, analysis_id = saved(store)
    other = store.resolve_user("report-other-" + uuid4().hex)
    api = TestClient(create_app(store=store, settings=Settings(store.database_url, "local", None, None, True),
                                verifier=HeaderSubjectVerifier()))
    headers = {"authorization": "Bearer subject:" + owner["clerk_user_id"]}
    endpoint = f"/api/v1/analyses/{analysis_id}"
    before = api.get(endpoint, headers=headers).json()
    assert before["status"] == "COMPLETED" and before["text_report"]["state"] == "QUEUED"
    assert api.get(endpoint, headers={"authorization": "Bearer subject:" + other["clerk_user_id"]}).status_code == 404
    assert api.get(f"/api/v1/guest-analyses/{analysis_id}", headers={"x-vct-guest-key": "a" * 64}).status_code == 404
    provider = FakeProvider()
    assert process_report_once(store, configured(), provider)
    after = api.get(endpoint, headers=headers).json()
    assert after["text_report"]["state"] == "READY"
    for field in ("status", "result", "supplier_snapshot_id", "supplier_data", "raw_evidence", "events", "reviews"):
        assert after[field] == before[field]
    report = after["text_report"]["report"]
    assert report["self_reported_confidence"] == {"score": 0.65,
        "basis": "Dữ liệu nguồn còn thiếu; cần xác minh độc lập.",
        "provenance": "model_self_reported", "calibration": "uncalibrated"}
    assert after["text_report"]["generated_at"]
    ids = {item["id"] for item in report["evidence"]}
    assert all(ref in ids for finding in report["findings"] for ref in finding["citations"])
    assert Store(store.database_url).get_for_user(analysis_id, owner["id"])["text_report"]["report"] == report
    assert not process_report_once(store, configured(), provider)
    assert len(provider.calls) == 1
    with store.connect() as conn:
        ledger = conn.execute("SELECT * FROM text_report_dispatches WHERE analysis_id = %s", (analysis_id,)).fetchone()
    assert ledger["reserved_usd"] > 0 and ledger["actual_usd"] is None and ledger["settled_at"]
    assert ledger["metadata"]["request_id"] == "fake-request"


def test_crash_after_dispatch_marks_uncertain_fences_late_write_no_replay(report_store):
    store = report_store
    _, analysis_id = saved(store)
    claim = store.claim_text_report(10)
    assert store.dispatch_text_report(analysis_id, claim["lease_token"], Decimal("0.05"), Decimal("1"), Decimal("0.1"), {})
    with store.connect() as conn:
        conn.execute("UPDATE text_report_jobs SET leased_until = now() - interval '1 second' WHERE analysis_id = %s", (analysis_id,))
    assert store.claim_text_report(10) is None
    assert store.get(analysis_id)["text_report"]["state"] == "UNCERTAIN"
    with pytest.raises(LeaseLost):
        store.settle_text_report(analysis_id, claim["lease_token"], "FAILED", "INVALID_OUTPUT", None, {})
    provider = FakeProvider()
    assert not process_report_once(store, configured(), provider) and not provider.calls


def test_stale_predispatch_lease_reclaims_without_reusing_token(report_store):
    store = report_store
    _, analysis_id = saved(store)
    old = store.claim_text_report(10)
    assert store.claim_text_report(10) is None
    with store.connect() as conn:
        conn.execute("UPDATE text_report_jobs SET leased_until = now() - interval '1 second' WHERE analysis_id = %s", (analysis_id,))
    new = store.claim_text_report(10)
    assert old["lease_token"] != new["lease_token"]
    with pytest.raises(LeaseLost):
        store.dispatch_text_report(analysis_id, old["lease_token"], Decimal("0.05"), Decimal("1"), Decimal("0.1"), {})
    store.settle_text_report(analysis_id, new["lease_token"], "UNAVAILABLE", "PROVIDER_UNAVAILABLE", None, {})


def test_budget_reservation_atomic_and_survives_analysis_deletion(report_store):
    store = report_store
    _, first_id = saved(store)
    _, second_id = saved(store)
    first = store.claim_text_report(30)
    store.dispatch_text_report(first_id, first["lease_token"], Decimal("0.06"), Decimal("0.1"), Decimal("0.1"), {})
    second = store.claim_text_report(30)
    assert store.dispatch_text_report(second_id, second["lease_token"], Decimal("0.06"), Decimal("0.1"), Decimal("0.1"), {}) is None
    with store.connect() as conn:
        conn.execute("UPDATE analyses SET supplier_snapshot_id = NULL WHERE id = %s", (first_id,))
        conn.execute("DELETE FROM supplier_reviews WHERE snapshot_id IN (SELECT id FROM supplier_snapshots WHERE analysis_id = %s)", (first_id,))
        conn.execute("DELETE FROM text_report_jobs WHERE analysis_id = %s", (first_id,))
        conn.execute("DELETE FROM supplier_snapshots WHERE analysis_id = %s", (first_id,))
        conn.execute("DELETE FROM analysis_status_events WHERE analysis_id = %s", (first_id,))
        conn.execute("DELETE FROM analysis_results WHERE analysis_id = %s", (first_id,))
        conn.execute("DELETE FROM analyses WHERE id = %s", (first_id,))
    assert store.dispatch_text_report(second_id, second["lease_token"], Decimal("0.06"), Decimal("0.1"), Decimal("0.1"), {}) is None


def test_atomic_enqueue_rolls_back_extraction_on_job_insert_failure(report_store):
    store = report_store
    with store.connect() as conn:
        conn.execute("""CREATE FUNCTION reject_report_job() RETURNS trigger LANGUAGE plpgsql AS $$
                         BEGIN RAISE EXCEPTION 'test admission failure'; END $$;
                        CREATE TRIGGER reject_report BEFORE INSERT ON text_report_jobs
                        FOR EACH ROW EXECUTE FUNCTION reject_report_job();""")
    with pytest.raises(Exception, match="test admission failure"):
        saved(store)
    with store.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM analyses").fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM supplier_snapshots").fetchone()["n"] == 0


def test_concurrent_workers_cannot_overreserve_budget(report_store):
    from concurrent.futures import ThreadPoolExecutor
    store = report_store
    saved(store)
    saved(store)
    first, second = store.claim_text_report(30), store.claim_text_report(30)
    assert first["analysis_id"] != second["analysis_id"]
    def dispatch(claim):
        return store.dispatch_text_report(claim["analysis_id"], claim["lease_token"],
                                          Decimal("0.06"), Decimal("0.1"), Decimal("0.1"), {})
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(dispatch, [first, second]))
    assert sum(result is not None for result in results) == 1
    with store.connect() as conn:
        assert conn.execute("SELECT sum(reserved_usd) AS total FROM text_report_dispatches").fetchone()["total"] == Decimal("0.06")


def test_guest_and_fixture_never_dispatch(report_store):
    from backend.app.fixture import FIXTURE_URL
    from backend.worker.main import process_local_once
    store = report_store
    guest = store.submit_guest(FIXTURE_URL, "a" * 64, azure=False, browser_limit=3, global_limit=100, window_seconds=86400)
    assert process_local_once(store)
    assert store.get_for_guest(guest, "a" * 64)["text_report"] is None
    owner = store.resolve_user("fixture-owner")
    owned = store.submit_customer(FIXTURE_URL, owner["id"], azure=False, customer_limit=20, window_seconds=86400)
    assert process_local_once(store)
    assert store.get(owned)["text_report"]["state"] == "INSUFFICIENT"
    assert not process_report_once(store, configured(), FakeProvider())


@pytest.mark.parametrize("mode", ["local", "azure", "dispatcher"])
def test_continuous_worker_drains_report_only_imports_with_empty_extraction_and_outbox(report_store, monkeypatch, mode):
    from contextlib import nullcontext
    from backend.worker import main as worker
    store = report_store
    _, first_id = saved(store)
    _, second_id = saved(store)
    with store.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM local_queue").fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM analysis_outbox").fetchone()["n"] == 0
    provider = FakeProvider()
    monkeypatch.setattr(worker, "process_report_once", lambda active_store: process_report_once(active_store, configured(), provider))
    class EmptyQueue:
        def receive(self): return nullcontext(self)
        def receive_messages(self, **kwargs): return []
        def publish(self, *args): pytest.fail("No extraction outbox message should be published")
        def reconnect(self): pytest.fail("The bounded worker should not encounter an infrastructure error")
    class StopLoop(BaseException): pass
    def idle_sleep(seconds):
        # The first idle iteration occurs after both jobs have been drained.
        assert seconds == 1 and len(provider.calls) == 2
        raise StopLoop()
    monkeypatch.setattr(worker.time, "sleep", idle_sleep)
    settings = Settings(store.database_url, "local", None, None, True)
    with pytest.raises(StopLoop):
        worker._run_forever(store, None if mode == "local" else EmptyQueue(), settings,
                            "dispatcher" if mode == "dispatcher" else "combined")
    reopened = Store(store.database_url)
    for analysis_id in (first_id, second_id):
        row = reopened.get(analysis_id)
        assert row["status"] == "COMPLETED" and row["text_report"]["state"] == "READY"
        assert row["text_report"]["report"]["summary"]
    assert len(provider.calls) == 2


def test_authentic_chinese_projection_persistence_and_owner_reopen_offline(report_store):
    store = report_store
    owner = store.resolve_user("chinese-owner")
    other = store.resolve_user("chinese-other")
    source = "https://item.taobao.com/item.htm?id=1076425861755"
    html = (Path(__file__).parent / "fixtures/taobao_item_1076425861755.html").read_text(encoding="utf-8")
    payload = parse_taobao_page(html, source, extraction_method="USER_UPLOAD", uploaded_bytes=html.encode("utf-8"))
    assert payload["supplier_data"]["extractor_version"] == "taobao-upload.v1"
    assert payload["raw_payload"]["provenance"] == "USER_PROVIDED_SAVED_PAGE"
    assert payload["raw_payload"]["captured_at"] is None
    analysis_id = store.import_customer_page(source, owner["id"], payload, customer_limit=20, window_seconds=86400)
    original = store.get_for_user(analysis_id, owner["id"])
    # Hand-authored output checks the pipeline only, not live translation quality.
    data = json.loads(content())
    data["findings"] = [
        {"kind": "observation", "text": "Nguồn hiển thị sản phẩm “洁柔抽纸Face粉软柔韧100抽3层抽实惠亲肤细腻宝宝可用2元包邮”.", "citations": ["E1"]},
        {"kind": "observation", "text": "Nguồn hiển thị giá 2.01 và 3.35.", "citations": ["E2"]},
    ]
    provider = FakeProvider(json.dumps(data, ensure_ascii=False))
    assert process_report_once(store, configured(), provider)
    reopened = Store(store.database_url).get_for_user(analysis_id, owner["id"])
    assert reopened["text_report"]["state"] == "READY"
    report = reopened["text_report"]["report"]
    evidence = report["evidence"]
    assert evidence[0]["path"] == "products" and "洁柔抽纸" in evidence[0]["value"][0]["title"]
    assert evidence[1]["path"] == "price_information"
    assert evidence[2]["scope"] == {"positive_review_rate_display_text": "product", "shop_metrics_display_text": "shop"}
    reviews = [entry["value"] for entry in evidence if entry["path"] == "reviews"]
    assert reviews == ["质量特别好，一直都用的这款抽纸", "外包装摸起来挺顺滑的，不过纸张质地稍微有些疏松，厚度一般。不过日常使用完全足够了，性价比不错"]
    exported = provider.calls[0][0][1]["content"]
    for private in ("心相印维达生活馆", "159450000", "2895982467", "1076425861755", "<html>"):
        assert private not in exported
    assert report["self_reported_confidence"]["score"] == 0.65
    assert report["metadata"]["actual_cost_usd"] is None
    assert Store(store.database_url).get_for_user(analysis_id, owner["id"])["text_report"] == reopened["text_report"]
    assert store.get_for_user(analysis_id, other["id"]) is None
    for field in ("supplier_data", "reviews", "raw_evidence", "supplier_snapshot_id", "result"):
        assert reopened[field] == original[field]
    assert not process_report_once(store, configured(), provider) and len(provider.calls) == 1


def test_safe_diagnostic_persisted_in_dispatch_metadata_without_rejected_payload(report_store):
    store = report_store
    _, analysis_id = saved(store)
    data = json.loads(content())
    data["sensitive-source-key"] = "sensitive-source-value"
    provider = FakeProvider(json.dumps(data))
    process_report_once(store, configured(), provider)
    assert store.get(analysis_id)["text_report"]["state"] == "FAILED"
    with store.connect() as conn:
        ledger = conn.execute("SELECT * FROM text_report_dispatches WHERE analysis_id = %s", (analysis_id,)).fetchone()
    assert ledger["metadata"]["validation_reason"] == "SCHEMA_INVALID"
    assert ledger["metadata"]["validation_location"] == "report"
    assert "sensitive-source" not in json.dumps(ledger["metadata"])
    assert ledger["actual_usd"] is None and ledger["reserved_usd"] > 0
    assert not process_report_once(store, configured(), provider)


def test_saved_v1_report_reopens_without_inferred_confidence_or_generation(report_store):
    store = report_store
    owner, analysis_id = saved(store)
    process_report_once(store, configured(), FakeProvider())
    legacy = store.get(analysis_id)["text_report"]["report"]
    del legacy["self_reported_confidence"]
    legacy["metadata"].update(prompt_version="vi-text.v1", schema_version="text-report.v1")
    with store.connect() as conn:
        conn.execute("UPDATE text_report_jobs SET report = %s::jsonb WHERE analysis_id = %s", (json.dumps(legacy), analysis_id))
    assert Store(store.database_url).get_for_user(analysis_id, owner["id"])["text_report"]["report"] == legacy
    provider = FakeProvider()
    assert not process_report_once(store, configured(), provider) and not provider.calls
