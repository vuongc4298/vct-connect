from decimal import Decimal
import json

import pytest

from backend.app.intelligence.assessment import build_assessment
from backend.app.intelligence.contracts import SCHEMA_VERSION
from backend.app.intelligence.media import MEDIA_SCHEMA_VERSION, ReviewMediaInput
from backend.app.intelligence.provider import ProviderResponse, ProviderUsage


PNG_DATA = "data:image/png;base64,aGVsbG8="


class FixtureProvider:
    def __init__(self, *, media_consistency="CONTRADICTS"):
        self.chat_calls = 0
        self.media_calls = 0
        self.media_consistency = media_consistency

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
                        "statement_vi": "Đánh giá đầu tiên mô tả lỗi chất lượng nghiêm trọng.",
                        "evidence_ids": ["review:0"],
                        "confidence": 1.0,
                    },
                    {
                        "category": "QUALITY",
                        "severity": "LOW",
                        "statement_vi": "Đánh giá thứ hai mô tả vấn đề chất lượng nhẹ.",
                        "evidence_ids": ["review:1"],
                        "confidence": 1.0,
                    },
                ],
                "confidence": 0.9,
            }
        else:
            output = {
                "schema_version": SCHEMA_VERSION,
                "language": "vi",
                "summary_vi": "Bằng chứng nhà cung cấp còn hạn chế.",
                "positive_signals": [],
                "risk_signals": [],
                "uncertainties": [{
                    "statement_vi": "Một số trường cần xác minh thêm.",
                    "evidence_fields": ["certifications"],
                    "confidence": 0.7,
                }],
                "recommended_verifications": ["Xác minh tài liệu."],
                "confidence": 0.8,
            }
        return ProviderResponse(
            provider="FAKE",
            request_id=f"chat-{self.chat_calls}",
            requested_model=kwargs["model"],
            response_model="fixture-chat-v1",
            content=json.dumps(output, ensure_ascii=False),
            usage=ProviderUsage(100, 50, 150, Decimal("0.001"), {"total_tokens": 150}),
            latency_ms=10,
            finish_reason="stop",
            settings={"temperature": kwargs["temperature"], "max_tokens": kwargs["max_tokens"]},
        )

    def generate_multimodal_json(self, **kwargs):
        self.media_calls += 1
        output = {
            "schema_version": MEDIA_SCHEMA_VERSION,
            "language": "vi",
            "findings": [{
                "media_id": "img-review-0",
                "review_evidence_id": "review:0",
                "consistency": self.media_consistency,
                "statement_vi": "Hình ảnh không nhất quán với mô tả lỗi nghiêm trọng." if self.media_consistency == "CONTRADICTS" else "Hình ảnh hỗ trợ mô tả đánh giá.",
                "confidence": 1.0,
                "timestamp_ms": None,
            }],
            "confidence": 0.9,
        }
        return ProviderResponse(
            provider="FAKE",
            request_id=f"media-{self.media_calls}",
            requested_model=kwargs["model"],
            response_model="fixture-vision-v1",
            content=json.dumps(output, ensure_ascii=False),
            usage=ProviderUsage(80, 30, 110, Decimal("0.002"), {"total_tokens": 110}),
            latency_ms=15,
            finish_reason="stop",
            settings={"temperature": kwargs["temperature"], "max_tokens": kwargs["max_tokens"]},
        )


def supplier_fixture():
    denominator = [
        "supplier_name", "company_information", "years_active", "categories",
        "certifications", "products", "price_information", "transaction_signals",
        "rating", "reviews", "delivery_information", "activity_history",
    ]
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
        "completeness_denominator": denominator,
        "missing_fields": ["certifications", "delivery_information", "activity_history"],
        "platform_supplier_id": "supplier-media",
        "supplier_name": "Fixture Supplier",
        "company_information": {"business_type": "Manufacturer"},
        "years_active": 5,
        "categories": ["bags"],
        "certifications": None,
        "products": [{"title": "Bag"}],
        "price_information": {"min": 10},
        "transaction_signals": {"review_count": 12},
        "rating": 4.0,
        "reviews": [
            {"text": "Severe stitching failure", "source_url": "https://example.test/r1"},
            {"text": "Minor loose thread", "source_url": "https://example.test/r2"},
        ],
        "delivery_information": None,
        "activity_history": None,
    }


def media_fixture():
    return [
        ReviewMediaInput(
            media_id="img-review-0",
            review_evidence_id="review:0",
            media_type="IMAGE",
            access_status="ACCESSIBLE",
            private_ref="blob://approved/review-0/image-1",
            mime_type="image/png",
            data_url=PNG_DATA,
        )
    ]


def quality_risk(bundle):
    return next(
        dimension.risk
        for dimension in bundle.risk.dimensions
        if dimension.dimension == "PRODUCT_QUALITY"
    )


def test_contradicting_permitted_media_reduces_review_derived_quality_risk_weight():
    baseline_provider = FixtureProvider()
    baseline = build_assessment(
        supplier_fixture(),
        provider=baseline_provider,
        model="fixture-chat",
    )

    media_provider = FixtureProvider(media_consistency="CONTRADICTS")
    enriched = build_assessment(
        supplier_fixture(),
        provider=media_provider,
        model="fixture-chat",
        media=media_fixture(),
        multimodal_provider=media_provider,
        multimodal_model="fixture-vision",
    )

    assert quality_risk(baseline) == pytest.approx(52.5)
    assert quality_risk(enriched) < quality_risk(baseline)
    assert quality_risk(enriched) == pytest.approx((80 * 0.5 + 25) / 1.5)
    assert enriched.media_run is not None
    assert media_provider.media_calls == 1
    assert any(f["finding_type"] == "MEDIA_CONSISTENCY" for f in enriched.findings)
    assert any(e["source_kind"] == "REVIEW_MEDIA" for e in enriched.evidence)


def test_text_only_assessment_never_invokes_multimodal_provider():
    provider = FixtureProvider()
    bundle = build_assessment(
        supplier_fixture(),
        provider=provider,
        model="fixture-chat",
    )
    assert bundle.media_run is None
    assert provider.media_calls == 0


def test_multimodal_run_keeps_raw_media_out_of_persistable_payload():
    provider = FixtureProvider()
    bundle = build_assessment(
        supplier_fixture(),
        provider=provider,
        model="fixture-chat",
        media=media_fixture(),
        multimodal_provider=provider,
        multimodal_model="fixture-vision",
    )
    serialized = json.dumps(bundle.media_run.input_payload)
    assert "data:image" not in serialized
    assert "aGVsbG8=" not in serialized
    provenance = bundle.media_run.assessment.provenance[0]
    assert provenance.private_ref == "blob://approved/review-0/image-1"
    assert provenance.content_sha256 is not None


def test_media_requires_review_linkage_and_provider_capability():
    provider = FixtureProvider()
    bad = [
        ReviewMediaInput(
            media_id="img-orphan",
            review_evidence_id="review:99",
            media_type="IMAGE",
            access_status="ACCESSIBLE",
            private_ref="blob://approved/orphan",
            mime_type="image/png",
            data_url=PNG_DATA,
        )
    ]
    with pytest.raises(ValueError, match="unknown review evidence"):
        build_assessment(
            supplier_fixture(),
            provider=provider,
            model="fixture-chat",
            media=bad,
            multimodal_provider=provider,
            multimodal_model="fixture-vision",
        )
    with pytest.raises(ValueError, match="multimodal provider/model"):
        build_assessment(
            supplier_fixture(),
            provider=provider,
            model="fixture-chat",
            media=media_fixture(),
        )
