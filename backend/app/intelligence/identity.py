"""Story 3.4 factory/trader identity evidence aggregation.

The aggregator keeps identity classification separate from supplier risk. It accepts
sourced evidence with direction, strength and reliability, then computes reproducible
factory/trader likelihoods, confidence, supporting evidence and uncertainty.
"""
from __future__ import annotations

from typing import Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator


IDENTITY_SCHEMA_VERSION = "factory-trader-assessment.v1"

IdentityDirection = Literal["FACTORY", "TRADER", "NEUTRAL"]
IdentitySourceKind = Literal[
    "PLATFORM_PROFILE",
    "SELF_CLAIM",
    "DOCUMENT",
    "DERIVED",
]
IdentityClassification = Literal[
    "FACTORY_LIKELY",
    "TRADER_LIKELY",
    "MIXED",
    "UNCERTAIN",
]


class IdentityEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1, max_length=160)
    source_field: str = Field(min_length=1, max_length=160)
    direction: IdentityDirection
    strength: float = Field(ge=0, le=1)
    reliability: float = Field(ge=0, le=1)
    source_kind: IdentitySourceKind
    statement: str = Field(min_length=1, max_length=800)
    value: str | int | float | bool | None = None

    @field_validator("evidence_id", "source_field", "statement")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("identity evidence text fields must not be blank")
        return value


class FactoryTraderAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["factory-trader-assessment.v1"] = IDENTITY_SCHEMA_VERSION
    classification: IdentityClassification
    factory_likelihood: float = Field(ge=0, le=1)
    trader_likelihood: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    supporting_evidence: list[IdentityEvidence]
    uncertainty_reasons: list[str]
    supplier_risk_penalty: Literal[0] = 0


def _weighted_mass(evidence: IdentityEvidence) -> float:
    return evidence.strength * evidence.reliability


