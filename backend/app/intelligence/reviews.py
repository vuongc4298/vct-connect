"""Deterministic Story 3.2 review signals.

This module intentionally uses no embeddings and no LLM. Story 3.3 owns
semantic clustering. Story 3.2 provides reproducible lexical complaint groups
and statistical signals with stable evidence IDs so later scoring can reduce
trust in review-derived evidence without declaring any individual review fake.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
import math
import re
import unicodedata
from typing import Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator


REVIEW_SCHEMA_VERSION = "review-signals.v1"
ComplaintCategory = Literal[
    "QUALITY", "DELIVERY", "AFTER_SALES", "PRODUCT_MISMATCH", "PACKAGING"
]
PatternKind = Literal[
    "EXACT_DUPLICATE_TEXT",
    "TIMING_BURST",
    "RATING_TEXT_MISMATCH",
    "REVIEW_VOLUME_INCONSISTENCY",
]

_COMPLAINT_LEXICON: dict[str, tuple[str, ...]] = {
    "QUALITY": (
        "poor quality", "bad quality", "defective", "broken", "poor stitching",
        "bad fabric", "thin fabric", "chất lượng kém", "bị lỗi", "bị rách",
        "质量差", "有瑕疵", "破损", "做工差",
    ),
    "DELIVERY": (
        "arrived late", "late delivery", "shipping delay", "slow shipping",
        "giao chậm", "giao trễ", "phát hàng chậm", "发货慢", "物流慢", "延迟",
    ),
    "AFTER_SALES": (
        "refund refused", "no refund", "return refused", "seller ignored",
        "no response", "không hoàn tiền", "không phản hồi", "đổi trả khó",
        "拒绝退款", "不退款", "客服不回复", "售后差",
    ),
    "PRODUCT_MISMATCH": (
        "not as described", "different from description", "wrong item",
        "wrong color", "wrong size", "không giống mô tả", "sai sản phẩm",
        "sai màu", "sai kích thước", "货不对板", "与描述不符", "颜色不符", "尺码不符",
    ),
    "PACKAGING": (
        "package damaged", "damaged packaging", "poor packaging",
        "bao bì hỏng", "đóng gói kém", "包装破损", "包装差",
    ),
}


def _normalized_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    text = re.sub(r"[^\w\u3400-\u9fff]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def _finite_rating(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or not 0 <= parsed <= 5:
        return None
    return parsed


def _parse_time(value: object) -> datetime | None:
    if value is None or not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


class ReviewEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=4000)
    source_url: str | None = Field(default=None, max_length=2048)
    rating: float | None = Field(default=None, ge=0, le=5)
    created_at: datetime | None = None

    @field_validator("created_at")
    @classmethod
    def timezone_required(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("created_at must include a timezone")
        return value


class ComplaintTopic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: ComplaintCategory
    review_count: int = Field(ge=2)
    evidence_ids: list[str] = Field(min_length=2)
    reliability: float = Field(ge=0, le=1)


class ReviewPattern(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: PatternKind
    strength: float = Field(ge=0, le=1)
    reliability: float = Field(ge=0, le=1)
    evidence_ids: list[str]
    details: dict[str, int | float | str]


class ReviewAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["review-signals.v1"] = REVIEW_SCHEMA_VERSION
    review_count: int = Field(ge=0)
    aggregate_review_count: int | None = Field(default=None, ge=0)
    complaint_topics: list[ComplaintTopic]
    suspicious_patterns: list[ReviewPattern]
    reliability: float = Field(ge=0, le=1)
    missing_inputs: list[str]


def _coerce_reviews(reviews: Sequence[Mapping[str, object]]) -> list[ReviewEvidence]:
    result: list[ReviewEvidence] = []
    ids: set[str] = set()
    for index, item in enumerate(reviews):
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        evidence_id = item.get("evidence_id")
        if not isinstance(evidence_id, str) or not evidence_id.strip():
            evidence_id = f"review:{index}"
        evidence_id = evidence_id.strip()
        if evidence_id in ids:
            raise ValueError("review evidence IDs must be unique")
        ids.add(evidence_id)
        result.append(ReviewEvidence(
            evidence_id=evidence_id,
            text=text.strip(),
            source_url=item.get("source_url") if isinstance(item.get("source_url"), str) else None,
            rating=_finite_rating(item.get("rating")),
            created_at=_parse_time(item.get("created_at")),
        ))
    return result


def _complaint_categories(text: str) -> set[str]:
    normalized = _normalized_text(text)
    found: set[str] = set()
    for category, phrases in _COMPLAINT_LEXICON.items():
        if any(_normalized_text(phrase) in normalized for phrase in phrases):
            found.add(category)
    return found


def _complaint_topics(reviews: Sequence[ReviewEvidence]) -> tuple[list[ComplaintTopic], dict[str, set[str]]]:
    evidence: dict[str, list[str]] = defaultdict(list)
    by_review: dict[str, set[str]] = {}
    for review in reviews:
        categories = _complaint_categories(review.text)
        by_review[review.evidence_id] = categories
        for category in sorted(categories):
            evidence[category].append(review.evidence_id)
    topics = [
        ComplaintTopic(
            category=category,
            review_count=len(ids),
            evidence_ids=ids,
            reliability=1.0,
        )
        for category, ids in sorted(evidence.items())
        if len(ids) >= 2
    ]
    return topics, by_review


def _duplicate_pattern(reviews: Sequence[ReviewEvidence]) -> ReviewPattern | None:
    groups: dict[str, list[str]] = defaultdict(list)
    for review in reviews:
        normalized = _normalized_text(review.text)
        if len(normalized) >= 8:
            groups[normalized].append(review.evidence_id)
    repeated = [ids for ids in groups.values() if len(ids) >= 2]
    if not repeated:
        return None
    repeated.sort(key=lambda ids: (-len(ids), ids))
    evidence_ids = sorted({evidence_id for ids in repeated for evidence_id in ids})
    repeated_reviews = sum(len(ids) for ids in repeated)
    strength = min(1.0, repeated_reviews / max(len(reviews), 1))
    return ReviewPattern(
        kind="EXACT_DUPLICATE_TEXT",
        strength=round(strength, 4),
        reliability=1.0,
        evidence_ids=evidence_ids,
        details={"duplicate_groups": len(repeated), "reviews_in_duplicate_groups": repeated_reviews},
    )


def _timing_pattern(reviews: Sequence[ReviewEvidence]) -> tuple[ReviewPattern | None, float]:
    timed = sorted((r for r in reviews if r.created_at is not None), key=lambda r: r.created_at)
    coverage = len(timed) / len(reviews) if reviews else 0.0
    if len(timed) < 3:
        return None, coverage
    best: list[ReviewEvidence] = []
    right = 0
    for left, review in enumerate(timed):
        if right < left:
            right = left
        while right < len(timed) and timed[right].created_at - review.created_at <= timedelta(hours=24):
            right += 1
        window = timed[left:right]
        if len(window) > len(best):
            best = window
    ratio = len(best) / len(timed)
    if len(best) < 3 or ratio < 0.6:
        return None, coverage
    return ReviewPattern(
        kind="TIMING_BURST",
        strength=round(ratio, 4),
        reliability=round(coverage, 4),
        evidence_ids=[r.evidence_id for r in best],
        details={"window_hours": 24, "reviews_in_window": len(best), "timestamped_reviews": len(timed)},
    ), coverage


def _rating_mismatch_pattern(
    reviews: Sequence[ReviewEvidence],
    complaint_by_review: Mapping[str, set[str]],
) -> tuple[ReviewPattern | None, float]:
    rated = [r for r in reviews if r.rating is not None]
    coverage = len(rated) / len(reviews) if reviews else 0.0
    mismatches = [
        r for r in rated
        if r.rating is not None and r.rating >= 4.0 and complaint_by_review.get(r.evidence_id)
    ]
    if len(mismatches) < 2:
        return None, coverage
    complaint_rated = [r for r in rated if complaint_by_review.get(r.evidence_id)]
    strength = len(mismatches) / max(len(complaint_rated), 1)
    return ReviewPattern(
        kind="RATING_TEXT_MISMATCH",
        strength=round(min(1.0, strength), 4),
        reliability=round(coverage, 4),
        evidence_ids=[r.evidence_id for r in mismatches],
        details={
            "high_rating_threshold": 4.0,
            "mismatched_reviews": len(mismatches),
            "rated_complaint_reviews": len(complaint_rated),
        },
    ), coverage


def _volume_pattern(reviews: Sequence[ReviewEvidence], aggregate_review_count: int | None) -> ReviewPattern | None:
    if aggregate_review_count is None or aggregate_review_count >= len(reviews):
        return None
    excess = len(reviews) - aggregate_review_count
    return ReviewPattern(
        kind="REVIEW_VOLUME_INCONSISTENCY",
        strength=round(min(1.0, excess / max(len(reviews), 1)), 4),
        reliability=1.0,
        evidence_ids=[r.evidence_id for r in reviews],
        details={"captured_reviews": len(reviews), "aggregate_review_count": aggregate_review_count},
    )


def analyze_review_signals(
    reviews: Sequence[Mapping[str, object]],
    *,
    aggregate_review_count: int | None = None,
) -> ReviewAnalysis:
    """Return deterministic review signals without asserting that a review is fake."""
    if aggregate_review_count is not None and (
        isinstance(aggregate_review_count, bool)
        or not isinstance(aggregate_review_count, int)
        or aggregate_review_count < 0
    ):
        raise ValueError("aggregate_review_count must be a non-negative integer or None")

    evidence = _coerce_reviews(reviews)
    topics, complaint_by_review = _complaint_topics(evidence)

    patterns: list[ReviewPattern] = []
    duplicate = _duplicate_pattern(evidence)
    if duplicate is not None:
        patterns.append(duplicate)

    timing, timing_coverage = _timing_pattern(evidence)
    if timing is not None:
        patterns.append(timing)

    mismatch, rating_coverage = _rating_mismatch_pattern(evidence, complaint_by_review)
    if mismatch is not None:
        patterns.append(mismatch)

    volume = _volume_pattern(evidence, aggregate_review_count)
    if volume is not None:
        patterns.append(volume)

    missing_inputs: list[str] = []
    if evidence and timing_coverage < 1:
        missing_inputs.append("review_timestamps")
    if evidence and rating_coverage < 1:
        missing_inputs.append("review_ratings")
    if aggregate_review_count is None:
        missing_inputs.append("aggregate_review_count")

    sample_factor = min(1.0, len(evidence) / 8) if evidence else 0.0
    weights = {
        "EXACT_DUPLICATE_TEXT": 0.35,
        "TIMING_BURST": 0.25,
        "RATING_TEXT_MISMATCH": 0.25,
        "REVIEW_VOLUME_INCONSISTENCY": 0.15,
    }
    penalty = sum(weights[p.kind] * p.strength * p.reliability for p in patterns)
    reliability = round(sample_factor * (1 - min(0.75, penalty)), 4)

    return ReviewAnalysis(
        review_count=len(evidence),
        aggregate_review_count=aggregate_review_count,
        complaint_topics=topics,
        suspicious_patterns=patterns,
        reliability=reliability,
        missing_inputs=missing_inputs,
    )


def analyze_supplier_reviews(supplier_data: Mapping[str, object]) -> ReviewAnalysis:
    """Adapter for current SupplierData snapshots; richer review fixtures may call the core directly."""
    reviews = supplier_data.get("reviews")
    review_list = reviews if isinstance(reviews, list) else []
    transaction_signals = supplier_data.get("transaction_signals")
    aggregate: int | None = None
    if isinstance(transaction_signals, Mapping):
        raw = transaction_signals.get("review_count")
        if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0:
            aggregate = raw
    return analyze_review_signals(review_list, aggregate_review_count=aggregate)
