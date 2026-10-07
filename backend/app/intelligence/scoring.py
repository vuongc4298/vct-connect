"""Versioned deterministic supplier-risk scoring for Epic 3 / Story 3.5.

The scorer follows Technical Specification section 14:
- seven fixed v0.1.0 dimension weights,
- reliability-weighted signal severity per dimension,
- confidence-weighted dimension aggregation,
- separate Risk, Confidence and Coverage,
- insufficient-information gates,
- conservative critical floors,
- review-manipulation confidence reduction for review-derived evidence.

Missing evidence is never converted into zero risk.
"""
from __future__ import annotations

from typing import Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator


SCORING_VERSION = "v0.1.0"
RISK_SCHEMA_VERSION = "supplier-risk.v0.1"

RiskDimension = Literal[
    "PRODUCT_QUALITY",
    "SUPPLIER_IDENTITY",
    "DELIVERY",
    "REVIEW_MANIPULATION",
    "AFTER_SALES",
    "PRICING",
    "COMMUNICATION",
]
RiskLabel = Literal["LOW", "MODERATE", "HIGH", "INSUFFICIENT_INFORMATION"]
RiskSourceKind = Literal[
    "REVIEW",
    "PLATFORM_PROFILE",
    "VERIFIED_DOCUMENT",
    "EXTRACTION",
    "MODEL_INTERPRETATION",
    "DERIVED",
]

DIMENSION_WEIGHTS: dict[RiskDimension, float] = {
    "PRODUCT_QUALITY": 0.25,
    "SUPPLIER_IDENTITY": 0.15,
    "DELIVERY": 0.15,
    "REVIEW_MANIPULATION": 0.15,
    "AFTER_SALES": 0.15,
    "PRICING": 0.10,
    "COMMUNICATION": 0.05,
}

CONFIDENCE_FACTOR_WEIGHTS = {
    "data_coverage": 0.40,
    "source_reliability": 0.25,
    "sample_adequacy": 0.20,
    "data_freshness": 0.15,
}

INSUFFICIENT_COVERAGE_THRESHOLD = 0.45
INSUFFICIENT_CONFIDENCE_THRESHOLD = 0.40
REVIEW_MANIPULATION_MAX_CONFIDENCE_REDUCTION = 0.50

# Product-owner approved conservative v0.1.0 critical-floor policy:
# only independently verified, corroborated, very severe/reliable non-review evidence.
CRITICAL_MIN_SEVERITY = 90.0
CRITICAL_MIN_RELIABILITY = 0.90
CRITICAL_MIN_CORROBORATING_EVIDENCE = 2
CRITICAL_RISK_FLOOR = 65.0


class RiskSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1, max_length=160)
    dimension: RiskDimension
    severity: float = Field(ge=0, le=100)
    reliability: float = Field(ge=0, le=1)
    importance: float = Field(default=1.0, gt=0, le=1)
    source_kind: RiskSourceKind
    review_derived: bool = False
    independently_verified: bool = False
    corroborating_evidence_count: int = Field(default=1, ge=1)
    critical_candidate: bool = False
    explanation: str = Field(min_length=1, max_length=1000)

    @field_validator("evidence_id", "explanation")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("risk signal text fields must not be blank")
        return value


class DimensionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: RiskDimension
    confidence: float = Field(ge=0, le=1)
    signals: list[RiskSignal]

    @field_validator("signals")
    @classmethod
    def matching_dimension(cls, value: list[RiskSignal], info):
        dimension = info.data.get("dimension")
        if dimension is not None and any(signal.dimension != dimension for signal in value):
            raise ValueError("all signals must match their dimension input")
        ids = [signal.evidence_id for signal in value]
        if len(ids) != len(set(ids)):
            raise ValueError("risk signal evidence IDs must be unique within a dimension")
        return value


