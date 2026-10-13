from decimal import Decimal
import json
import os
from uuid import uuid4

import pytest

from backend.app.intelligence.assessment import build_assessment
from backend.app.intelligence.contracts import SCHEMA_VERSION
from backend.app.intelligence.media import MEDIA_SCHEMA_VERSION, ReviewMediaInput
from backend.app.intelligence.provider import EmbeddingResponse, ProviderResponse, ProviderUsage
from backend.app.config import Settings
from backend.app.extraction.extension1688 import DomCapture, normalize_capture
from backend.app.storage import ResultConflict, Store
from backend.worker.main import dispatch_outbox_once, process_azure_once, process_local_once


SOURCE_URL = "https://detail.1688.com/offer/996518024136.html"


class WorkerProvider:
    def __init__(self, *, supplier_dimensions=False):
        self.chat_calls = 0
        self.embedding_calls = 0
        self.supplier_dimensions = supplier_dimensions

    def generate_json(self, **kwargs):
        self.chat_calls += 1
        review = "review-evidence interpretation" in kwargs["system_prompt"]
        output = (
            {
                "schema_version": "review-interpretation.v1",
                "language": "vi",
                "findings": [{
                    "category": "QUALITY",
                    "severity": "MEDIUM",
                    "statement_vi": "Hai đánh giá phản ánh vấn đề chất lượng.",
                    "evidence_ids": ["review:0", "review:1"],
                    "confidence": 0.8,
                }],
                "confidence": 0.8,
            }
            if review else
            {
                "schema_version": SCHEMA_VERSION,
                "language": "vi",
                "summary_vi": "Bằng chứng nhà cung cấp được diễn giải có giới hạn.",
                "positive_signals": [],
                "risk_signals": [],
                "uncertainties": [{
                    "statement_vi": "Một số bằng chứng còn thiếu.",
                    "evidence_fields": ["certifications"],
                    "confidence": 0.7,
                }],
                "recommended_verifications": ["Xác minh tài liệu trước khi đặt cọc."],
                "confidence": 0.75,
            }
        )
        if not review and self.supplier_dimensions:
            output["dimension_assessments"] = [{
                "dimension": "PRICING", "severity": "LOW",
                "statement_vi": "Giá hiển thị cần đối chiếu trước khi giao dịch.",
                "evidence_fields": ["price_information"],
                "evidence_quotes": {"price_information": "12"}, "confidence": 0.6,
            }]
        return ProviderResponse(
            provider="FAKE_WORKER",
            request_id=f"worker-chat-{self.chat_calls}",
            requested_model=kwargs["model"],
            response_model="worker-model-v1",
            content=json.dumps(output, ensure_ascii=False),
            usage=ProviderUsage(100, 40, 140, Decimal("0.001"), {"total_tokens": 140}),
            latency_ms=20,
            finish_reason="stop",
            settings={"temperature": kwargs["temperature"], "max_tokens": kwargs["max_tokens"]},
        )

    def generate_multimodal_json(self, **kwargs):
        self.chat_calls += 1
        output = {
            "schema_version": MEDIA_SCHEMA_VERSION,
            "language": "vi",
            "findings": [{
                "media_id": "worker-img-0",
                "review_evidence_id": "review:0",
                "consistency": "SUPPORTS",
                "statement_vi": "Ảnh hỗ trợ mô tả vấn đề đường may.",
                "confidence": 0.9,
                "timestamp_ms": None,
            }],
            "confidence": 0.9,
        }
        return ProviderResponse(
            provider="FAKE_WORKER",
            request_id=f"worker-media-{self.chat_calls}",
            requested_model=kwargs["model"],
            response_model="worker-vision-v1",
            content=json.dumps(output, ensure_ascii=False),
            usage=ProviderUsage(70, 30, 100, Decimal("0.002"), {"total_tokens": 100}),
            latency_ms=12,
            finish_reason="stop",
            settings={"temperature": kwargs["temperature"], "max_tokens": kwargs["max_tokens"]},
        )

    def embed_texts(self, **kwargs):
        self.embedding_calls += 1
        return EmbeddingResponse(
            provider="FAKE_WORKER",
            request_id=f"worker-embed-{self.embedding_calls}",
            requested_model=kwargs["model"],
            response_model="worker-embed-v1",
            vectors=((1.0, 0.0), (0.99, 0.01)),
            usage=ProviderUsage(10, 0, 10, Decimal("0.0001"), {"total_tokens": 10}),
            latency_ms=5,
            settings={"encoding_format": "float"},
        )


