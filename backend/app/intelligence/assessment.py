"""Story 3.7 complete text-only assessment orchestration."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Mapping, Sequence

from .identity import FactoryTraderAssessment, assess_supplier_identity
from .interpretation import InterpretationRun, interpret_supplier_data
from .provider import EmbeddingProvider, LLMProvider
from .reviews import ReviewAnalysis, analyze_review_signals
from .scoring import (
    ConfidenceFactors,
    DimensionInput,
    RiskAssessment,
    RiskSignal,
    score_supplier_risk,
)
from .semantic_reviews import SemanticReviewRun, interpret_reviews


_SEVERITY = {"NONE": 0.0, "LOW": 25.0, "MEDIUM": 55.0, "HIGH": 80.0}
_CATEGORY_DIMENSION = {
    "QUALITY": "PRODUCT_QUALITY",
    "PRODUCT_MISMATCH": "PRODUCT_QUALITY",
    "PACKAGING": "PRODUCT_QUALITY",
    "DELIVERY": "DELIVERY",
    "AFTER_SALES": "AFTER_SALES",
}


@dataclass(frozen=True)
class AssessmentBundle:
    supplier_run: InterpretationRun
    review_analysis: ReviewAnalysis | SemanticReviewRun
    identity: FactoryTraderAssessment
    risk: RiskAssessment
    findings: tuple[dict, ...]
    evidence: tuple[dict, ...]


def _reviews(supplier_data: Mapping[str, object]) -> list[dict]:
    raw = supplier_data.get("reviews")
    if not isinstance(raw, list):
        return []
    result: list[dict] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            continue
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        result.append({"evidence_id": f"review:{index}", **dict(item)})
    return result


def _aggregate_review_count(supplier_data: Mapping[str, object]) -> int | None:
    signals = supplier_data.get("transaction_signals")
    if isinstance(signals, Mapping):
        value = signals.get("review_count")
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    return None


def _review_score_inputs(
    review_analysis: ReviewAnalysis | SemanticReviewRun,
) -> tuple[list[DimensionInput], list[dict], list[dict], float]:
    findings: list[dict] = []
    evidence: list[dict] = []
    by_dimension: dict[str, list[RiskSignal]] = {}
    if isinstance(review_analysis, SemanticReviewRun):
        assessment = review_analysis.assessment
        review_reliability = assessment.review_reliability
        review_confidence = assessment.confidence
        for finding_index, finding in enumerate(assessment.findings):
            stable_key = f"review:{finding_index}:{finding.category}:" + ",".join(finding.evidence_ids)
            findings.append({
                "finding_key": stable_key,
                "finding_type": "REVIEW_FINDING",
                "dimension": _CATEGORY_DIMENSION.get(finding.category),
                "severity": _SEVERITY[finding.severity],
                "confidence": finding.confidence,
                "payload": finding.model_dump(mode="json"),
            })
            dimension = _CATEGORY_DIMENSION.get(finding.category)
            if dimension is not None and finding.severity != "NONE":
                by_dimension.setdefault(dimension, []).append(RiskSignal(
                    evidence_id="review-finding:" + stable_key,
                    dimension=dimension,
                    severity=_SEVERITY[finding.severity],
                    reliability=max(0.0, min(1.0, review_reliability * finding.confidence)),
                    source_kind="MODEL_INTERPRETATION",
                    review_derived=True,
                    explanation=finding.statement_vi,
                ))
        patterns = assessment.suspicious_patterns
    else:
        review_reliability = review_analysis.reliability
        review_confidence = review_analysis.reliability
        patterns = review_analysis.suspicious_patterns

    manipulation_signals: list[RiskSignal] = []
    for index, pattern in enumerate(patterns):
        payload = pattern.model_dump(mode="json")
        findings.append({
            "finding_key": f"review-pattern:{index}:{pattern.kind}",
            "finding_type": "REVIEW_PATTERN",
            "dimension": "REVIEW_MANIPULATION",
            "severity": pattern.strength * 100,
            "confidence": pattern.reliability,
            "payload": payload,
        })
        manipulation_signals.append(RiskSignal(
            evidence_id=f"review-pattern:{index}:{pattern.kind}",
            dimension="REVIEW_MANIPULATION",
            severity=pattern.strength * 100,
            reliability=pattern.reliability,
            source_kind="DERIVED",
            review_derived=False,
            explanation=f"Deterministic/semantic review pattern: {pattern.kind}",
        ))
        for evidence_id in pattern.evidence_ids:
            evidence.append({
                "evidence_id": evidence_id,
                "source_kind": "REVIEW",
                "source_field": "reviews",
                "payload": {"pattern": pattern.kind},
            })
    if manipulation_signals:
        by_dimension["REVIEW_MANIPULATION"] = manipulation_signals

    dimensions = [
        DimensionInput(
            dimension=dimension,
            confidence=review_confidence,
            signals=signals,
        )
        for dimension, signals in by_dimension.items()
    ]
    return dimensions, findings, evidence, review_reliability


def _identity_records(identity: FactoryTraderAssessment) -> tuple[list[dict], list[dict], list[DimensionInput]]:
    findings = [{
        "finding_key": "identity:assessment",
        "finding_type": "IDENTITY_ASSESSMENT",
        "dimension": "SUPPLIER_IDENTITY",
        "severity": 60.0 if "contradictory_identity_evidence" in identity.uncertainty_reasons else None,
        "confidence": identity.confidence,
        "payload": identity.model_dump(mode="json"),
    }]
    evidence = [
        {
            "evidence_id": item.evidence_id,
            "source_kind": item.source_kind,
            "source_field": item.source_field,
            "payload": item.model_dump(mode="json"),
        }
        for item in identity.supporting_evidence
    ]
    dimensions: list[DimensionInput] = []
    if "contradictory_identity_evidence" in identity.uncertainty_reasons:
        dimensions.append(DimensionInput(
            dimension="SUPPLIER_IDENTITY",
            confidence=identity.confidence,
            signals=[RiskSignal(
                evidence_id="identity:contradictory",
                dimension="SUPPLIER_IDENTITY",
                severity=60,
                reliability=max(identity.confidence, 0.25),
                source_kind="DERIVED",
                explanation="Strong factory and trader identity evidence conflict.",
            )],
        ))
    return findings, evidence, dimensions


def _supplier_records(run: InterpretationRun) -> tuple[list[dict], list[dict]]:
    findings: list[dict] = []
    evidence: list[dict] = []
    groups = [
        ("SUPPLIER_POSITIVE", run.interpretation.positive_signals),
        ("SUPPLIER_RISK", run.interpretation.risk_signals),
        ("SUPPLIER_UNCERTAINTY", run.interpretation.uncertainties),
    ]
    for kind, signals in groups:
        for index, signal in enumerate(signals):
            findings.append({
                "finding_key": f"{kind.lower()}:{index}",
                "finding_type": kind,
                "dimension": None,
                "severity": None,
                "confidence": signal.confidence,
                "payload": signal.model_dump(mode="json"),
            })
            for field in signal.evidence_fields:
                evidence.append({
                    "evidence_id": f"supplier:{field}",
                    "source_kind": "SUPPLIER_DATA",
                    "source_field": field,
                    "payload": {"field": field},
                })
    return findings, evidence


def build_assessment(
    supplier_data: Mapping[str, object],
    *,
    provider: LLMProvider,
    model: str,
    embedding_provider: EmbeddingProvider | None = None,
    embedding_model: str | None = None,
    metadata: Mapping[str, str] | None = None,
) -> AssessmentBundle:
    supplier_run = interpret_supplier_data(
        supplier_data,
        provider=provider,
        model=model,
        metadata=metadata,
    )
    reviews = _reviews(supplier_data)
    aggregate_count = _aggregate_review_count(supplier_data)
    if reviews and embedding_provider is not None and embedding_model:
        review_analysis: ReviewAnalysis | SemanticReviewRun = interpret_reviews(
            reviews,
            aggregate_review_count=aggregate_count,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            provider=provider,
            model=model,
            metadata=metadata,
        )
    else:
        review_analysis = analyze_review_signals(
            reviews,
            aggregate_review_count=aggregate_count,
        )

    identity = assess_supplier_identity(supplier_data)
    dimensions, review_findings, review_evidence, review_reliability = _review_score_inputs(
        review_analysis
    )
    identity_findings, identity_evidence, identity_dimensions = _identity_records(identity)
    dimensions.extend(identity_dimensions)

    supplier_findings, supplier_evidence = _supplier_records(supplier_run)
    coverage = float(supplier_data.get("completeness") or 0.0)
    reliabilities = [supplier_run.interpretation.confidence]
    if reviews:
        reliabilities.append(review_reliability)
    if identity.supporting_evidence:
        reliabilities.append(identity.confidence)
    source_reliability = mean(reliabilities) if reliabilities else 0.0
    sample_adequacy = min(1.0, len(reviews) / 8) if reviews else 0.0

    risk = score_supplier_risk(
        dimensions,
        confidence_factors=ConfidenceFactors(
            data_coverage=max(0.0, min(1.0, coverage)),
            source_reliability=max(0.0, min(1.0, source_reliability)),
            sample_adequacy=sample_adequacy,
            data_freshness=1.0,
        ),
    )

    findings = supplier_findings + review_findings + identity_findings
    evidence_by_id: dict[str, dict] = {}
    for item in supplier_evidence + review_evidence + identity_evidence:
        evidence_by_id.setdefault(item["evidence_id"], item)
    return AssessmentBundle(
        supplier_run=supplier_run,
        review_analysis=review_analysis,
        identity=identity,
        risk=risk,
        findings=tuple(findings),
        evidence=tuple(evidence_by_id.values()),
    )
