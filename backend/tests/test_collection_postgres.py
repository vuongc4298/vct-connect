from hashlib import sha256
import json
import os
from uuid import UUID, uuid4
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
os.environ.setdefault("DEVELOPER_MODE", "true")
os.environ.setdefault("DATABASE_URL", "postgresql://unused")
os.environ["QUEUE_TRANSPORT"] = "local"
from backend.app.auth import VerifiedIdentity
from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.storage import Store
from backend.app.extraction.supplier_bundle import SupplierBundle, normalize_bundle
from backend.tests.test_supplier_bundle import selected
from backend.tests.test_browser_html import html_sources
from backend.tests.test_worker_assessment_postgres import cleanup, WorkerProvider
from backend.worker.main import process_local_once
from backend.app.intelligence.assessment import build_assessment


class Verifier:
    def __init__(self):
        self.owner = "collection_" + uuid4().hex

    def verify(self, request):
        return VerifiedIdentity(request.headers.get("x-test-owner", self.owner))


@pytest.fixture
def client_store():
    url = os.getenv("VCT_TEST_DATABASE_URL")
    if not url: pytest.skip("Set VCT_TEST_DATABASE_URL")
    store = Store(url); store.initialize()
    settings = Settings(url, "local", None, None, True)
    return TestClient(create_app(store=store, settings=settings, verifier=Verifier())), store, settings


def initial(value):
    result = {k: v for k, v in value.items() if k not in {"shop", "factory", "outcomes"}}
    if "html_sources" in result: result["html_sources"] = [x for x in result["html_sources"] if x["page"] == "PRODUCT"]
    return result


def test_alibaba_guided_sources_reserve_once_replay_finish_and_reach_owned_report(client_store):
    from backend.tests.test_alibaba_browser import selected as alibaba_selected
    client, store, settings = client_store
    value = alibaba_selected(); value['job_id'] = str(uuid4())
    analysis_id = UUID(value['job_id'])
    try:
        for _ in range(2):
            assert client.post('/api/v1/analyses/collection/begin', json=initial(value)).status_code == 202
        assert store.get(analysis_id)['status'] == 'PROCESSING'
        wrong = json.loads(json.dumps(value))
        wrong['factory']['shop_url'] = 'https://different.en.alibaba.com/'
        assert client.post('/api/v1/analyses/collection/finish', json=wrong).status_code == 422
        for _ in range(2):
            assert client.post('/api/v1/analyses/collection/finish', json=value).status_code == 202
        data = store.get(analysis_id)['supplier_data']
        assert data['platform'] == 'ALIBABA'
        assert data['company_information']['production_line_count'] == 4
        assert data['price_information']['minimum_order_quantity'] == 1
        provider = WorkerProvider()
        assert process_local_once(store, settings, assess=lambda data: build_assessment(data, provider=provider, model='fixture'))
        with store.connect() as conn:
            owner = conn.execute('SELECT user_id FROM analyses WHERE id=%s', (analysis_id,)).fetchone()['user_id']
            assert conn.execute("SELECT used FROM admission_counters WHERE scope='CUSTOMER' AND subject=%s", (str(owner),)).fetchone()['used'] == 1
            assert conn.execute('SELECT count(*) AS n FROM reports WHERE analysis_id=%s', (analysis_id,)).fetchone()['n'] == 1
        report = store.get_report_for_user(analysis_id, owner)['payload']
        assert any(e['evidence_id']=='supplier:html_sources' for e in report['evidence'])
        assert any(e['evidence_id']=='supplier:company_information' for e in report['evidence'])
        assert provider.chat_calls == 1
    finally: cleanup(store, analysis_id)