def supplier_data():
    denominator = [
        "supplier_name", "company_information", "years_active", "categories",
        "certifications", "products", "price_information", "transaction_signals",
        "rating", "reviews", "delivery_information", "activity_history",
    ]
    return {
        "contract_version": "supplierdata.v1",
        "platform": "1688",
        "source_url": SOURCE_URL,
        "offer_id": "996518024136",
        "extracted_at": "2026-10-07T00:00:00+00:00",
        "extraction_method": "PUBLIC_HTTP",
        "analysis_mode": "GUEST_PUBLIC",
        "extractor_version": "worker-fixture",
        "completeness": 0.75,
        "completeness_denominator": denominator,
        "missing_fields": ["certifications", "delivery_information", "activity_history"],
        "platform_supplier_id": "worker-supplier",
        "supplier_name": "Worker Supplier",
        "company_information": {
            "business_type": "Manufacturer",
            "factory_area_sqm": 1800,
            "production_line_count": 2,
        },
        "years_active": 5,
        "categories": ["bags"],
        "certifications": None,
        "products": [{"title": "Bag"}],
        "price_information": {"min": 12},
        "transaction_signals": {"review_count": 10},
        "rating": 4.0,
        "reviews": [
            {"text": "Poor stitching quality", "source_url": "https://example.test/r1"},
            {"text": "Stitching quality is poor", "source_url": "https://example.test/r2"},
        ],
        "delivery_information": None,
        "activity_history": None,
    }


@pytest.fixture
def store():
    url = os.getenv("VCT_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set VCT_TEST_DATABASE_URL for PostgreSQL worker-assessment checks")
    instance = Store(url)
    instance.initialize()
    return instance


def cleanup(store, analysis_id):
    with store.connect() as conn:
        supplier = conn.execute(
            "SELECT supplier_id FROM supplier_snapshots WHERE analysis_id = %s",
            (analysis_id,),
        ).fetchone()
        conn.execute("DELETE FROM local_queue WHERE analysis_id = %s", (analysis_id,))
        conn.execute("DELETE FROM analysis_results WHERE analysis_id = %s", (analysis_id,))
        conn.execute("DELETE FROM analysis_assessments WHERE analysis_id = %s", (analysis_id,))
        conn.execute("DELETE FROM llm_review_runs WHERE analysis_id = %s", (analysis_id,))
        conn.execute("UPDATE analyses SET supplier_snapshot_id = NULL WHERE id = %s", (analysis_id,))
        conn.execute("DELETE FROM supplier_snapshots WHERE analysis_id = %s", (analysis_id,))
        conn.execute("DELETE FROM analyses WHERE id = %s", (analysis_id,))
        if supplier:
            conn.execute(
                "DELETE FROM suppliers WHERE id = %s AND NOT EXISTS "
                "(SELECT 1 FROM supplier_snapshots WHERE supplier_id = %s)",
                (supplier["supplier_id"], supplier["supplier_id"]),
            )


