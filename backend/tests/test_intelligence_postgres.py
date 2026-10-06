from decimal import Decimal
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from backend.app.extraction.offer1688 import parse_1688_page
from backend.app.intelligence.contracts import SCHEMA_VERSION
from backend.app.intelligence.provider import ProviderResponse, ProviderUsage
from backend.app.intelligence.service import interpret_analysis_snapshot
from backend.app.intelligence.store import get_interpretation_run
from backend.app.storage import Store


class FixtureProvider:
    def generate_json(self, **kwargs):
        output = {
            "schema_version": SCHEMA_VERSION,
            "language": "vi",
            "summary_vi": "Ảnh chụp cung cấp một phần bằng chứng về nhà cung cấp; các trường còn thiếu vẫn cần được xác minh.",
            "positive_signals": [{
                "statement_vi": "Nguồn có tên nhà cung cấp có thể truy vết về ảnh chụp.",
                "evidence_fields": ["supplier_name"],
                "confidence": 0.92,
            }],
            "risk_signals": [],
            "uncertainties": [{
                "statement_vi": "Bằng chứng hiện tại chưa phủ đủ toàn bộ hợp đồng SupplierData.",
                "evidence_fields": ["certifications"],
                "confidence": 0.8,
            }],
            "recommended_verifications": ["Đối chiếu giấy phép kinh doanh trước khi đặt cọc."],
            "confidence": 0.71,
        }
        return ProviderResponse(
            provider="FAKE",
            request_id="fixture-request-3-1",
            requested_model=kwargs["model"],
            response_model="fixture-model-2026-10-06",
            content=json.dumps(output, ensure_ascii=False),
            usage=ProviderUsage(
                prompt_tokens=420,
                completion_tokens=180,
                total_tokens=600,
                cost_usd=Decimal("0.00420000"),
                raw={"prompt_tokens": 420, "completion_tokens": 180, "total_tokens": 600, "cost": "0.0042"},
            ),
            latency_ms=321,
            finish_reason="stop",
            settings={"temperature": 0.1, "max_tokens": 1800, "response_format": {"type": "json_object"}},
        )


@pytest.fixture
def store():
    url = os.getenv("VCT_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set VCT_TEST_DATABASE_URL for PostgreSQL intelligence checks")
    instance = Store(url)
    instance.initialize()
    return instance


def _remove_analysis(store: Store, analysis_id):
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


def test_story_3_1_persists_structured_interpretation_and_full_run_provenance(store):
    source_url = "https://detail.1688.com/offer/996518024136.html"
    html = (Path(__file__).parent / "fixtures" / "1688_offer_996518024136.html").read_text(encoding="utf-8")
    payload = parse_1688_page(html, source_url, analysis_mode="GUEST_PUBLIC")
    analysis_id = store.submit_local(source_url)
    try:
        claim = store.claim_processing(analysis_id, 60, 3)
        store.complete_processing(analysis_id, claim["token"], payload)
        run_id, run = interpret_analysis_snapshot(
            store, analysis_id, provider=FixtureProvider(), model="fixture-candidate",
        )
        stored = get_interpretation_run(store, run_id)
        assert stored is not None
        assert stored["analysis_id"] == analysis_id
        assert stored["supplier_snapshot_id"] == store.get(analysis_id)["supplier_snapshot_id"]
        assert stored["provider"] == "FAKE"
        assert stored["provider_request_id"] == "fixture-request-3-1"
        assert stored["model"] == "fixture-candidate"
        assert stored["model_version"] == "fixture-model-2026-10-06"
        assert stored["prompt_version"] == run.prompt_version
        assert stored["pipeline_version"] == run.pipeline_version
        assert stored["schema_version"] == SCHEMA_VERSION
        assert stored["input_payload"]["platform"] == "1688"
        assert stored["output"]["language"] == "vi"
        assert float(stored["confidence"]) == pytest.approx(0.71)
        assert stored["prompt_tokens"] == 420
        assert stored["completion_tokens"] == 180
        assert stored["total_tokens"] == 600
        assert stored["cost_usd"] == Decimal("0.00420000")
        assert stored["cost_status"] == "REPORTED"
        assert stored["latency_ms"] == 321
        assert stored["raw_usage"]["total_tokens"] == 600
        assert len(stored["input_sha256"]) == 64
    finally:
        _remove_analysis(store, analysis_id)


def test_provider_request_id_is_unique_for_audit_reconciliation(store):
    # The DB constraint prevents two persisted runs from claiming the same provider request.
    with store.connect() as conn:
        index = conn.execute(
            "SELECT indexname FROM pg_indexes WHERE schemaname = current_schema() "
            "AND tablename = 'llm_review_runs' AND indexname = 'llm_review_runs_provider_request_id_key'"
        ).fetchone()
    assert index is not None

