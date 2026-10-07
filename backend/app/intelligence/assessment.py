"""Story 3.7 complete text-only assessment orchestration."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Mapping, Sequence

from .identity import FactoryTraderAssessment, assess_supplier_identity
from .interpretation import InterpretationRun, interpret_supplier_data
from .media import MediaInterpretationRun, ReviewMediaInput, interpret_review_media
from .provider import EmbeddingProvider, LLMProvider, MultimodalLLMProvider
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
_MEDIA_MULTIPLIER = {
    "SUPPORTS": 1.10,
    "PARTIALLY_SUPPORTS": 1.00,
    "CONTRADICTS": 0.50,
    "CANNOT_DETERMINE": 1.00,
}
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
    media_run: MediaInterpretationRun | None
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
        result.append({**dict(item), "evidence_id": f"review:{index}"})
    return result


def _aggregate_review_count(supplier_data: Mapping[str, object]) -> int | None:
    signals = supplier_data.get("transaction_signals")
    if isinstance(signals, Mapping):
        value = signals.get("review_count")
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    return None


def _media_review_factors(media_run: MediaInterpretationRun | None) -> dict[str, float]:
    if media_run is None:
        return {}
    grouped: dict[str, list[float]] = {}
    for finding in media_run.assessment.findings:
        base = _MEDIA_MULTIPLIER[finding.consistency]
        factor = 1.0 + (base - 1.0) * finding.confidence
        grouped.setdefault(finding.review_evidence_id, []).append(factor)
    return {
        evidence_id: sum(values) / len(values)
        for evidence_id, values in grouped.items()
        if values
    }


def _review_score_inputs(
    review_analysis: ReviewAnalysis | SemanticReviewRun,
    media_run: MediaInterpretationRun | None = None,
) -> tuple[list[DimensionInput], list[dict], list[dict], float]:
    findings: list[dict] = []
    evidence: list[dict] = []
    by_dimension: dict[str, list[RiskSignal]] = {}
    media_factors = _media_review_factors(media_run)
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
                    reliability=max(
                        0.0,
                        min(
                            1.0,
                            review_reliability
                            * finding.confidence
                            * (
                                sum(media_factors.get(evidence_id, 1.0) for evidence_id in finding.evidence_ids)
                                / len(finding.evidence_ids)
                            ),
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
                review_reliability * (sum(media_factors.values()) / len(media_factors)),
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


def _media_records(
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
    media: Sequence[ReviewMediaInput] | None = None,
    multimodal_provider: MultimodalLLMProvider | None = None,
    multimodal_model: str | None = None,
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

    media_run: MediaInterpretationRun | None = None
    if media:
        if multimodal_provider is None or not multimodal_model:
            raise ValueError("permitted review media requires a configured multimodal provider/model")
        review_text_by_id = {
            review["evidence_id"]: str(review["text"])
            for review in reviews
        }
        media_run = interpret_review_media(
            review_text_by_id,
            media,
            provider=multimodal_provider,
            model=multimodal_model,
            metadata=metadata,
        )

    identity = assess_supplier_identity(supplier_data)
    dimensions, review_findings, review_evidence, review_reliability = _review_score_inputs(
        review_analysis, media_run
    )
    identity_findings, identity_evidence, identity_dimensions = _identity_records(identity)
    dimensions.extend(identity_dimensions)

    supplier_findings, supplier_evidence = _supplier_records(supplier_run)
    media_findings, media_evidence = _media_records(media_run)
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

    findings = supplier_findings + review_findings + media_findings + identity_findings
    evidence_by_id: dict[str, dict] = {}
    for item in supplier_evidence + review_evidence + media_evidence + identity_evidence:
        evidence_by_id.setdefault(item["evidence_id"], item)
    return AssessmentBundle(
        supplier_run=supplier_run,
        review_analysis=review_analysis,
        media_run=media_run,
        identity=identity,
        risk=risk,
        findings=tuple(findings),
        evidence=tuple(evidence_by_id.values()),
    )
