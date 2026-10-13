"""Regressions for narrative evidence being omitted from dimension scoring."""
import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.app.intelligence.assessment import build_assessment
from backend.app.intelligence.assessment_policy import merge_dimension_inputs, supplier_score_inputs
from backend.app.intelligence.contracts import SupplierInterpretation
from backend.app.intelligence.interpretation import interpret_supplier_data
from backend.app.intelligence.scoring import DimensionInput, RiskSignal
from backend.app.reporting.builder import build_report
from backend.tests.test_complete_assessment import supplier_fixture
from backend.tests.test_intelligence import FakeProvider, valid_output


def assessment(dimension="DELIVERY", severity="MEDIUM", field="delivery_information", quote="Late deliveries"):
    return dict(dimension=dimension, severity=severity, statement_vi="Cần xác minh giao hàng.",
                evidence_fields=[field], evidence_quotes={field: quote}, confidence=0.8)


def provider_with(*items):
    return FakeProvider(valid_output() | {"dimension_assessments": list(items)})


def test_captured_supplier_evidence_scores_without_embeddings_and_keeps_missing_unknown():
    data = supplier_fixture() | {"price_information": {"display_text": "CNY 8.70; minimum order 1 piece"}}
    bundle = build_assessment(data, provider=provider_with(assessment("PRICING", "MEDIUM", "price_information", "CNY 8.70; minimum order 1 piece")), model="fixture")
    delivery = next(item for item in bundle.risk.dimensions if item.dimension == "PRICING")
    assert delivery.risk == 55
    assert delivery.base_confidence == 0.7
    assert "PRICING" not in bundle.risk.missing_dimensions
    assert "SUPPLIER_IDENTITY" in bundle.risk.missing_dimensions
    assert len(bundle.risk.dimensions) == 5
    assert bundle.risk.scoring_version == "v0.2.1"
    # A single supported category must not turn the overall supplier into low risk.
    assert bundle.risk.label == "INSUFFICIENT_INFORMATION"
    assert bundle.risk.overall_risk is None
    evidence = {item["evidence_id"]: item for item in bundle.evidence}
    assert evidence[delivery.evidence_ids[0]]["payload"]["evidence_quotes"] == {
        "price_information": "CNY 8.70; minimum order 1 piece"}
    assert evidence[delivery.evidence_ids[0]]["payload"]["independently_verified"] is False
    report = build_report(analysis_id="dimension-regression", source_url=data["source_url"],
        snapshot={"normalized_data": data},
        assessment={"risk_assessment": bundle.risk.model_dump(mode="json"),
                    "supplier_interpretation": bundle.supplier_run.interpretation.model_dump(mode="json")},
        findings=bundle.findings, evidence=bundle.evidence, raw_reviews=data["reviews"])
    projected = next(item for item in report.risk.dimensions if item["dimension"] == "PRICING")
    assert projected["risk"] == 55
    assert any(item.evidence_id == projected["evidence_ids"][0] for item in report.evidence)


@pytest.mark.parametrize("item", [
    assessment(severity="UNKNOWN"),
    assessment(quote="Invented delivery fact"),
    assessment(field="certifications", quote="ISO 9001"),
    assessment(field="supplier_name", quote="Fixture Supplier"),
    assessment() | {"confidence": 0},
])
def test_missing_ambiguous_uncited_or_irrelevant_evidence_does_not_get_a_score(item):
    data = supplier_fixture() | {"delivery_information": {"note": "Late deliveries"}}
    run = interpret_supplier_data(data, provider=provider_with(item), model="fixture")
    assert supplier_score_inputs(run) == ([], [])


def test_one_review_does_not_generalize_quality_and_old_outputs_remain_readable():
    data = supplier_fixture() | {"reviews": [{"text": "Excellent"}]}
    item = assessment("PRODUCT_QUALITY", "LOW", "reviews", "Excellent")
    run = interpret_supplier_data(data, provider=provider_with(item), model="fixture")
    assert supplier_score_inputs(run) == ([], [])
    assert SupplierInterpretation.model_validate(valid_output()).dimension_assessments == []