def aggregate_identity_evidence(
    evidence: Sequence[IdentityEvidence | Mapping[str, object]],
) -> FactoryTraderAssessment:
    items = [
        item if isinstance(item, IdentityEvidence) else IdentityEvidence.model_validate(item)
        for item in evidence
    ]
    ids = [item.evidence_id for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("identity evidence IDs must be unique")

    directed = [item for item in items if item.direction in {"FACTORY", "TRADER"}]
    factory_mass = sum(_weighted_mass(item) for item in directed if item.direction == "FACTORY")
    trader_mass = sum(_weighted_mass(item) for item in directed if item.direction == "TRADER")
    total_mass = factory_mass + trader_mass

    if total_mass > 0:
        factory_likelihood = factory_mass / total_mass
        trader_likelihood = trader_mass / total_mass
    else:
        factory_likelihood = trader_likelihood = 0.5

    strongest_factory = max((_weighted_mass(item) for item in directed if item.direction == "FACTORY"), default=0.0)
    strongest_trader = max((_weighted_mass(item) for item in directed if item.direction == "TRADER"), default=0.0)
    contradictory = strongest_factory >= 0.35 and strongest_trader >= 0.35

    self_claim_only = bool(directed) and all(item.source_kind == "SELF_CLAIM" for item in directed)
    independent_reliability = max(
        (item.reliability for item in directed if item.source_kind != "SELF_CLAIM"),
        default=0.0,
    )
    coverage_factor = min(1.0, len(directed) / 4)
    dominance = abs(factory_likelihood - trader_likelihood)
    confidence = coverage_factor * (0.45 + 0.55 * dominance)
    confidence *= 0.5 + 0.5 * independent_reliability
    if self_claim_only:
        confidence = min(confidence, 0.25)
    if contradictory:
        confidence *= 0.45
    if not directed:
        confidence = 0.0
    confidence = round(max(0.0, min(1.0, confidence)), 4)

    uncertainty: list[str] = []
    if not directed:
        uncertainty.append("no_directional_identity_evidence")
    if self_claim_only:
        uncertainty.append("self_claim_only")
    if contradictory:
        uncertainty.append("contradictory_identity_evidence")
    if directed and len(directed) < 2:
        uncertainty.append("limited_identity_evidence")
    if independent_reliability < 0.5 and directed and not self_claim_only:
        uncertainty.append("low_independent_reliability")

    if confidence < 0.4:
        classification: IdentityClassification = "UNCERTAIN"
    elif factory_likelihood >= 0.7:
        classification = "FACTORY_LIKELY"
    elif trader_likelihood >= 0.7:
        classification = "TRADER_LIKELY"
    else:
        classification = "MIXED"

    return FactoryTraderAssessment(
        classification=classification,
        factory_likelihood=round(factory_likelihood, 4),
        trader_likelihood=round(trader_likelihood, 4),
        confidence=confidence,
        supporting_evidence=items,
        uncertainty_reasons=uncertainty,
        supplier_risk_penalty=0,
    )


def _text(value: object) -> str:
    return str(value).strip().casefold() if value is not None else ""


def supplier_identity_evidence(supplier_data: Mapping[str, object]) -> list[IdentityEvidence]:
    """Conservatively map only present SupplierData fields into identity evidence."""
    company = supplier_data.get("company_information")
    company = company if isinstance(company, Mapping) else {}
    evidence: list[IdentityEvidence] = []

    business_type = _text(company.get("business_type"))
    if business_type:
        if any(token in business_type for token in ("manufacturer", "factory", "manufacturing", "生产", "工厂")):
            evidence.append(IdentityEvidence(
                evidence_id="company_information.business_type.factory",
                source_field="company_information.business_type",
                direction="FACTORY",
                strength=0.75,
                reliability=0.55,
                source_kind="SELF_CLAIM",
                statement="Platform profile states a manufacturing/factory business type.",
                value=str(company.get("business_type")),
            ))
        if any(token in business_type for token in ("trading", "trader", "wholesale", "贸易", "经销")):
            evidence.append(IdentityEvidence(
                evidence_id="company_information.business_type.trader",
                source_field="company_information.business_type",
                direction="TRADER",
                strength=0.75,
                reliability=0.55,
                source_kind="SELF_CLAIM",
                statement="Platform profile states a trading/wholesale business type.",
                value=str(company.get("business_type")),
            ))

    numeric_factory_fields = {
        "factory_area_sqm": (0.75, "Factory-area evidence is present."),
        "production_line_count": (0.9, "Production-line evidence is present."),
        "qc_staff_count": (0.55, "QC staffing evidence is present."),
        "rd_team_count": (0.45, "R&D staffing evidence is present."),
        "employee_count": (0.3, "Employee-count evidence is present."),
    }
    for field, (strength, statement) in numeric_factory_fields.items():
        raw = company.get(field)
        if isinstance(raw, bool):
            continue
        try:
            value = float(raw) if raw is not None else 0.0
        except (TypeError, ValueError):
            continue
        if value <= 0:
            continue
        evidence.append(IdentityEvidence(
            evidence_id=f"company_information.{field}",
            source_field=f"company_information.{field}",
            direction="FACTORY",
            strength=strength,
            reliability=0.7,
            source_kind="PLATFORM_PROFILE",
            statement=statement,
            value=raw if isinstance(raw, (int, float)) else str(raw),
        ))

    certifications = supplier_data.get("certifications")
    if isinstance(certifications, list) and certifications:
        evidence.append(IdentityEvidence(
            evidence_id="certifications.present",
            source_field="certifications",
            direction="NEUTRAL",
            strength=0.0,
            reliability=0.5,
            source_kind="PLATFORM_PROFILE",
            statement="Certifications are present but do not by themselves establish factory or trader status.",
            value=len(certifications),
        ))

    return evidence


def assess_supplier_identity(supplier_data: Mapping[str, object]) -> FactoryTraderAssessment:
    return aggregate_identity_evidence(supplier_identity_evidence(supplier_data))
