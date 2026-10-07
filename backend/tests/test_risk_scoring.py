import pytest

from backend.app.intelligence.scoring import (
    CONFIDENCE_FACTOR_WEIGHTS,
    CRITICAL_RISK_FLOOR,
    DIMENSION_WEIGHTS,
    SCORING_VERSION,
    ConfidenceFactors,
    DimensionInput,
    RiskSignal,
    score_supplier_risk,
)


def signal(
    evidence_id,
    dimension,
    severity,
    *,
    reliability=1.0,
    importance=1.0,
    source_kind="EXTRACTION",
    review_derived=False,
    independently_verified=False,
    corroborating_evidence_count=1,
    critical_candidate=False,
):
    return RiskSignal(
        evidence_id=evidence_id,
        dimension=dimension,
        severity=severity,
        reliability=reliability,
        importance=importance,
        source_kind=source_kind,
        review_derived=review_derived,
        independently_verified=independently_verified,
        corroborating_evidence_count=corroborating_evidence_count,
        critical_candidate=critical_candidate,
        explanation=f"fixture {evidence_id}",
    )


def full_dimensions(*, manipulation=0, review_derived=True):
    return [
        DimensionInput(
            dimension="PRODUCT_QUALITY",
            confidence=0.8,
            signals=[signal("quality", "PRODUCT_QUALITY", 60, review_derived=review_derived, source_kind="REVIEW" if review_derived else "EXTRACTION")],
        ),
        DimensionInput(
            dimension="SUPPLIER_IDENTITY",
            confidence=0.8,
            signals=[signal("identity", "SUPPLIER_IDENTITY", 40)],
        ),
        DimensionInput(
            dimension="DELIVERY",
            confidence=0.8,
            signals=[signal("delivery", "DELIVERY", 50, review_derived=review_derived, source_kind="REVIEW" if review_derived else "EXTRACTION")],
        ),
        DimensionInput(
            dimension="REVIEW_MANIPULATION",
            confidence=0.8,
            signals=[signal("manipulation", "REVIEW_MANIPULATION", manipulation, source_kind="DERIVED")],
        ),
        DimensionInput(
            dimension="AFTER_SALES",
            confidence=0.8,
            signals=[signal("after-sales", "AFTER_SALES", 55, review_derived=review_derived, source_kind="REVIEW" if review_derived else "EXTRACTION")],
        ),
        DimensionInput(
            dimension="PRICING",
            confidence=0.8,
            signals=[signal("pricing", "PRICING", 30)],
        ),
        DimensionInput(
            dimension="COMMUNICATION",
            confidence=0.8,
            signals=[signal("communication", "COMMUNICATION", 20)],
        ),
    ]


def high_confidence_factors():
    return ConfidenceFactors(
        data_coverage=0.9,
        source_reliability=0.8,
        sample_adequacy=0.7,
        data_freshness=0.6,
    )


def test_v010_dimension_and_confidence_weights_are_exact():
    assert SCORING_VERSION == "v0.1.0"
    assert DIMENSION_WEIGHTS == {
        "PRODUCT_QUALITY": 0.25,
        "SUPPLIER_IDENTITY": 0.15,
        "DELIVERY": 0.15,
        "REVIEW_MANIPULATION": 0.15,
        "AFTER_SALES": 0.15,
        "PRICING": 0.10,
        "COMMUNICATION": 0.05,
    }
    assert sum(DIMENSION_WEIGHTS.values()) == pytest.approx(1.0)
    assert CONFIDENCE_FACTOR_WEIGHTS == {
        "data_coverage": 0.40,
        "source_reliability": 0.25,
        "sample_adequacy": 0.20,
        "data_freshness": 0.15,
    }


def test_dimension_formula_reliability_weights_signal_severity():
    result = score_supplier_risk([
        DimensionInput(
            dimension="PRODUCT_QUALITY",
            confidence=1.0,
            signals=[
                signal("q1", "PRODUCT_QUALITY", 80, reliability=1.0, importance=1.0),
                signal("q2", "PRODUCT_QUALITY", 20, reliability=0.5, importance=1.0),
            ],
        )
    ], confidence_factors=high_confidence_factors())
    dimension = next(d for d in result.dimensions if d.dimension == "PRODUCT_QUALITY")
    assert dimension.risk == pytest.approx((80 + 10) / 1.5, abs=0.0001)