class ConfidenceFactors(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_coverage: float = Field(ge=0, le=1)
    source_reliability: float = Field(ge=0, le=1)
    sample_adequacy: float = Field(ge=0, le=1)
    data_freshness: float = Field(ge=0, le=1)


class DimensionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: RiskDimension
    configured_weight: float = Field(gt=0, le=1)
    risk: float | None = Field(default=None, ge=0, le=100)
    base_confidence: float = Field(ge=0, le=1)
    effective_confidence: float = Field(ge=0, le=1)
    review_derived_share: float = Field(ge=0, le=1)
    review_manipulation_adjustment: float = Field(ge=0, le=1)
    evidence_ids: list[str]


class RiskAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["supplier-risk.v0.1"] = RISK_SCHEMA_VERSION
    scoring_version: Literal["v0.1.0"] = SCORING_VERSION
    overall_risk: float | None = Field(default=None, ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    data_coverage: float = Field(ge=0, le=1)
    label: RiskLabel
    dimensions: list[DimensionResult]
    critical_floor: float | None = Field(default=None, ge=0, le=100)
    critical_evidence_ids: list[str]
    missing_dimensions: list[RiskDimension]


def _dimension_risk(signals: Sequence[RiskSignal]) -> float | None:
    denominator = sum(signal.importance * signal.reliability for signal in signals)
    if denominator <= 0:
        return None
    numerator = sum(
        signal.importance * signal.reliability * signal.severity
        for signal in signals
    )
    return numerator / denominator


def _review_derived_share(signals: Sequence[RiskSignal]) -> float:
    denominator = sum(signal.importance * signal.reliability for signal in signals)
    if denominator <= 0:
        return 0.0
    review_mass = sum(
        signal.importance * signal.reliability
        for signal in signals
        if signal.review_derived
    )
    return max(0.0, min(1.0, review_mass / denominator))


def _overall_confidence(factors: ConfidenceFactors) -> float:
    return (
        CONFIDENCE_FACTOR_WEIGHTS["data_coverage"] * factors.data_coverage
        + CONFIDENCE_FACTOR_WEIGHTS["source_reliability"] * factors.source_reliability
        + CONFIDENCE_FACTOR_WEIGHTS["sample_adequacy"] * factors.sample_adequacy
        + CONFIDENCE_FACTOR_WEIGHTS["data_freshness"] * factors.data_freshness
    )


def _critical_eligible(signal: RiskSignal) -> bool:
    return (
        signal.critical_candidate
        and not signal.review_derived
        and signal.source_kind == "VERIFIED_DOCUMENT"
        and signal.independently_verified
        and signal.corroborating_evidence_count >= CRITICAL_MIN_CORROBORATING_EVIDENCE
        and signal.severity >= CRITICAL_MIN_SEVERITY
        and signal.reliability >= CRITICAL_MIN_RELIABILITY
    )


def _label(risk: float | None, coverage: float, confidence: float) -> RiskLabel:
    if (
        risk is None
        or coverage < INSUFFICIENT_COVERAGE_THRESHOLD
        or confidence < INSUFFICIENT_CONFIDENCE_THRESHOLD
    ):
        return "INSUFFICIENT_INFORMATION"
    if risk <= 34:
        return "LOW"
    if risk <= 64:
        return "MODERATE"
    return "HIGH"


def score_supplier_risk(
    dimensions: Sequence[DimensionInput | Mapping[str, object]],
    *,
    confidence_factors: ConfidenceFactors | Mapping[str, object],
) -> RiskAssessment:
    """Compute one reproducible v0.1.0 assessment."""
    inputs = [
        value if isinstance(value, DimensionInput) else DimensionInput.model_validate(value)
        for value in dimensions
    ]
    by_dimension = {value.dimension: value for value in inputs}
    if len(by_dimension) != len(inputs):
        raise ValueError("each risk dimension may be supplied at most once")

    factors = (
        confidence_factors
        if isinstance(confidence_factors, ConfidenceFactors)
        else ConfidenceFactors.model_validate(confidence_factors)
    )
    confidence = _overall_confidence(factors)

    review_input = by_dimension.get("REVIEW_MANIPULATION")
    review_manipulation_risk = (
        _dimension_risk(review_input.signals) if review_input is not None else None
    )
    review_manipulation_fraction = (review_manipulation_risk or 0.0) / 100.0

    results: list[DimensionResult] = []
    missing: list[RiskDimension] = []
    weighted_risk_numerator = 0.0
    weighted_risk_denominator = 0.0

    for dimension, configured_weight in DIMENSION_WEIGHTS.items():
        item = by_dimension.get(dimension)
        if item is None or not item.signals:
            missing.append(dimension)
            results.append(DimensionResult(
                dimension=dimension,
                configured_weight=configured_weight,
                risk=None,
                base_confidence=item.confidence if item is not None else 0.0,
                effective_confidence=0.0,
                review_derived_share=0.0,
                review_manipulation_adjustment=0.0,
                evidence_ids=[],
            ))
            continue

        risk = _dimension_risk(item.signals)
        review_share = _review_derived_share(item.signals)
        adjustment = 0.0
        if dimension in {"PRODUCT_QUALITY", "DELIVERY", "AFTER_SALES"}:
            adjustment = (
                review_share
                * review_manipulation_fraction
                * REVIEW_MANIPULATION_MAX_CONFIDENCE_REDUCTION
            )
        effective_confidence = item.confidence * (1.0 - adjustment)

        results.append(DimensionResult(
            dimension=dimension,
            configured_weight=configured_weight,
            risk=round(risk, 4) if risk is not None else None,
            base_confidence=item.confidence,
            effective_confidence=round(effective_confidence, 4),
            review_derived_share=round(review_share, 4),
            review_manipulation_adjustment=round(adjustment, 4),
            evidence_ids=[signal.evidence_id for signal in item.signals],
        ))
        if risk is not None and effective_confidence > 0:
            mass = configured_weight * effective_confidence
            weighted_risk_numerator += mass * risk
            weighted_risk_denominator += mass

    overall = (
        weighted_risk_numerator / weighted_risk_denominator
        if weighted_risk_denominator > 0
        else None
    )

    critical = [
        signal
        for item in inputs
        for signal in item.signals
        if _critical_eligible(signal)
    ]
    critical_ids = sorted(signal.evidence_id for signal in critical)
    critical_floor = CRITICAL_RISK_FLOOR if critical else None
    if overall is not None and critical_floor is not None:
        overall = max(overall, critical_floor)

    overall_rounded = round(overall, 4) if overall is not None else None
    confidence_rounded = round(confidence, 4)
    return RiskAssessment(
        overall_risk=overall_rounded,
        confidence=confidence_rounded,
        data_coverage=factors.data_coverage,
        label=_label(overall_rounded, factors.data_coverage, confidence_rounded),
        dimensions=results,
        critical_floor=critical_floor,
        critical_evidence_ids=critical_ids,
        missing_dimensions=missing,
    )