@pytest.mark.parametrize("admission", ["public", "import", "import_azure", "capture", "capture_azure"])
@pytest.mark.parametrize("supplier_dimensions", [False, True])
def test_worker_persists_report_completes_once_and_replay_spends_no_ai(store, admission, supplier_dimensions):
    data = supplier_data()
    owner = store.resolve_user("evidence_worker_" + uuid4().hex) if admission != "public" else None
    azure = admission.endswith("_azure")
    settings = Settings(store.database_url, "azure" if azure else "local", None, None, True, processing_max_attempts=1)
    if owner:
        data.update(extraction_method="USER_UPLOAD", analysis_mode="ACCOUNT_PUBLIC")
    payload = {
        "source_url": SOURCE_URL,
        "extraction_status": "PARTIAL",
        "raw_payload": {"fixture": True},
        "reviews": data["reviews"],
        "supplier_data": data,
    }
    if admission.startswith("capture"):
        payload = normalize_capture(DomCapture.model_validate({
            "source_url": SOURCE_URL, "offer_id": "996518024136",
            "fields": {"supplier_name": "Synthetic worker supplier", "product_title": "Synthetic bag",
                       "company_location": "Guangdong", "price_text": "12 CNY", "review_count": 10},
        }))
        data = payload["supplier_data"]
    expected_chat_calls = 2 if data["reviews"] else 1
    expected_embedding_calls = 1 if data["reviews"] else 0
    provider = WorkerProvider(supplier_dimensions=supplier_dimensions)
    assessor_calls = 0

    def assessor(snapshot):
        nonlocal assessor_calls
        assessor_calls += 1
        return build_assessment(
            snapshot,
            provider=provider,
            model="worker-chat",
            embedding_provider=provider,
            embedding_model="worker-embedding",
            metadata={"feature": "worker_test"},
        )

    persist = store.capture_customer_page if admission.startswith("capture") else store.import_customer_page
    analysis_id = persist(SOURCE_URL, owner["id"], payload, customer_limit=20, window_seconds=86400, azure=azure) if owner else store.submit_local(SOURCE_URL)
    try:
        if owner:
            assert store.get(analysis_id)["attempt_count"] == 0
            snapshot_id = store.get(analysis_id)["supplier_snapshot_id"]
        if azure:
            from backend.tests.test_tracer import Queue, Receiver
            queue = Queue(Receiver(str(analysis_id)))
            queue.fail_publish = True
            assert dispatch_outbox_once(store, queue, settings)
            queue.fail_publish = False
            with store.connect() as conn:
                conn.execute("UPDATE analysis_outbox SET next_attempt_at = now() WHERE analysis_id = %s", (analysis_id,))
            assert dispatch_outbox_once(store, queue, settings)
            assert queue.published == [analysis_id, analysis_id]
            process = lambda **kwargs: process_azure_once(store, queue, settings, **kwargs)
        else:
            process = lambda **kwargs: process_local_once(store, settings, **kwargs)
        assert process(
            compute=lambda _url: (_ for _ in ()).throw(AssertionError("stored evidence re-extracted")) if owner else payload,
            assess=assessor,
        )
        row = store.get(analysis_id)
        assert row["status"] == "COMPLETED"
        assert assessor_calls == 1
        assert provider.chat_calls == expected_chat_calls
        assert provider.embedding_calls == expected_embedding_calls
        if owner:
            assert row["supplier_snapshot_id"] == snapshot_id
            assert store.get_report_for_user(analysis_id, owner["id"]) is not None
            assert store.get_report_for_user(analysis_id, uuid4()) is None
        assert store.complete_processing(analysis_id, uuid4(), payload) == "replay"
        changed = json.loads(json.dumps(payload))
        changed["raw_payload"]["different"] = True
        with pytest.raises(ResultConflict):
            store.complete_processing(analysis_id, uuid4(), changed)

        with store.connect() as conn:
            assessment = conn.execute(
                "SELECT id, scoring_version, risk_label FROM analysis_assessments "
                "WHERE analysis_id = %s",
                (analysis_id,),
            ).fetchone()
            assert assessment is not None
            assert assessment["scoring_version"] == "v0.2.1"
            assert conn.execute(
                "SELECT count(*) AS n FROM llm_review_runs "
                "WHERE assessment_id = %s",
                (assessment["id"],),
            ).fetchone()["n"] == expected_chat_calls
            assert conn.execute(
                "SELECT count(*) AS n FROM analysis_findings "
                "WHERE assessment_id = %s",
                (assessment["id"],),
            ).fetchone()["n"] > 0
            assert conn.execute(
                "SELECT count(*) AS n FROM analysis_evidence "
                "WHERE assessment_id = %s",
                (assessment["id"],),
            ).fetchone()["n"] > 0
            report = conn.execute(
                "SELECT schema_version, language, payload FROM reports "
                "WHERE analysis_id = %s AND assessment_id = %s",
                (analysis_id, assessment["id"]),
            ).fetchone()
            assert report is not None
            assert report["schema_version"] == "report.v1"
            assert report["language"] == "vi"
            assert report["payload"]["risk"]["scoring_version"] == "v0.2.1"
            risk = report["payload"]["risk"]
            if supplier_dimensions:
                pricing = next(item for item in risk["dimensions"] if item["dimension"] == "PRICING")
                assert pricing["risk"] == 25
                stored = next(item for item in report["payload"]["evidence"]
                              if item["evidence_id"] == pricing["evidence_ids"][0])
                assert stored["payload"]["evidence_quotes"] == {"price_information": "12"}
            supported_weight = sum(item["configured_weight"] for item in risk["dimensions"]
                                   if item["risk"] is not None and item["effective_confidence"] > 0)
            assert risk["coverage"] == pytest.approx(min(data["completeness"], supported_weight))
            if risk["coverage"] < 0.45:
                assert risk["label"] == "INSUFFICIENT_INFORMATION"
                assert risk["overall_risk"] is None
            assert report["payload"]["supplier_summary_vi"]
            assert report["payload"]["recommended_actions_vi"]
            assert report["payload"]["limitations_vi"]
            assert report["payload"]["missing_data"]["source_fields"] == data["missing_fields"]
            if data["reviews"]:
                assert any(item["evidence_id"] == "review:0" for item in report["payload"]["evidence"])

            if not azure:
                conn.execute("INSERT INTO local_queue (analysis_id) VALUES (%s)", (analysis_id,))
            else:
                assert conn.execute("SELECT state FROM analysis_outbox WHERE analysis_id = %s", (analysis_id,)).fetchone()["state"] == "PUBLISHED"

        assert process(
            compute=lambda _url: (_ for _ in ()).throw(AssertionError("replay re-extracted")),
            assess=lambda _snapshot: (_ for _ in ()).throw(AssertionError("replay spent AI")),
        )
        assert assessor_calls == 1
        assert provider.chat_calls == expected_chat_calls
        assert provider.embedding_calls == expected_embedding_calls
        assert store.get(analysis_id)["status"] == "COMPLETED"
        assert store.get(analysis_id)["attempt_count"] == 1
        if azure:
            assert queue.receiver.completed == 2
            assert queue.receiver.dead_letters == []
    finally:
        cleanup(store, analysis_id)
        if owner:
            with store.connect() as conn:
                conn.execute("DELETE FROM admission_counters WHERE scope = 'CUSTOMER' AND subject = %s", (str(owner["id"]),))
                conn.execute("DELETE FROM users WHERE id = %s", (owner["id"],))