def test_overall_risk_uses_dimension_weight_times_effective_confidence():
    result = score_supplier_risk(
        full_dimensions(manipulation=0),
        confidence_factors=high_confidence_factors(),
    )
    # All dimension confidences are equal and there is no manipulation adjustment,
    # so the configured dimension weights reduce to their direct weighted average.
    expected = (
        0.25 * 60
        + 0.15 * 40
        + 0.15 * 50
        + 0.15 * 0
        + 0.15 * 55
        + 0.10 * 30
        + 0.05 * 20
    )
    assert result.overall_risk == pytest.approx(expected, abs=0.0001)
    assert result.label == "MODERATE"


def test_confidence_is_separate_weighted_factor_score():
    result = score_supplier_risk(
        full_dimensions(),
        confidence_factors={
            "data_coverage": 0.9,
            "source_reliability": 0.8,
            "sample_adequacy": 0.7,
            "data_freshness": 0.6,
        },
    )
    assert result.confidence == pytest.approx(
        0.40 * 0.9 + 0.25 * 0.8 + 0.20 * 0.7 + 0.15 * 0.6
    )
    assert result.data_coverage == 0.9


@pytest.mark.parametrize(
    ("risk", "expected"),
    [(0, "LOW"), (34, "LOW"), (35, "MODERATE"), (64, "MODERATE"), (65, "HIGH"), (100, "HIGH")],
)
def test_user_facing_risk_thresholds(risk, expected):
    result = score_supplier_risk([
        DimensionInput(
            dimension="PRODUCT_QUALITY",
            confidence=1.0,
            signals=[signal("only", "PRODUCT_QUALITY", risk)],
        )
    ], confidence_factors={
        "data_coverage": 1,
        "source_reliability": 1,
        "sample_adequacy": 1,
        "data_freshness": 1,
    })
    assert result.label == expected


def test_low_coverage_returns_insufficient_information_even_when_risk_is_low():
    result = score_supplier_risk([
        DimensionInput(
            dimension="PRODUCT_QUALITY",
            confidence=1,
            signals=[signal("q", "PRODUCT_QUALITY", 5)],
        )
    ], confidence_factors={
        "data_coverage": 0.4499,
        "source_reliability": 1,
        "sample_adequacy": 1,
        "data_freshness": 1,
    })
    assert result.overall_risk == 5
    assert result.label == "INSUFFICIENT_INFORMATION"


def test_low_confidence_returns_insufficient_information():
    result = score_supplier_risk([
        DimensionInput(
            dimension="PRODUCT_QUALITY",
            confidence=1,
            signals=[signal("q", "PRODUCT_QUALITY", 80)],
        )
    ], confidence_factors={
        "data_coverage": 0.45,
        "source_reliability": 0,
        "sample_adequacy": 0,
        "data_freshness": 0,
    })
    assert result.confidence == 0.18
    assert result.label == "INSUFFICIENT_INFORMATION"


def test_missing_dimension_is_unknown_not_zero_risk():
    result = score_supplier_risk([
        DimensionInput(
            dimension="PRICING",
            confidence=0.8,
            signals=[signal("p", "PRICING", 70)],
        )
    ], confidence_factors=high_confidence_factors())
    assert result.overall_risk == 70
    assert "PRODUCT_QUALITY" in result.missing_dimensions
    quality = next(d for d in result.dimensions if d.dimension == "PRODUCT_QUALITY")
    assert quality.risk is None
    assert quality.effective_confidence == 0


def test_review_manipulation_reduces_only_review_derived_quality_delivery_and_after_sales_confidence():
    baseline = score_supplier_risk(
        full_dimensions(manipulation=0),
        confidence_factors=high_confidence_factors(),
    )
    manipulated = score_supplier_risk(
        full_dimensions(manipulation=100),
        confidence_factors=high_confidence_factors(),
    )
    baseline_by = {d.dimension: d for d in baseline.dimensions}
    manipulated_by = {d.dimension: d for d in manipulated.dimensions}

    for name in ("PRODUCT_QUALITY", "DELIVERY", "AFTER_SALES"):
        assert baseline_by[name].effective_confidence == 0.8
        assert manipulated_by[name].effective_confidence == 0.4
        assert manipulated_by[name].review_manipulation_adjustment == 0.5

    for name in ("SUPPLIER_IDENTITY", "PRICING", "COMMUNICATION", "REVIEW_MANIPULATION"):
        assert manipulated_by[name].review_manipulation_adjustment == 0.0


