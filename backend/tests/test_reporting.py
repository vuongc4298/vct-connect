from backend.app.reporting.builder import build_report
from backend.app.reporting.contracts import REPORT_SCHEMA_VERSION


def source_fixture(*, insufficient=False):
    risk = {
        "schema_version": "supplier-risk.v0.1",
        "scoring_version": "v0.1.0",
        "overall_risk": None if insufficient else 58.0,
        "confidence": 0.35 if insufficient else 0.72,
        "data_coverage": 0.40 if insufficient else 0.75,
        "label": "INSUFFICIENT_INFORMATION" if insufficient else "MODERATE",
        "dimensions": [
            {
                "dimension": "PRODUCT_QUALITY",
                "configured_weight": 0.25,
                "risk": 70.0,
                "base_confidence": 0.8,
                "effective_confidence": 0.8,
                "review_derived_share": 1.0,
                "review_manipulation_adjustment": 0.0,
                "evidence_ids": ["review-finding:quality"],
            }
        ],
        "critical_floor": None,
        "critical_evidence_ids": [],
        "missing_dimensions": ["DELIVERY", "AFTER_SALES"],
    }
    assessment = {
        "id": "assessment-1",
        "scoring_version": "v0.1.0",
        "supplier_interpretation": {
            "schema_version": "supplier-interpretation.v1",
            "language": "vi",
            "summary_vi": "Nhà cung cấp có một số bằng chứng tích cực nhưng còn thiếu dữ liệu cần xác minh.",
            "positive_signals": [],
            "risk_signals": [],
            "uncertainties": [
                {
                    "statement_vi": "Chưa có chứng nhận được xác minh.",
                    "evidence_fields": ["certifications"],
                    "confidence": 0.8,
                }
            ],
            "recommended_verifications": [],
            "confidence": 0.75,
        },
        "review_analysis": {
            "mode": "semantic",
            "assessment": {
                "confidence": 0.8,
                "review_reliability": 0.7,
                "findings": [],
                "suspicious_patterns": [],
            },
        },
        "identity_assessment": {
            "schema_version": "factory-trader-assessment.v1",
            "factory_likelihood": 0.6,
            "trader_likelihood": 0.2,
            "confidence": 0.55,
            "classification": "UNCERTAIN",
            "supporting_evidence": [
                {
                    "evidence_id": "identity:business_type",
                    "direction": "FACTORY",
                    "strength": 0.6,
                    "reliability": 0.5,
                    "source_kind": "PLATFORM_PROFILE",
                    "source_field": "company_information.business_type",
                    "statement": "Manufacturer",
                }
            ],
            "uncertainty_reasons": ["self_claim_only"],
            "supplier_risk_penalty": 0,
        },
        "risk_assessment": risk,
    }
    snapshot = {
        "normalized_data": {
            "platform": "1688",
            "source_url": "https://detail.1688.com/offer/996518024136.html",
            "extracted_at": "2026-10-07T00:00:00+00:00",
            "supplier_name": "Fixture Supplier",
            "platform_supplier_id": "supplier-1",
        },
        "missing_fields": ["certifications", "delivery_information"],
    }
    findings = [
        {
            "finding_key": "supplier_positive:0",
            "finding_type": "SUPPLIER_POSITIVE",
            "dimension": None,
            "severity": None,
            "confidence": 0.8,
            "payload": {
                "statement_vi": "Có thông tin hoạt động nhiều năm.",
                "evidence_fields": ["years_active"],
                "confidence": 0.8,
            },
        },
        {
            "finding_key": "review:0:QUALITY:review:0",
            "finding_type": "REVIEW_FINDING",
            "dimension": "PRODUCT_QUALITY",
            "severity": 80.0,
            "confidence": 0.9,
            "payload": {
                "category": "QUALITY",
                "severity": "HIGH",
                "statement_vi": "Đánh giá mô tả lỗi chất lượng.",
                "evidence_ids": ["review:0"],
                "confidence": 0.9,
            },
        },
        {
            "finding_key": "identity:assessment",
            "finding_type": "IDENTITY_ASSESSMENT",
            "dimension": "SUPPLIER_IDENTITY",
            "severity": None,
            "confidence": 0.55,
            "payload": assessment["identity_assessment"],
        },
    ]
    evidence = [
        {
            "evidence_id": "supplier:years_active",
            "source_kind": "SUPPLIER_DATA",
            "source_field": "years_active",
            "payload": {"field": "years_active"},
        },
        {
            "evidence_id": "identity:business_type",
            "source_kind": "PLATFORM_PROFILE",
            "source_field": "company_information.business_type",
            "payload": {"statement": "Manufacturer"},
        },
    ]
    raw_reviews = [
        {
            "ordinal": 0,
            "payload": {
                "text": "Poor quality stitching",
                "source_url": "https://example.test/r1",
            },
        }
    ]
    return assessment, snapshot, findings, evidence, raw_reviews


def test_report_v1_keeps_risk_confidence_coverage_evidence_and_actions_separate():
    assessment, snapshot, findings, evidence, reviews = source_fixture()
    report = build_report(
        analysis_id="analysis-1",
        source_url=snapshot["normalized_data"]["source_url"],
        snapshot=snapshot,
        assessment=assessment,
        findings=findings,
        evidence=evidence,
        raw_reviews=reviews,
    )

    assert report.schema_version == REPORT_SCHEMA_VERSION
    assert report.language == "vi"
    assert report.risk.overall_risk == 58.0
    assert report.risk.label == "MODERATE"
    assert report.risk.confidence == 0.72
    assert report.risk.coverage == 0.75
    assert report.risk.scoring_version == "v0.1.0"
    assert report.key_risks[0].finding_type == "REVIEW_FINDING"
    assert report.key_risks[0].evidence_ids == ["review:0"]
    assert report.positive_signals[0].evidence_ids == ["supplier:years_active"]
    assert {item.evidence_id for item in report.evidence} >= {
        "review:0", "supplier:years_active", "identity:business_type"
    }
    assert report.missing_data["source_fields"] == [
        "certifications", "delivery_information"
    ]
    assert report.missing_data["risk_dimensions"] == ["DELIVERY", "AFTER_SALES"]
    assert report.recommended_actions_vi
    assert report.limitations_vi


def test_insufficient_information_is_explicit_and_never_rendered_as_low_risk():
    assessment, snapshot, findings, evidence, reviews = source_fixture(insufficient=True)
    report = build_report(
        analysis_id="analysis-2",
        source_url=snapshot["normalized_data"]["source_url"],
        snapshot=snapshot,
        assessment=assessment,
        findings=findings,
        evidence=evidence,
        raw_reviews=reviews,
    )

    assert report.risk.overall_risk is None
    assert report.risk.label == "INSUFFICIENT_INFORMATION"
    assert report.risk.confidence == 0.35
    assert report.risk.coverage == 0.40
    assert any("không được diễn giải" in item for item in report.limitations_vi)
    assert any("Bổ sung bằng chứng" in item for item in report.recommended_actions_vi)