def test_worker_media_loader_enriches_same_reporting_path_without_persisting_bytes(store):
    data = supplier_data()
    payload = {
        "source_url": SOURCE_URL,
        "extraction_status": "PARTIAL",
        "raw_payload": {"fixture": True},
        "reviews": data["reviews"],
        "supplier_data": data,
    }
    provider = WorkerProvider()
    loader_calls = 0

    def media_loader(_store, _snapshot_id, _supplier_data):
        nonlocal loader_calls
        loader_calls += 1
        return [
            ReviewMediaInput(
                media_id="worker-img-0",
                review_evidence_id="review:0",
                media_type="IMAGE",
                access_status="ACCESSIBLE",
                private_ref="blob://approved/worker/review-0",
                mime_type="image/png",
                data_url="data:image/png;base64,aGVsbG8=",
            )
        ]

    def assessor(snapshot, media):
        return build_assessment(
            snapshot,
            provider=provider,
            model="worker-chat",
            embedding_provider=provider,
            embedding_model="worker-embedding",
            media=media,
            multimodal_provider=provider,
            multimodal_model="worker-vision",
            metadata={"feature": "worker_media_test"},
        )

    analysis_id = store.submit_local(SOURCE_URL)
    try:
        assert process_local_once(
            store,
            compute=lambda _url: payload,
            assess=assessor,
            media_loader=media_loader,
        )
        assert store.get(analysis_id)["status"] == "COMPLETED"
        assert loader_calls == 1
        assert provider.chat_calls == 3
        assert provider.embedding_calls == 1

        with store.connect() as conn:
            assessment = conn.execute(
                "SELECT id, media_analysis FROM analysis_assessments WHERE analysis_id = %s",
                (analysis_id,),
            ).fetchone()
            assert assessment is not None
            assert assessment["media_analysis"]["assessment"]["findings"][0]["consistency"] == "SUPPORTS"
            assert "data:image" not in json.dumps(assessment["media_analysis"])
            runs = conn.execute(
                "SELECT run_kind, input_payload, output FROM llm_review_runs "
                "WHERE assessment_id = %s ORDER BY run_kind",
                (assessment["id"],),
            ).fetchall()
            assert {row["run_kind"] for row in runs} == {
                "SUPPLIER_INTERPRETATION",
                "REVIEW_INTERPRETATION",
                "MEDIA_INTERPRETATION",
            }
            assert all("data:image" not in json.dumps(row["input_payload"]) for row in runs)
            media_evidence = conn.execute(
                "SELECT payload FROM analysis_evidence "
                "WHERE assessment_id = %s AND source_kind = 'REVIEW_MEDIA'",
                (assessment["id"],),
            ).fetchone()
            assert media_evidence is not None
            assert media_evidence["payload"]["private_ref"] == "blob://approved/worker/review-0"
            assert "data:image" not in json.dumps(media_evidence["payload"])
            report = conn.execute(
                "SELECT payload FROM reports WHERE analysis_id = %s",
                (analysis_id,),
            ).fetchone()
            assert report is not None
            assert report["payload"]["schema_version"] == "report.v1"
            assert "data:image" not in json.dumps(report["payload"])
            assert any(
                item["evidence_id"] == "media:worker-img-0"
                for item in report["payload"]["evidence"]
            )
    finally:
        cleanup(store, analysis_id)


