import pytest

from backend.app.intelligence.identity import (
    IDENTITY_SCHEMA_VERSION,
    IdentityEvidence,
    aggregate_identity_evidence,
    assess_supplier_identity,
    supplier_identity_evidence,
)


def test_strong_independent_factory_evidence_becomes_factory_likely():
    result = aggregate_identity_evidence([
        IdentityEvidence(
            evidence_id="factory-area",
            source_field="company_information.factory_area_sqm",
            direction="FACTORY",
            strength=0.85,
            reliability=0.9,
            source_kind="PLATFORM_PROFILE",
            statement="Factory area is independently present.",
            value=5000,
        ),
        IdentityEvidence(
            evidence_id="production-lines",
            source_field="company_information.production_line_count",
            direction="FACTORY",
            strength=0.95,
            reliability=0.9,
            source_kind="PLATFORM_PROFILE",
            statement="Production-line count is present.",
            value=8,
        ),
        IdentityEvidence(
            evidence_id="qc-staff",
            source_field="company_information.qc_staff_count",
            direction="FACTORY",
            strength=0.6,
            reliability=0.8,
            source_kind="PLATFORM_PROFILE",
            statement="QC staffing is present.",
            value=12,
        ),
        IdentityEvidence(
            evidence_id="document",
            source_field="verified_document.business_scope",
            direction="FACTORY",
            strength=0.8,
            reliability=0.95,
            source_kind="DOCUMENT",
            statement="Verified business-scope document supports manufacturing activity.",
            value="manufacturing",
        ),
    ])
    assert result.schema_version == IDENTITY_SCHEMA_VERSION
    assert result.classification == "FACTORY_LIKELY"
    assert result.factory_likelihood > 0.95
    assert result.confidence >= 0.8
    assert result.supplier_risk_penalty == 0


def test_strong_trader_evidence_does_not_create_supplier_risk_penalty():
    result = aggregate_identity_evidence([
        {
            "evidence_id": "trade-license",
            "source_field": "verified_document.business_scope",
            "direction": "TRADER",
            "strength": 0.9,
            "reliability": 0.95,
            "source_kind": "DOCUMENT",
            "statement": "Verified scope describes trading activity.",
            "value": "trading",
        },
        {
            "evidence_id": "platform-type",
            "source_field": "company_information.business_type",
            "direction": "TRADER",
            "strength": 0.8,
            "reliability": 0.75,
            "source_kind": "PLATFORM_PROFILE",
            "statement": "Platform profile classifies the business as a trader.",
            "value": "Trading Company",
        },
        {
            "evidence_id": "derived-wholesale",
            "source_field": "identity_profile.wholesale_only",
            "direction": "TRADER",
            "strength": 0.5,
            "reliability": 0.7,
            "source_kind": "DERIVED",
            "statement": "Independent identity profile supports wholesale activity.",
            "value": True,
        },
        {
            "evidence_id": "registry",
            "source_field": "verified_document.registration",
            "direction": "TRADER",
            "strength": 0.7,
            "reliability": 0.9,
            "source_kind": "DOCUMENT",
            "statement": "Registry evidence supports trading scope.",
            "value": "wholesale",
        },
    ])
    assert result.classification == "TRADER_LIKELY"
    assert result.trader_likelihood > 0.95
    assert result.confidence >= 0.75
    assert result.supplier_risk_penalty == 0


def test_self_claim_only_stays_uncertain_even_when_direction_is_one_sided():
    result = aggregate_identity_evidence([
        {
            "evidence_id": "claim-1",
            "source_field": "company_information.business_type",
            "direction": "FACTORY",
            "strength": 0.9,
            "reliability": 0.55,
            "source_kind": "SELF_CLAIM",
            "statement": "Profile claims manufacturer status.",
            "value": "Manufacturer",
        },
        {
            "evidence_id": "claim-2",
            "source_field": "company_information.description",
            "direction": "FACTORY",
            "strength": 0.8,
            "reliability": 0.5,
            "source_kind": "SELF_CLAIM",
            "statement": "Seller description claims factory ownership.",
            "value": "Own factory",
        },
    ])
    assert result.factory_likelihood == 1.0
    assert result.classification == "UNCERTAIN"
    assert result.confidence <= 0.25
    assert "self_claim_only" in result.uncertainty_reasons


