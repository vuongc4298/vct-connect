"""Internal assessment policy helpers.

This module contains deterministic transformation policy only. It must not perform
provider calls or persistence. Story 3.8 extracted these helpers from assessment.py
without changing the v0.1.0 assessment contract.
"""
from __future__ import annotations

from typing import Mapping

from .identity import FactoryTraderAssessment
from .interpretation import InterpretationRun
from .media import MediaInterpretationRun
from .reviews import ReviewAnalysis
from .scoring import DimensionInput, RiskSignal
from .semantic_reviews import SemanticReviewRun


SEVERITY = {"NONE": 0.0, "LOW": 25.0, "MEDIUM": 55.0, "HIGH": 80.0}
MEDIA_MULTIPLIER = {
    "SUPPORTS": 1.10,
    "PARTIALLY_SUPPORTS": 1.00,
    "CONTRADICTS": 0.50,
    "CANNOT_DETERMINE": 1.00,
}
CATEGORY_DIMENSION = {
    "QUALITY": "PRODUCT_QUALITY",
    "PRODUCT_MISMATCH": "PRODUCT_QUALITY",
    "PACKAGING": "PRODUCT_QUALITY",
    "DELIVERY": "DELIVERY",
    "AFTER_SALES": "AFTER_SALES",
}


def normalized_reviews(supplier_data: Mapping[str, object]) -> list[dict]:
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
        result.append({**dict(item), "evidence_id": f"review:{index}"})
    return result


def aggregate_review_count(supplier_data: Mapping[str, object]) -> int | None:
    signals = supplier_data.get("transaction_signals")
    if isinstance(signals, Mapping):
        value = signals.get("review_count")
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    return None


def media_review_factors(media_run: MediaInterpretationRun | None) -> dict[str, float]:
    if media_run is None:
        return {}
    grouped: dict[str, list[float]] = {}
    for finding in media_run.assessment.findings:
        base = MEDIA_MULTIPLIER[finding.consistency]
        factor = 1.0 + (base - 1.0) * finding.confidence
        grouped.setdefault(finding.review_evidence_id, []).append(factor)
    return {
        evidence_id: sum(values) / len(values)
        for evidence_id, values in grouped.items()
        if values
    }


def review_score_inputs(
    review_analysis: ReviewAnalysis | SemanticReviewRun,
    media_run: MediaInterpretationRun | None = None,
) -> tuple[list[DimensionInput], list[dict], list[dict], float]:
    findings: list[dict] = []
    evidence: list[dict] = []
    by_dimension: dict[str, list[RiskSignal]] = {}
    media_factors = media_review_factors(media_run)

    if isinstance(review_analysis, SemanticReviewRun):
        assessment = review_analysis.assessment
        review_reliability = assessment.review_reliability
        review_confidence = assessment.confidence
        for finding_index, finding in enumerate(assessment.findings):
            stable_key = (
                f"review:{finding_index}:{finding.category}:"
                + ",".join(finding.evidence_ids)
            )
            findings.append({
                "finding_key": stable_key,
                "finding_type": "REVIEW_FINDING",
                "dimension": CATEGORY_DIMENSION.get(finding.category),
                "severity": SEVERITY[finding.severity],
                "confidence": finding.confidence,
                "payload": finding.model_dump(mode="json"),
            })
            dimension = CATEGORY_DIMENSION.get(finding.category)
            if dimension is not None and finding.severity != "NONE":
                media_factor = (
                    sum(
                        media_factors.get(evidence_id, 1.0)
                        for evidence_id in finding.evidence_ids
                    )
                    / len(finding.evidence_ids)
                )
                by_dimension.setdefault(dimension, []).append(RiskSignal(
                    evidence_id="review-finding:" + stable_key,
                    dimension=dimension,
                    severity=SEVERITY[finding.severity],
                    reliability=max(
                        0.0,
                        min(
                            1.0,
                            review_reliability * finding.confidence * media_factor,
                        ),
                    ),
                    source_kind="MODEL_INTERPRETATION",
                    review_derived=True,
                    explanation=finding.statement_vi,
                ))
        patterns = assessment.suspicious_patterns
    else:
        review_reliability = review_analysis.reliability
        review_confidence = review_analysis.reliability
        patterns = review_analysis.suspicious_patterns

    if media_factors:
        review_reliability = max(
            0.0,
            min(
                1.0,
                review_reliability
                * (sum(media_factors.values()) / len(media_factors)),
            ),
        )

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


def identity_records(
    identity: FactoryTraderAssessment,
) -> tuple[list[dict], list[dict], list[DimensionInput]]:
    findings = [{
        "finding_key": "identity:assessment",
        "finding_type": "IDENTITY_ASSESSMENT",
        "dimension": "SUPPLIER_IDENTITY",
        "severity": (
            60.0
            if "contradictory_identity_evidence" in identity.uncertainty_reasons
            else None
        ),
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


def media_records(
    media_run: MediaInterpretationRun | None,
) -> tuple[list[dict], list[dict]]:
    if media_run is None:
        return [], []
    findings = [
        {
            "finding_key": f"media:{index}:{finding.media_id}",
            "finding_type": "MEDIA_CONSISTENCY",
            "dimension": None,
            "severity": None,
            "confidence": finding.confidence,
            "payload": finding.model_dump(mode="json"),
        }
        for index, finding in enumerate(media_run.assessment.findings)
    ]
    evidence = [
        {
            "evidence_id": f"media:{item.media_id}",
            "source_kind": "REVIEW_MEDIA",
            "source_field": "reviews",
            "payload": item.model_dump(mode="json"),
        }
        for item in media_run.assessment.provenance
    ]
    return findings, evidence


def supplier_records(run: InterpretationRun) -> tuple[list[dict], list[dict]]:
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


def dedupe_evidence(*groups: list[dict]) -> tuple[dict, ...]:
    evidence_by_id: dict[str, dict] = {}
    for group in groups:
        for item in group:
            evidence_by_id.setdefault(item["evidence_id"], item)
    return tuple(evidence_by_id.values())