def test_reporting_retry_uses_persisted_assessment_without_repeating_ai(store, monkeypatch):
    from backend.app.reporting.service import run_worker_report as real_run_worker_report

    data = supplier_data()
    payload = {
        "source_url": SOURCE_URL,
        "extraction_status": "PARTIAL",
        "raw_payload": {"fixture": True},
        "reviews": data["reviews"],
        "supplier_data": data,
    }
    provider = WorkerProvider()
    assessor_calls = 0

    def assessor(snapshot):
        nonlocal assessor_calls
        assessor_calls += 1
        return build_assessment(
            snapshot,
            provider=provider,
            model="worker-chat",
            embedding_provider=provider,
            embedding_model="worker-embedding",
            metadata={"feature": "report_retry_test"},
        )

    def fail_report(_store, _claim):
        raise RuntimeError("fixture reporting failure")

    analysis_id = store.submit_local(SOURCE_URL)
    try:
        monkeypatch.setattr("backend.worker.main.run_worker_report", fail_report)
        assert process_local_once(
            store,
            compute=lambda _url: payload,
            assess=assessor,
        )
        failed = store.get(analysis_id)
        assert failed["status"] == "FAILED_RETRYABLE"
        assert assessor_calls == 1
        assert provider.chat_calls == 2
        assert provider.embedding_calls == 1

        with store.connect() as conn:
            assert conn.execute(
                "SELECT count(*) AS n FROM analysis_assessments WHERE analysis_id = %s",
                (analysis_id,),
            ).fetchone()["n"] == 1
            assert conn.execute(
                "SELECT count(*) AS n FROM reports WHERE analysis_id = %s",
                (analysis_id,),
            ).fetchone()["n"] == 0
            conn.execute(
                "UPDATE analyses SET next_retry_at = now() WHERE id = %s",
                (analysis_id,),
            )
            conn.execute(
                "UPDATE local_queue SET available_at = now() WHERE analysis_id = %s",
                (analysis_id,),
            )

        monkeypatch.setattr("backend.worker.main.run_worker_report", real_run_worker_report)
        assert process_local_once(
            store,
            compute=lambda _url: (_ for _ in ()).throw(
                AssertionError("report retry re-extracted")
            ),
            assess=lambda _snapshot: (_ for _ in ()).throw(
                AssertionError("report retry repeated AI")
            ),
        )

        assert store.get(analysis_id)["status"] == "COMPLETED"
        assert assessor_calls == 1
        assert provider.chat_calls == 2
        assert provider.embedding_calls == 1
        with store.connect() as conn:
            assert conn.execute(
                "SELECT count(*) AS n FROM reports WHERE analysis_id = %s",
                (analysis_id,),
            ).fetchone()["n"] == 1
    finally:
        cleanup(store, analysis_id)