def test_combined_html_upload_enriches_one_owned_report(client_store):
    client, store, settings = client_store
    value = selected(); value["html_sources"] = html_sources(value)
    analysis_id = UUID(value["job_id"])
    try:
        assert client.post("/api/v1/analyses/collection/begin", json=initial(value)).status_code == 202
        assert client.post("/api/v1/analyses/collection/finish", json=value).status_code == 202
        assert client.post("/api/v1/analyses/collection/finish", json=value).status_code == 202
        data = store.get(analysis_id)["supplier_data"]
        assert data["products"][0]["packaging_display_text"] == "10 shirts per carton"
        assert len(data["reviews"]) == 10
        provider = WorkerProvider()
        assert process_local_once(store, settings, assess=lambda data: build_assessment(data, provider=provider, model="fixture"))
        with store.connect() as conn:
            owner = conn.execute("SELECT user_id FROM analyses WHERE id=%s", (analysis_id,)).fetchone()["user_id"]
        report = store.get_report_for_user(analysis_id, owner)["payload"]
        assert any(e["evidence_id"] == "supplier:html_sources" for e in report["evidence"])
        assert provider.chat_calls == 1
    finally: cleanup(store, analysis_id)


def test_guided_capture_allows_login_time_then_finishes_company_once(client_store):
    client, store, _ = client_store
    value = selected(); value["guided"] = True
    value["html_sources"] = html_sources(value)[:2]
    value.pop("factory")
    value["outcomes"] = [{"page": "SHOP", "status": "OK"}, {"page": "FACTORY", "status": "UNAVAILABLE"}]
    analysis_id = UUID(value["job_id"])
    try:
        for _ in range(2):
            assert client.post("/api/v1/analyses/collection/begin", json=initial(value)).status_code == 202
        with store.connect() as conn:
            row = conn.execute("SELECT expires_at-now() AS remaining FROM extension_collection_jobs WHERE analysis_id=%s", (analysis_id,)).fetchone()
            assert 1700 < row["remaining"].total_seconds() <= 1800
            # A human taking several minutes to log in must not trigger the old 60s fallback.
            conn.execute("UPDATE extension_collection_jobs SET expires_at=expires_at-interval '5 minutes' WHERE analysis_id=%s", (analysis_id,))
        assert store.finish_expired_collections() == 0
        assert store.get(analysis_id)["status"] == "PROCESSING"
        for _ in range(2):
            assert client.post("/api/v1/analyses/collection/finish", json=value).status_code == 202
        data = store.get(analysis_id)["supplier_data"]
        assert data["company_information"]["shop_introduction_display_text"]
        assert len(data["reviews"]) == 10
        with store.connect() as conn:
            assert conn.execute("SELECT count(*) AS n FROM local_queue WHERE analysis_id=%s", (analysis_id,)).fetchone()["n"] == 1
            owner = conn.execute("SELECT user_id FROM analyses WHERE id=%s", (analysis_id,)).fetchone()["user_id"]
            assert conn.execute("SELECT used FROM admission_counters WHERE scope='CUSTOMER' AND subject=%s", (str(owner),)).fetchone()["used"] == 1
    finally: cleanup(store, analysis_id)


def test_guided_user_opened_factory_requires_product_company_backlink(client_store):
    client, store, _ = client_store
    value = selected(); value["guided"] = True
    value["html_sources"] = [source for source in html_sources(value) if source["page"] != "SHOP"]
    value.pop("shop")
    value["outcomes"] = [{"page": "SHOP", "status": "UNAVAILABLE"}, {"page": "FACTORY", "status": "OK"}]
    analysis_id = UUID(value["job_id"])
    try:
        assert client.post("/api/v1/analyses/collection/begin", json=initial(value)).status_code == 202
        wrong = json.loads(json.dumps(value)); wrong["factory"]["shop_url"] = "https://shopwrong123.1688.com/"
        assert client.post("/api/v1/analyses/collection/finish", json=wrong).status_code == 422
        assert client.post("/api/v1/analyses/collection/finish", json=value).status_code == 202
        assert store.get(analysis_id)["supplier_data"]["years_active"] == 1
    finally: cleanup(store, analysis_id)