def test_non_review_quality_evidence_is_not_downweighted_by_manipulation():
    result = score_supplier_risk(
        full_dimensions(manipulation=100, review_derived=False),
        confidence_factors=high_confidence_factors(),
    )
    quality = next(d for d in result.dimensions if d.dimension == "PRODUCT_QUALITY")
    assert quality.review_derived_share == 0
    assert quality.effective_confidence == 0.8


def test_mixed_review_and_nonreview_evidence_gets_proportional_adjustment():
    dimensions = full_dimensions(manipulation=100)
    dimensions[0] = DimensionInput(
        dimension="PRODUCT_QUALITY",
        confidence=0.8,
        signals=[
            signal("review-q", "PRODUCT_QUALITY", 80, review_derived=True, source_kind="REVIEW"),
            signal("inspection-q", "PRODUCT_QUALITY", 80, review_derived=False, source_kind="EXTRACTION"),
        ],
    )
    result = score_supplier_risk(dimensions, confidence_factors=high_confidence_factors())
    quality = next(d for d in result.dimensions if d.dimension == "PRODUCT_QUALITY")
    assert quality.review_derived_share == 0.5
    assert quality.review_manipulation_adjustment == 0.25
    assert quality.effective_confidence == 0.6


def test_approved_verified_critical_signal_applies_high_risk_floor():
    dimensions = full_dimensions(manipulation=0, review_derived=False)
    dimensions[1] = DimensionInput(
        dimension="SUPPLIER_IDENTITY",
        confidence=0.95,
        signals=[
            signal(
                "verified-identity-critical",
                "SUPPLIER_IDENTITY",
                95,
                reliability=0.95,
                source_kind="VERIFIED_DOCUMENT",
                independently_verified=True,
                corroborating_evidence_count=2,
                critical_candidate=True,
            )
        ],
    )
    result = score_supplier_risk(dimensions, confidence_factors=high_confidence_factors())
    assert result.critical_floor == CRITICAL_RISK_FLOOR
    assert result.critical_evidence_ids == ["verified-identity-critical"]
    assert result.overall_risk >= 65
    assert result.label == "HIGH"


def test_one_ambiguous_review_can_never_trigger_critical_floor():
    result = score_supplier_risk([
        DimensionInput(
            dimension="PRODUCT_QUALITY",
            confidence=1.0,
            signals=[
                signal(
                    "angry-review",
                    "PRODUCT_QUALITY",
                    100,
                    reliability=1.0,
                    source_kind="REVIEW",
                    review_derived=True,
                    independently_verified=True,
                    corroborating_evidence_count=10,
                    critical_candidate=True,
                )
            ],
        )
    ], confidence_factors={
        "data_coverage": 1,
        "source_reliability": 1,
        "sample_adequacy": 1,
        "data_freshness": 1,
    })
    assert result.critical_floor is None
    assert result.critical_evidence_ids == []


@pytest.mark.parametrize("change", [
    {"severity": 89.9},
    {"reliability": 0.899},
    {"independently_verified": False},
    {"corroborating_evidence_count": 1},
    {"source_kind": "PLATFORM_PROFILE"},
    {"critical_candidate": False},
])
def test_critical_floor_fails_closed_when_any_eligibility_rule_is_missing(change):
    kwargs = dict(
        severity=95,
        reliability=0.95,
        source_kind="VERIFIED_DOCUMENT",
        independently_verified=True,
        corroborating_evidence_count=2,
        critical_candidate=True,
    )
    kwargs.update(change)
    severity = kwargs.pop("severity")
    result = score_supplier_risk([
        DimensionInput(
            dimension="SUPPLIER_IDENTITY",
            confidence=1,
            signals=[signal("candidate", "SUPPLIER_IDENTITY", severity, **kwargs)],
        )
    ], confidence_factors={
        "data_coverage": 1,
        "source_reliability": 1,
        "sample_adequacy": 1,
        "data_freshness": 1,
    })
    assert result.critical_floor is None


def test_duplicate_dimensions_are_rejected():
    item = DimensionInput(
        dimension="PRICING",
        confidence=1,
        signals=[signal("p", "PRICING", 20)],
    )
    with pytest.raises(ValueError, match="at most once"):
        score_supplier_risk([item, item], confidence_factors=high_confidence_factors())


def test_dimension_rejects_signal_for_another_dimension():
    with pytest.raises(Exception):
        DimensionInput(
            dimension="PRICING",
            confidence=1,
            signals=[signal("q", "PRODUCT_QUALITY", 20)],
        )
