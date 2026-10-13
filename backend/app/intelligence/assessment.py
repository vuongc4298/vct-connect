"""Complete supplier assessment orchestration.

Provider calls live here; deterministic record shaping lives in assessment_policy.
Story 3.8 keeps the public build_assessment contract unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Mapping, Sequence

from .assessment_policy import (
    aggregate_review_count,
    dedupe_evidence,
    identity_records,
    media_records,
    normalized_reviews,
    review_score_inputs,
    supplier_records,
    supplier_score_inputs,
    merge_dimension_inputs,
)
from .identity import FactoryTraderAssessment, assess_supplier_identity
from .interpretation import InterpretationRun, interpret_supplier_data
from .media import MediaInterpretationRun, ReviewMediaInput, interpret_review_media
from .provider import EmbeddingProvider, LLMProvider, MultimodalLLMProvider
from .reviews import ReviewAnalysis, analyze_review_signals
from .scoring import CURRENT_DIMENSION_WEIGHTS, CURRENT_SCORING_VERSION, ConfidenceFactors, RiskAssessment, score_supplier_risk
from .semantic_reviews import SemanticReviewRun, interpret_reviews


@dataclass(frozen=True)
class AssessmentBundle:
    supplier_run: InterpretationRun
    review_analysis: ReviewAnalysis | SemanticReviewRun
    media_run: MediaInterpretationRun | None
    identity: FactoryTraderAssessment
    risk: RiskAssessment
    findings: tuple[dict, ...]
    evidence: tuple[dict, ...]


def _interpret_reviews(
    reviews: list[dict],
    supplier_data: Mapping[str, object],
    *,
    provider: LLMProvider,
    model: str,
    embedding_provider: EmbeddingProvider | None,
    embedding_model: str | None,
    metadata: Mapping[str, str] | None,
) -> ReviewAnalysis | SemanticReviewRun:
    aggregate_count = aggregate_review_count(supplier_data)
    if reviews and embedding_provider is not None and embedding_model:
        return interpret_reviews(
            reviews,
            aggregate_review_count=aggregate_count,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            provider=provider,
            model=model,
            metadata=metadata,
        )
    return analyze_review_signals(
        reviews,
        aggregate_review_count=aggregate_count,
    )


def _interpret_media(
    reviews: list[dict],
    media: Sequence[ReviewMediaInput] | None,
    *,
    multimodal_provider: MultimodalLLMProvider | None,
    multimodal_model: str | None,
    metadata: Mapping[str, str] | None,
) -> MediaInterpretationRun | None:
    if not media:
        return None
    if multimodal_provider is None or not multimodal_model:
        raise ValueError(
            "permitted review media requires a configured multimodal provider/model"
        )
    return interpret_review_media(
        {
            review["evidence_id"]: str(review["text"])
            for review in reviews
        },
        media,
        provider=multimodal_provider,
        model=multimodal_model,
        metadata=metadata,
    )


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
    reviews = normalized_reviews(supplier_data)
    review_analysis = _interpret_reviews(
        reviews,
        supplier_data,
        provider=provider,
        model=model,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        metadata=metadata,
    )
    media_run = _interpret_media(
        reviews,
        media,
        multimodal_provider=multimodal_provider,
        multimodal_model=multimodal_model,
        metadata=metadata,
    )
    identity = assess_supplier_identity(supplier_data)

    dimensions, review_findings, review_evidence, review_reliability = (
        review_score_inputs(review_analysis, media_run)
    )
    identity_findings, identity_evidence, identity_dimensions = identity_records(identity)
    dimensions.extend(identity_dimensions)

    supplier_findings, supplier_evidence = supplier_records(supplier_run)
    supplier_dimensions, dimension_evidence = supplier_score_inputs(supplier_run)
    # Semantic review findings already represent these review-derived facts.
    review_supported = {item.dimension for item in dimensions
                        if any(signal.review_derived for signal in item.signals)}
    supplier_dimensions = [item for item in supplier_dimensions
                           if item.dimension in CURRENT_DIMENSION_WEIGHTS
                           and not (item.dimension in review_supported
                                   and any(signal.review_derived for signal in item.signals))]
    used_ids = {signal.evidence_id for item in supplier_dimensions for signal in item.signals}
    supplier_evidence.extend(item for item in dimension_evidence if item["evidence_id"] in used_ids)
    dimensions = merge_dimension_inputs([item for item in dimensions + supplier_dimensions
                                         if item.dimension in CURRENT_DIMENSION_WEIGHTS])
    media_findings, media_evidence = media_records(media_run)

    # A populated profile does not establish coverage of risk dimensions.
    # Only dimensions with usable scored evidence count toward that coverage.
    supported = {item.dimension for item in dimensions if item.confidence > 0
                 and any(signal.reliability > 0 for signal in item.signals)}
    dimension_coverage = sum(CURRENT_DIMENSION_WEIGHTS[name] for name in supported)
    coverage = min(float(supplier_data.get("completeness") or 0.0), dimension_coverage)
    reliabilities = [supplier_run.interpretation.confidence]
    if reviews:
        reliabilities.append(review_reliability)
    if identity.supporting_evidence:
        reliabilities.append(identity.confidence)
    source_reliability = mean(reliabilities) if reliabilities else 0.0
    sample_adequacy = min(1.0, len(reviews) / 8) if reviews else 0.0

    risk = score_supplier_risk(
        dimensions,
        scoring_version=CURRENT_SCORING_VERSION,
        confidence_factors=ConfidenceFactors(
            data_coverage=max(0.0, min(1.0, coverage)),
            source_reliability=max(0.0, min(1.0, source_reliability)),
            sample_adequacy=sample_adequacy,
            data_freshness=0.0 if supplier_data.get("extraction_method") == "USER_UPLOAD" else 1.0,
        ),
    )
    if risk.label == "INSUFFICIENT_INFORMATION":
        risk = risk.model_copy(update={"overall_risk": None})

    return AssessmentBundle(
        supplier_run=supplier_run,
        review_analysis=review_analysis,
        media_run=media_run,
        identity=identity,
        risk=risk,
        findings=tuple(
            supplier_findings
            + review_findings
            + media_findings
            + identity_findings
        ),
        evidence=dedupe_evidence(
            supplier_evidence,
            review_evidence,
            media_evidence,
            identity_evidence,
        ),
    )