def test_company_claims_and_model_authenticity_claims_cannot_bypass_specialist_modules():
    data = supplier_fixture()
    identity = assessment("SUPPLIER_IDENTITY", "MEDIUM", "company_information", "Manufacturer")
    authenticity = assessment("REVIEW_MANIPULATION", "HIGH", "reviews", "Poor quality stitching")
    run = interpret_supplier_data(data, provider=provider_with(identity, authenticity), model="fixture")
    assert supplier_score_inputs(run) == ([], [])


def test_metric_quote_needs_its_value_and_category_merge_does_not_double_count_reviews():
    data = supplier_fixture()
    metric = {"label": "Overall fulfillment rate", "scope": "SUPPLIER_PLATFORM", "value": "45%"}
    data["transaction_signals"] = {"source_metrics": [metric]}
    item = assessment("DELIVERY", "MEDIUM", "transaction_signals", metric["label"])
    run = interpret_supplier_data(data, provider=provider_with(item), model="fixture")
    assert supplier_score_inputs(run) == ([], [])
    item["evidence_quotes"]["transaction_signals"] = json.dumps(metric, sort_keys=True, separators=(",", ":"))
    run = interpret_supplier_data(data, provider=provider_with(item), model="fixture")
    assert supplier_score_inputs(run)[0][0].signals[0].severity == 55
    # Equivalent JSON objects from providers preserve the full quoted fact.
    item["evidence_quotes"]["transaction_signals"] = metric
    run = interpret_supplier_data(data, provider=provider_with(item), model="fixture")
    assert supplier_score_inputs(run)[0][0].signals[0].severity == 55


def test_unquoted_context_is_removed_without_adding_new_model_references():
    item = assessment() | {"evidence_fields": ["delivery_information", "products"],
        "evidence_quotes": {"delivery_information": "Late deliveries", "rating": "4.2"}}
    output = SupplierInterpretation.model_validate(valid_output() | {"dimension_assessments": [item]})
    kept = output.dimension_assessments[0]
    assert kept.evidence_fields == ["delivery_information"]
    assert kept.evidence_quotes == {"delivery_information": "Late deliveries"}


def test_null_quotes_for_missing_fields_preserve_uncertainty_and_cannot_score():
    output = valid_output()
    output["uncertainties"][0]["evidence_quotes"] = {"certifications": None}
    output["dimension_assessments"] = [assessment() | {
        "evidence_quotes": {"delivery_information": None}}]
    provider = FakeProvider(output)
    run = interpret_supplier_data(supplier_fixture(), provider=provider, model="fixture")
    assert len(provider.calls) == 1
    assert run.interpretation.uncertainties[0].evidence_quotes == {}
    assert run.interpretation.uncertainties[0].evidence_fields == ["certifications"]
    assert run.interpretation.dimension_assessments[0].severity == "UNKNOWN"
    assert supplier_score_inputs(run) == ([], [])


def test_live_sparse_phone_shape_completes_with_grouped_null_uncertainty_quotes():
    data = supplier_fixture()
    missing = ["company_information", "years_active", "categories", "certifications",
               "price_information", "transaction_signals", "rating", "delivery_information", "activity_history"]
    data.update({field: None for field in missing})
    data.update(completeness=0.25, missing_fields=missing, extraction_method="USER_UPLOAD")
    output = valid_output() | {
        "positive_signals": [], "risk_signals": [],
        "uncertainties": [{"statement_vi": "Một số nguồn chưa có dữ liệu.",
            "evidence_fields": missing, "evidence_quotes": dict.fromkeys(missing), "confidence": 0.7}],
        "dimension_assessments": [assessment("PRODUCT_QUALITY", "MEDIUM", "reviews", "Poor quality stitching")],
    }
    provider = FakeProvider(output)
    bundle = build_assessment(data, provider=provider, model="fixture")
    assert len(provider.calls) == 1
    assert bundle.supplier_run.interpretation.uncertainties[0].evidence_quotes == {}
    quality = next(item for item in bundle.risk.dimensions if item.dimension == "PRODUCT_QUALITY")
    assert quality.risk == 55
    assert bundle.risk.overall_risk is None
    assert bundle.risk.label == "INSUFFICIENT_INFORMATION"


