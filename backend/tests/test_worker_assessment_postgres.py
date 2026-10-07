from decimal import Decimal
import json
import os

import pytest

from backend.app.intelligence.assessment import build_assessment
from backend.app.intelligence.contracts import SCHEMA_VERSION
from backend.app.intelligence.provider import EmbeddingResponse, ProviderResponse, ProviderUsage
from backend.app.storage import Store
from backend.worker.main import process_local_once


SOURCE_URL = "https://detail.1688.com/offer/996518024136.html"


class WorkerProvider:
    def __init__(self):
        self.chat_calls = 0
        self.embedding_calls = 0

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


def test_worker_reaches_reporting_once_and_replay_spends_no_ai(store):
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
            metadata={"feature": "worker_test"},
        )

    analysis_id = store.submit_local(SOURCE_URL)
    try:
        assert process_local_once(
            store,
            compute=lambda _url: payload,
            assess=assessor,
        )
        row = store.get(analysis_id)
        assert row["status"] == "REPORTING"
        assert assessor_calls == 1
        assert provider.chat_calls == 2
        assert provider.embedding_calls == 1

        with store.connect() as conn:
            assessment = conn.execute(
                "SELECT id, scoring_version, risk_label FROM analysis_assessments "
                "WHERE analysis_id = %s",
                (analysis_id,),
            ).fetchone()
            assert assessment is not None
            assert assessment["scoring_version"] == "v0.1.0"
            assert conn.execute(
                "SELECT count(*) AS n FROM llm_review_runs "
                "WHERE assessment_id = %s",
                (assessment["id"],),
            ).fetchone()["n"] == 2
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

            conn.execute(
                "INSERT INTO local_queue (analysis_id) VALUES (%s)",
                (analysis_id,),
            )

        assert process_local_once(
            store,
            compute=lambda _url: (_ for _ in ()).throw(AssertionError("replay re-extracted")),
            assess=lambda _snapshot: (_ for _ in ()).throw(AssertionError("replay spent AI")),
        )
        assert assessor_calls == 1
        assert provider.chat_calls == 2
        assert provider.embedding_calls == 1
        assert store.get(analysis_id)["status"] == "REPORTING"
    finally:
        cleanup(store, analysis_id)