def test_contradictory_factory_and_trader_evidence_stays_uncertain():
    result = aggregate_identity_evidence([
        {
            "evidence_id": "factory-doc",
            "source_field": "verified_document.factory",
            "direction": "FACTORY",
            "strength": 0.9,
            "reliability": 0.9,
            "source_kind": "DOCUMENT",
            "statement": "Document supports factory activity.",
        },
        {
            "evidence_id": "trader-doc",
            "source_field": "verified_document.trade",
            "direction": "TRADER",
            "strength": 0.9,
            "reliability": 0.9,
            "source_kind": "DOCUMENT",
            "statement": "Document supports trading activity.",
        },
    ])
    assert result.factory_likelihood == 0.5
    assert result.trader_likelihood == 0.5
    assert result.classification == "UNCERTAIN"
    assert "contradictory_identity_evidence" in result.uncertainty_reasons


def test_no_directional_evidence_is_neutral_and_uncertain():
    result = aggregate_identity_evidence([
        {
            "evidence_id": "cert",
            "source_field": "certifications",
            "direction": "NEUTRAL",
            "strength": 0.0,
            "reliability": 0.8,
            "source_kind": "PLATFORM_PROFILE",
            "statement": "Certification does not establish business identity.",
            "value": "ISO 9001",
        }
    ])
    assert result.factory_likelihood == 0.5
    assert result.trader_likelihood == 0.5
    assert result.confidence == 0.0
    assert result.classification == "UNCERTAIN"
    assert result.uncertainty_reasons == ["no_directional_identity_evidence"]


def test_supplier_adapter_uses_structured_factory_fields_conservatively():
    supplier = {
        "company_information": {
            "company_name": "Example Co",
            "business_type": "Manufacturer",
            "factory_area_sqm": 3200,
            "production_line_count": 4,
            "qc_staff_count": 8,
        },
        "certifications": ["ISO 9001"],
    }
    evidence = supplier_identity_evidence(supplier)
    ids = {item.evidence_id for item in evidence}
    assert {
        "company_information.business_type.factory",
        "company_information.factory_area_sqm",
        "company_information.production_line_count",
        "company_information.qc_staff_count",
        "certifications.present",
    } <= ids
    result = assess_supplier_identity(supplier)
    assert result.classification == "FACTORY_LIKELY"
    assert result.supplier_risk_penalty == 0


def test_supplier_adapter_business_type_claim_alone_stays_uncertain():
    result = assess_supplier_identity({
        "company_information": {"business_type": "Trading Company"},
        "certifications": None,
    })
    assert result.trader_likelihood == 1.0
    assert result.classification == "UNCERTAIN"
    assert result.confidence <= 0.25
    assert result.supplier_risk_penalty == 0


def test_certifications_do_not_count_as_factory_evidence():
    evidence = supplier_identity_evidence({
        "company_information": None,
        "certifications": ["ISO 9001", "BSCI"],
    })
    assert len(evidence) == 1
    assert evidence[0].direction == "NEUTRAL"
    assert aggregate_identity_evidence(evidence).classification == "UNCERTAIN"


def test_duplicate_evidence_ids_are_rejected():
    evidence = {
        "evidence_id": "duplicate",
        "source_field": "x",
        "direction": "FACTORY",
        "strength": 0.5,
        "reliability": 0.5,
        "source_kind": "DERIVED",
        "statement": "Signal.",
    }
    with pytest.raises(ValueError, match="unique"):
        aggregate_identity_evidence([evidence, evidence])


def test_invalid_strength_or_reliability_is_rejected():
    with pytest.raises(Exception):
        IdentityEvidence(
            evidence_id="bad",
            source_field="x",
            direction="FACTORY",
            strength=1.2,
            reliability=0.5,
            source_kind="DERIVED",
            statement="Invalid.",
        )


def test_identity_assessment_contract_has_no_supplier_risk_score():
    result = aggregate_identity_evidence([])
    payload = result.model_dump()
    assert "risk_score" not in payload
    assert payload["supplier_risk_penalty"] == 0
