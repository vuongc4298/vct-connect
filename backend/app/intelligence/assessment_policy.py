"""Internal assessment policy helpers.

This module contains deterministic transformation policy only. It must not perform
provider calls or persistence. Story 3.8 extracted these helpers from assessment.py
without changing the v0.1.0 assessment contract.
"""
from __future__ import annotations

from typing import Mapping
import json

from .identity import FactoryTraderAssessment
from .interpretation import InterpretationRun
from .media import MediaInterpretationRun
from .reviews import ReviewAnalysis
from .scoring import DimensionInput, RiskSignal
from .semantic_reviews import SemanticReviewRun


SEVERITY = {"NONE": 0.0, "LOW": 25.0, "MEDIUM": 55.0, "HIGH": 80.0}
DIMENSION_FIELDS = {
    "PRODUCT_QUALITY": {"reviews", "transaction_signals", "certifications"},
    "SUPPLIER_IDENTITY": {"company_information", "certifications", "activity_history"},
    "DELIVERY": {"delivery_information", "transaction_signals", "reviews"},
    "REVIEW_MANIPULATION": {"reviews"},
    "AFTER_SALES": {"reviews", "transaction_signals", "company_information"},
    "PRICING": {"price_information"},
    "COMMUNICATION": {"reviews", "transaction_signals"},
}
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
    *,
    accessible_reviews: list[dict] | None = None,
) -> tuple[list[DimensionInput], list[dict], list[dict], float]:
    findings: list[dict] = []
    evidence: list[dict] = []
    topic_evidence: list[dict] = []
    by_dimension: dict[str, list[RiskSignal]] = {}
    media_factors = media_review_factors(media_run)
    complaint_topics = (
        review_analysis.deterministic_analysis.complaint_topics
        if isinstance(review_analysis, SemanticReviewRun)
        else review_analysis.complaint_topics
    )
    for index, topic in enumerate(complaint_topics):
        findings.append({
            "finding_key": f"review-topic:{index}:{topic.category}",
            "finding_type": "REVIEW_COMPLAINT_TOPIC",
            "dimension": CATEGORY_DIMENSION.get(topic.category),
            "severity": None,
            "confidence": topic.reliability,
            "payload": topic.model_dump(mode="json"),
        })
        for evidence_id in topic.evidence_ids:
            topic_evidence.append({
                "evidence_id": evidence_id,
                "source_kind": "REVIEW",
                "source_field": "reviews",
                "payload": {"complaint_topic": topic.category},
            })

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

    elif accessible_reviews is not None:
        # Ten public reviews permit a preliminary check, not population verification.
        deterministic = (review_analysis.deterministic_analysis
                         if isinstance(review_analysis, SemanticReviewRun) else review_analysis)
        if deterministic.review_count >= 10:
            confidence = min(review_confidence, 0.6)
            if 'review_timestamps' in deterministic.missing_inputs:
                confidence = min(confidence, 0.45)
            if 'review_ratings' in deterministic.missing_inputs:
                confidence = min(confidence, 0.4)
            evidence_id = 'review-sample:credibility'
            statement = (f'Kiểm tra sơ bộ {deterministic.review_count} đánh giá đã thu thập chưa thấy '
                         'mẫu bất thường trong các phép kiểm tra khả dụng; mẫu được chọn có thể thiên lệch '
                         'và không xác minh tính xác thực của toàn bộ đánh giá.')
            by_dimension['REVIEW_MANIPULATION'] = [RiskSignal(
                evidence_id=evidence_id, dimension='REVIEW_MANIPULATION', severity=35,
                reliability=confidence, source_kind='DERIVED', explanation=statement,
            )]
            evidence.append({'evidence_id': evidence_id, 'source_kind': 'DERIVED',
                             'source_field': 'reviews', 'payload': {
                                 'statement_vi': statement, 'sample_count': deterministic.review_count,
                                 'evidence_ids': [item['evidence_id'] for item in accessible_reviews],
                                 'missing_inputs': deterministic.missing_inputs,
                                 'policy': 'accessible-review-sample.v1', 'confidence_cap': confidence,
                                 'independently_verified': False,
                             }})

    # Preserve existing suspicious-pattern evidence payloads when a review is
    # also part of a recurring complaint topic. Final evidence dedupe is
    # first-write-wins, so deferred topic linkage is appended afterward.
    evidence.extend(topic_evidence)

    dimensions = [
        DimensionInput(
            dimension=dimension,
            confidence=min(review_confidence, signals[0].reliability) if dimension == 'REVIEW_MANIPULATION' and not manipulation_signals else review_confidence,
            signals=signals,
        )
        for dimension, signals in by_dimension.items()
    ]
    dimensions = [item.model_copy(update={'confidence': min(item.confidence, 0.6),
                  'signals': [signal.model_copy(update={'reliability': min(signal.reliability, 0.6)})
                              for signal in item.signals]}) if item.dimension == 'AFTER_SALES' else item
                  for item in dimensions]
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


