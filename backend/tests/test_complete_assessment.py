from decimal import Decimal
import json

from backend.app.intelligence.assessment import build_assessment
from backend.app.intelligence.contracts import SCHEMA_VERSION
from backend.app.intelligence.provider import (
    EmbeddingResponse,
    ProviderResponse,
    ProviderUsage,
)


class FakeProvider:
    def __init__(self):
        self.chat_calls = 0
        self.embedding_calls = 0

    def generate_json(self, **kwargs):
        self.chat_calls += 1
        if "review-evidence interpretation" in kwargs["system_prompt"]:
            output = {
                "schema_version": "review-interpretation.v1",
                "language": "vi",
                "findings": [
                    {
                        "category": "QUALITY",
                        "severity": "HIGH",
                        "statement_vi": "Hai đánh giá mô tả chất lượng sản phẩm kém.",
                        "evidence_ids": ["review:0", "review:1"],
                        "confidence": 0.9,
                    }
                ],
                "confidence": 0.85,
            }
            model = "fixture-review-v1"
        else:
            output = {
                "schema_version": SCHEMA_VERSION,
                "language": "vi",
                "summary_vi": "Dữ liệu cung cấp bằng chứng một phần về nhà cung cấp.",
                "positive_signals": [],
                "risk_signals": [],
                "uncertainties": [{
                    "statement_vi": "Một số trường vẫn cần xác minh.",
                    "evidence_fields": ["certifications"],
                    "confidence": 0.7,
                }],
                "recommended_verifications": ["Xác minh giấy phép kinh doanh."],
                "confidence": 0.8,
            }
            model = "fixture-supplier-v1"
        return ProviderResponse(
            provider="FAKE",
            request_id=f"chat-{self.chat_calls}",
            requested_model=kwargs["model"],
            response_model=model,
            content=json.dumps(output, ensure_ascii=False),
            usage=ProviderUsage(
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                cost_usd=Decimal("0.001"),
                raw={"total_tokens": 150},
            ),
            latency_ms=25,
            finish_reason="stop",
            settings={"temperature": kwargs["temperature"], "max_tokens": kwargs["max_tokens"]},
        )

    def embed_texts(self, **kwargs):
        self.embedding_calls += 1
        vectors = tuple(
            (1.0, 0.0) if index < 2 else (0.0, 1.0)
            for index, _ in enumerate(kwargs["texts"])
        )
        return EmbeddingResponse(
            provider="FAKE",
            request_id=f"embed-{self.embedding_calls}",
            requested_model=kwargs["model"],
            response_model="fixture-embedding-v1",
            vectors=vectors,
            usage=ProviderUsage(
                prompt_tokens=20,
                completion_tokens=0,
                total_tokens=20,
                cost_usd=Decimal("0.0002"),
                raw={"total_tokens": 20},
            ),
            latency_ms=10,
            settings={"encoding_format": "float"},
        )


def supplier_fixture():
    return {
        "contract_version": "supplierdata.v1",
        "platform": "1688",
        "source_url": "https://detail.1688.com/offer/996518024136.html",
        "offer_id": "996518024136",
        "extracted_at": "2026-10-07T00:00:00+00:00",
        "extraction_method": "PUBLIC_HTTP",
        "analysis_mode": "GUEST_PUBLIC",
        "extractor_version": "fixture",
        "completeness": 0.75,
        "completeness_denominator": [
            "supplier_name", "company_information", "years_active", "categories",
            "certifications", "products", "price_information", "transaction_signals",
            "rating", "reviews", "delivery_information", "activity_history",
        ],
        "missing_fields": ["certifications", "activity_history", "delivery_information"],
        "platform_supplier_id": "supplier-1",
        "supplier_name": "Fixture Supplier",
        "company_information": {
            "business_type": "Manufacturer",
            "factory_area_sqm": 2000,
            "production_line_count": 3,
        },
        "years_active": 6,
        "categories": ["bags"],
        "certifications": None,
        "products": [{"title": "Bag"}],
        "price_information": {"min": 10},
        "transaction_signals": {"review_count": 20},
        "rating": 4.2,
        "reviews": [
            {"text": "Poor quality stitching", "source_url": "https://example.test/r1"},
            {"text": "Stitching quality is poor", "source_url": "https://example.test/r2"},
        ],
        "delivery_information": None,
        "activity_history": None,
    }


def test_complete_assessment_composes_review_identity_and_versioned_score():
    provider = FakeProvider()
    bundle = build_assessment(
        supplier_fixture(),
        provider=provider,
        model="fixture-chat",
        embedding_provider=provider,
        embedding_model="fixture-embedding",
        metadata={"feature": "complete_assessment"},
    )
    assert provider.chat_calls == 2
    assert provider.embedding_calls == 1
    assert bundle.risk.scoring_version == "v0.1.0"
    assert bundle.risk.data_coverage == 0.75
    assert bundle.identity.supplier_risk_penalty == 0
    assert bundle.review_analysis.assessment.findings[0].category == "QUALITY"
    assert any(finding["finding_type"] == "REVIEW_FINDING" for finding in bundle.findings)
    assert any(finding["finding_type"] == "IDENTITY_ASSESSMENT" for finding in bundle.findings)
    assert any(item["source_kind"] == "REVIEW" for item in bundle.evidence)


def test_missing_embedding_model_degrades_to_deterministic_review_without_second_llm_call():
    provider = FakeProvider()
    bundle = build_assessment(
        supplier_fixture(),
        provider=provider,
        model="fixture-chat",
        embedding_provider=None,
        embedding_model=None,
    )
    assert provider.chat_calls == 1
    assert provider.embedding_calls == 0
    assert bundle.risk.scoring_version == "v0.1.0"
    assert hasattr(bundle.review_analysis, "suspicious_patterns")


def test_recurring_complaint_topics_are_persistable_findings_but_not_new_risk_signals():
    provider = FakeProvider()
    fixture = supplier_fixture()
    fixture["reviews"] = [
        {"text": "Poor quality stitching", "source_url": "https://example.test/r1"},
        {"text": "Poor quality and poor stitching", "source_url": "https://example.test/r2"},
    ]
    bundle = build_assessment(
        fixture,
        provider=provider,
        model="fixture-chat",
        embedding_provider=None,
        embedding_model=None,
    )
    topic = next(
        finding
        for finding in bundle.findings
        if finding["finding_type"] == "REVIEW_COMPLAINT_TOPIC"
    )
    assert topic["payload"]["category"] == "QUALITY"
    assert topic["payload"]["evidence_ids"] == ["review:0", "review:1"]
    assert topic["severity"] is None
    quality = next(
        dimension
        for dimension in bundle.risk.dimensions
        if dimension.dimension == "PRODUCT_QUALITY"
    )
    assert quality.risk is None
    assert "PRODUCT_QUALITY" in bundle.risk.missing_dimensions
    assert bundle.risk.scoring_version == "v0.1.0"