def test_ambiguous_translated_return_metric_cannot_become_product_quality_risk():
    data = supplier_fixture()
    metric = {"label": "Store return rate", "scope": "SUPPLIER_PLATFORM", "value": "27%"}
    data["transaction_signals"] = {"source_metrics": [metric]}
    item = assessment("PRODUCT_QUALITY", "HIGH", "transaction_signals", json.dumps(metric, sort_keys=True))
    run = interpret_supplier_data(data, provider=provider_with(item), model="fixture")
    assert supplier_score_inputs(run) == ([], [])


def test_duplicate_or_arbitrary_categories_rejected():
    with pytest.raises(ValidationError):
        SupplierInterpretation.model_validate(valid_output() | {
            "dimension_assessments": [assessment(), assessment()]})
    with pytest.raises(ValidationError):
        SupplierInterpretation.model_validate(valid_output() | {
            "dimension_assessments": [assessment() | {"severity": "SAFE"}]})
    unsupported = SupplierInterpretation.model_validate(valid_output() | {
        "dimension_assessments": [assessment() | {"evidence_quotes": {}}]})
    assert unsupported.dimension_assessments[0].severity == "UNKNOWN"


def test_merge_preserves_independent_existing_signals_and_weights_confidence():
    def dimension(evidence_id, confidence, severity):
        return DimensionInput(dimension="DELIVERY", confidence=confidence, signals=[RiskSignal(
            evidence_id=evidence_id, dimension="DELIVERY", severity=severity,
            reliability=confidence, source_kind="REVIEW", explanation="Delivery evidence")])
    merged = merge_dimension_inputs([dimension("review:0", 0.9, 80), dimension("supplier:d", 0.6, 25)])
    assert len(merged) == 1
    assert [item.evidence_id for item in merged[0].signals] == ["review:0", "supplier:d"]
    assert merged[0].confidence == pytest.approx(0.78)


def test_prompt_requests_categories_quotes_and_ambiguous_metric_caution():
    provider = provider_with(assessment())
    interpret_supplier_data(supplier_fixture(), provider=provider, model="fixture")
    prompt = provider.calls[0]["system_prompt"]
    assert "dimension_assessments" in prompt and "repeat-purchase rate" in prompt
    assert "evidence_quotes" in json.loads(
        provider.calls[0]["user_prompt"].split("OUTPUT_SCHEMA:\n")[1].split("\n\nSUPPLIER_DATA:")[0]
    )["$defs"]["SupplierDimensionAssessment"]["properties"]


def test_structural_repair_is_bounded_strict_and_accounts_for_both_requests():
    invalid = valid_output()
    invalid["recommended_verifications"] = [{"statement_vi": "Yêu cầu mẫu hàng."}]

    class RepairProvider(FakeProvider):
        def generate_json(self, **kwargs):
            self.output = invalid if not self.calls else valid_output()
            return super().generate_json(**kwargs)

    provider = RepairProvider()
    run = interpret_supplier_data(supplier_fixture(), provider=provider, model="fixture")
    assert len(provider.calls) == 2
    assert "STRUCTURAL_REPAIR" in provider.calls[1]["user_prompt"]
    assert run.provider_response.usage.total_tokens == 910
    assert run.provider_response.usage.cost_usd == Decimal("0.002468")
    assert run.provider_response.latency_ms == 240
    assert run.provider_response.settings["schema_repair"]["attempts"] == 1
    assert "statement_vi" in run.provider_response.settings["schema_repair"]["original_output"]

    always_invalid = FakeProvider(invalid)
    with pytest.raises(ValueError, match="failed the supplier interpretation schema"):
        interpret_supplier_data(supplier_fixture(), provider=always_invalid, model="fixture")
    assert len(always_invalid.calls) == 2