def _source_fragments(value: object) -> list[str]:
    fragments = [json.dumps(value, ensure_ascii=False, sort_keys=True)]
    fragments.append(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    if isinstance(value, str):
        fragments.append(value)
    elif isinstance(value, Mapping):
        for item in value.values():
            fragments.extend(_source_fragments(item))
    elif isinstance(value, list):
        for item in value:
            fragments.extend(_source_fragments(item))
    return fragments


def supplier_score_inputs(run: InterpretationRun) -> tuple[list[DimensionInput], list[dict]]:
    """Score only explicit categories supported by present, quoted source evidence.

    Narrative positives/risks and missing fields never implicitly become scores.
    Model claims cannot activate critical floors or count as verified documents.
    """
    dimensions: list[DimensionInput] = []
    evidence: list[dict] = []
    source = run.input_payload["evidence"]
    for item in run.interpretation.dimension_assessments:
        fields = set(item.evidence_fields)
        if (item.dimension in {"SUPPLIER_IDENTITY", "REVIEW_MANIPULATION"}
                or item.severity == "UNKNOWN" or not fields
                or fields != set(item.evidence_quotes)
                or not fields.intersection(DIMENSION_FIELDS[item.dimension])):
            continue
        metrics = source.get("transaction_signals")
        if "transaction_signals" in fields and isinstance(metrics, Mapping):
            raw_metrics = metrics.get("source_metrics")
            if isinstance(raw_metrics, list) and any(
                isinstance(metric, Mapping) and isinstance(metric.get("label"), str)
                and metric["label"].casefold() in {
                    "store return rate", "dropshipping buyer's return rate", "return customer rate"
                } and metric["label"] in item.evidence_quotes["transaction_signals"]
                for metric in raw_metrics
            ):
                # These translated platform labels may mean repeat purchase;
                # they cannot support numeric quality/returns risk as captured.
                continue
            if isinstance(raw_metrics, list) and not any(
                isinstance(metric, Mapping)
                and isinstance(metric.get("label"), str)
                and isinstance(metric.get("value"), str)
                and metric["label"] in item.evidence_quotes["transaction_signals"]
                and metric["value"] in item.evidence_quotes["transaction_signals"]
                for metric in raw_metrics
            ):
                continue
        if any(source.get(field) in (None, "", [], {}) or not any(
            item.evidence_quotes[field] in fragment
            for fragment in _source_fragments(source[field])
        ) for field in fields):
            continue
        review_derived = "reviews" in fields
        # One isolated review cannot support a generalized dimension assessment.
        single_after_sales_concern = (item.dimension == 'AFTER_SALES' and item.severity in {'MEDIUM', 'HIGH'})
        if review_derived and len(normalized_reviews(source)) < 2 and not single_after_sales_concern:
            continue
        confidence = min(item.confidence, run.interpretation.confidence, 0.7)
        if item.dimension == 'AFTER_SALES':
            confidence = min(confidence, 0.6)
            if review_derived and len(normalized_reviews(source)) < 2:
                confidence = min(confidence, 0.4)
        if confidence <= 0:
            continue
        evidence_id = f"supplier-dimension:{item.dimension.lower()}"
        dimensions.append(DimensionInput(
            dimension=item.dimension, confidence=confidence,
            signals=[RiskSignal(
                evidence_id=evidence_id, dimension=item.dimension,
                severity=SEVERITY[item.severity], reliability=confidence,
                source_kind="MODEL_INTERPRETATION", review_derived=review_derived,
                explanation=item.statement_vi,
            )],
        ))
        evidence.append({
            "evidence_id": evidence_id, "source_kind": "MODEL_INTERPRETATION",
            "source_field": None,
            "payload": {**item.model_dump(mode="json"), "confidence": confidence,
                        "policy": "supplier-dimensions.v2", "independently_verified": False,
                        "preliminary": item.dimension == "AFTER_SALES"},
        })
    return dimensions, evidence


def merge_dimension_inputs(dimensions: list[DimensionInput]) -> list[DimensionInput]:
    """Keep existing review/identity signals when supplier dimensions overlap."""
    grouped: dict[str, list[DimensionInput]] = {}
    for item in dimensions:
        grouped.setdefault(item.dimension, []).append(item)
    merged: list[DimensionInput] = []
    for dimension, items in grouped.items():
        signals = [signal for item in items for signal in item.signals]
        mass = sum(signal.reliability for signal in signals)
        confidence = sum(
            item.confidence * sum(signal.reliability for signal in item.signals)
            for item in items
        ) / mass if mass else 0.0
        merged.append(DimensionInput(dimension=dimension, confidence=confidence, signals=signals))
    return merged


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