def test_real_phone_product_capture_with_svg_removed_reserves_linked_company(client_store):
    client, store, _ = client_store
    value = json.loads((Path(__file__).parent / "fixtures/1688-product-1009411929167-bundle.json").read_text(encoding="utf-8"))
    value["job_id"] = str(uuid4())
    analysis_id = UUID(value["job_id"])
    try:
        response = client.post("/api/v1/analyses/collection/begin", json=value)
        assert response.status_code == 202, response.text
        with store.connect() as conn:
            payload = conn.execute("SELECT initial_payload FROM extension_collection_jobs WHERE analysis_id=%s", (analysis_id,)).fetchone()["initial_payload"]
        assert payload["raw_payload"]["linked_collection"]["shop_url"] == "https://shop05n8n645901d1.1688.com/"
        assert payload["supplier_data"]["html_capture_status"][0]["status"] == "PARSED"
    finally: cleanup(store, analysis_id)


def test_html_upload_rejects_controls_and_oversized_selected_payload(client_store):
    client, _, _ = client_store
    value = selected(); value["html_sources"] = html_sources(value)
    value["html_sources"][0]["html"] += '<button>PRIVATE_ACCOUNT_CONTROL</button>'
    assert client.post("/api/v1/analyses/collection/finish", json=value).status_code == 422
    value["html_sources"] = html_sources(value)
    value["product"]["fields"]["reviews"] = [{"text": "厚" * 2000, "original_length": 2000}] * 20
    assert client.post("/api/v1/analyses/collection/finish", json=value).status_code == 422


@pytest.mark.parametrize("field", ["description", "claim"])
def test_finish_rejects_non_persistable_factory_text_before_storage(client_store, field):
    client, _, _ = client_store
    value = selected()
    if field == "description": value["factory"]["description"] = "invalid\x00text"
    else: value["factory"]["claims"][0]["value"] = "invalid\x00text"
    assert client.post("/api/v1/analyses/collection/finish", json=value).status_code == 422


def test_collection_reserves_once_finalizes_once_and_reports_combined_sources(client_store):
    client, store, settings = client_store
    value = selected(); analysis_id = UUID(value["job_id"])
    try:
        for _ in range(2):
            response = client.post("/api/v1/analyses/collection/begin", json=initial(value))
            assert response.status_code == 202, response.text
        assert store.get(analysis_id)["status"] == "PROCESSING"
        with store.connect() as conn:
            assert conn.execute("SELECT count(*) AS n FROM local_queue WHERE analysis_id=%s", (analysis_id,)).fetchone()["n"] == 0
            owner = conn.execute("SELECT user_id FROM analyses WHERE id=%s", (analysis_id,)).fetchone()["user_id"]
            used = conn.execute("SELECT used FROM admission_counters WHERE scope='CUSTOMER' AND subject=%s", (str(owner),)).fetchone()["used"]
            assert used == 1
        assert client.post("/api/v1/analyses/collection/finish", json=value, headers={"x-test-owner": "other_"+uuid4().hex}).status_code == 404
        for _ in range(2):
            response = client.post("/api/v1/analyses/collection/finish", json=value)
            assert response.status_code == 202, response.text
        with store.connect() as conn:
            assert conn.execute("SELECT count(*) AS n FROM local_queue WHERE analysis_id=%s", (analysis_id,)).fetchone()["n"] == 1
            assert conn.execute("SELECT count(*) AS n FROM supplier_snapshots WHERE analysis_id=%s", (analysis_id,)).fetchone()["n"] == 1
        assert store.get(analysis_id)["supplier_data"]["years_active"] == 1
        provider = WorkerProvider()
        assert process_local_once(store, settings, assess=lambda data: build_assessment(data, provider=provider, model="fixture"))
        assert store.get(analysis_id)["status"] == "COMPLETED"
        assert provider.chat_calls == 1
        report = store.get_report_for_user(analysis_id, owner)["payload"]
        assert any(e["evidence_id"] == "supplier:factory_profile" for e in report["evidence"])
        assert report["review_summary"]["review_count"] == 10
        changed = json.loads(json.dumps(value)); changed["factory"]["claims"][0]["value"] = "2024.07.14"
        assert client.post("/api/v1/analyses/collection/finish", json=changed).status_code == 409
    finally: cleanup(store, analysis_id)


def test_deadline_recovery_keeps_product_without_extra_admission(client_store):
    client, store, settings = client_store
    value = selected(); value["job_id"] = str(uuid4()); analysis_id = UUID(value["job_id"])
    value["html_sources"] = html_sources(value)
    try:
        assert client.post("/api/v1/analyses/collection/begin", json=initial(value)).status_code == 202
        with store.connect() as conn:
            conn.execute("UPDATE extension_collection_jobs SET expires_at=now()-interval '1 second' WHERE analysis_id=%s", (analysis_id,))
        assert store.finish_expired_collections() == 1
        assert store.finish_expired_collections() == 0
        row = store.get(analysis_id)
        assert row["status"] == "ASSESSING"
        assert len(row["reviews"]) == 10
        assert row["supplier_data"]["years_active"] is None
        assert row["supplier_data"]["products"][0]["packaging_display_text"] == "10 shirts per carton"
        assert row["raw_evidence"]["collection_deadline_fallback"] is True
        # A late completion cannot overwrite the deadline snapshot.
        assert client.post("/api/v1/analyses/collection/finish", json=value).status_code == 202
        assert store.get(analysis_id)["supplier_data"]["years_active"] is None
        provider = WorkerProvider()
        assert process_local_once(store, settings, assess=lambda data: build_assessment(data, provider=provider, model="fixture"))
        with store.connect() as conn:
            owner = conn.execute("SELECT user_id FROM analyses WHERE id=%s", (analysis_id,)).fetchone()["user_id"]
        report = store.get_report_for_user(analysis_id, owner)["payload"]
        assert any("TIMEOUT" in line for line in report["limitations_vi"])
    finally: cleanup(store, analysis_id)


def test_collection_rejects_oversize_and_changed_product(client_store):
    client, store, _ = client_store
    value = selected(); value["job_id"] = str(uuid4()); analysis_id = UUID(value["job_id"])
    try:
        assert client.post("/api/v1/analyses/collection/begin", json=initial(value)).status_code == 202
        changed = json.loads(json.dumps(value))
        changed["product"]["source_url"] = "https://detail.1688.com/offer/996518024136.html"
        changed["product"]["offer_id"] = "996518024136"
        assert client.post("/api/v1/analyses/collection/finish", json=changed).status_code == 409
        assert client.post("/api/v1/analyses/collection/finish", content='"'+'x'*32768+'"', headers={"content-type":"application/json"}).status_code == 413
    finally: cleanup(store, analysis_id)


def test_header_only_shop_capture_finishes_one_owned_analysis(client_store):
    from backend.tests.test_browser_html import header_only_shop_fixture
    client, store, _ = client_store
    value = header_only_shop_fixture(); value["guided"] = True
    analysis_id = UUID(value["job_id"])
    try:
        assert client.post("/api/v1/analyses/collection/begin", json=initial(value)).status_code == 202
        for _ in range(2):
            response = client.post("/api/v1/analyses/collection/finish", json=value)
            assert response.status_code == 202, response.text
        data = store.get(analysis_id)["supplier_data"]
        assert data["company_information"]["shop_evidence_scope"] == "SHOP_HEADER_ONLY"
        assert "shop_introduction_display_text" not in data["company_information"]
        with store.connect() as conn:
            assert conn.execute("SELECT count(*) AS n FROM local_queue WHERE analysis_id=%s", (analysis_id,)).fetchone()["n"] == 1
    finally: cleanup(store, analysis_id)
