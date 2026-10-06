from backend.app.intelligence.reviews import (
    REVIEW_SCHEMA_VERSION,
    analyze_review_signals,
    analyze_supplier_reviews,
)


def mixed_fixture():
    return [
        {
            "evidence_id": "r1",
            "text": "Poor quality and poor stitching.",
            "rating": 5,
            "created_at": "2026-10-01T08:00:00+00:00",
        },
        {
            "evidence_id": "r2",
            "text": "Poor quality and poor stitching!",
            "rating": 5,
            "created_at": "2026-10-01T08:10:00+00:00",
        },
        {
            "evidence_id": "r3",
            "text": "Arrived late; shipping delay was unacceptable.",
            "rating": 4,
            "created_at": "2026-10-01T08:20:00+00:00",
        },
        {
            "evidence_id": "r4",
            "text": "Arrived late; shipping delay was unacceptable.",
            "rating": 4,
            "created_at": "2026-10-01T09:00:00+00:00",
        },
        {
            "evidence_id": "r5",
            "text": "Seller ignored me and no response after I asked for a return.",
            "rating": 2,
            "created_at": "2026-10-04T09:00:00+00:00",
        },
        {
            "evidence_id": "r6",
            "text": "Seller ignored me and no response after I asked for a return.",
            "rating": 1,
            "created_at": "2026-10-05T09:00:00+00:00",
        },
        {
            "evidence_id": "r7",
            "text": "Useful neutral note about sizing.",
            "rating": 3,
            "created_at": "2026-10-06T09:00:00+00:00",
        },
        {
            "evidence_id": "r8",
            "text": "Useful neutral note about material.",
            "rating": 3,
            "created_at": "2026-10-07T09:00:00+00:00",
        },
    ]


def test_mixed_fixture_exposes_recurring_topics_and_statistical_patterns():
    result = analyze_review_signals(mixed_fixture(), aggregate_review_count=8)
    assert result.schema_version == REVIEW_SCHEMA_VERSION
    topics = {topic.category: topic for topic in result.complaint_topics}
    assert set(topics) == {"QUALITY", "DELIVERY", "AFTER_SALES"}
    assert topics["QUALITY"].evidence_ids == ["r1", "r2"]
    assert topics["DELIVERY"].evidence_ids == ["r3", "r4"]
    assert topics["AFTER_SALES"].evidence_ids == ["r5", "r6"]

    patterns = {pattern.kind: pattern for pattern in result.suspicious_patterns}
    assert patterns["EXACT_DUPLICATE_TEXT"].evidence_ids == ["r1", "r2", "r3", "r4", "r5", "r6"]
    assert patterns["TIMING_BURST"].evidence_ids == ["r1", "r2", "r3", "r4"]
    assert patterns["RATING_TEXT_MISMATCH"].evidence_ids == ["r1", "r2", "r3", "r4"]
    assert "REVIEW_VOLUME_INCONSISTENCY" not in patterns
    assert result.missing_inputs == []
    assert 0 < result.reliability < 1


def test_punctuation_and_case_do_not_hide_exact_duplicate_text():
    result = analyze_review_signals([
        {"evidence_id": "a", "text": "BAD QUALITY!!!"},
        {"evidence_id": "b", "text": "bad   quality"},
    ])
    pattern = result.suspicious_patterns[0]
    assert pattern.kind == "EXACT_DUPLICATE_TEXT"
    assert pattern.evidence_ids == ["a", "b"]


def test_one_ambiguous_review_does_not_create_recurring_or_mismatch_claim():
    result = analyze_review_signals([
        {"evidence_id": "one", "text": "Poor quality", "rating": 5},
    ], aggregate_review_count=1)
    assert result.complaint_topics == []
    assert result.suspicious_patterns == []
    assert result.reliability == 0.125


def test_timing_signal_requires_three_reviews_and_sixty_percent_of_timestamped_sample():
    result = analyze_review_signals([
        {"evidence_id": "a", "text": "neutral one", "created_at": "2026-01-01T00:00:00+00:00"},
        {"evidence_id": "b", "text": "neutral two", "created_at": "2026-01-01T01:00:00+00:00"},
        {"evidence_id": "c", "text": "neutral three", "created_at": "2026-01-01T02:00:00+00:00"},
        {"evidence_id": "d", "text": "neutral four", "created_at": "2026-01-10T00:00:00+00:00"},
        {"evidence_id": "e", "text": "neutral five", "created_at": "2026-01-20T00:00:00+00:00"},
    ], aggregate_review_count=5)
    pattern = next(p for p in result.suspicious_patterns if p.kind == "TIMING_BURST")
    assert pattern.strength == 0.6
    assert pattern.reliability == 1.0


def test_missing_timestamp_and_rating_inputs_are_explicit_not_guessed():
    result = analyze_review_signals([
        {"evidence_id": "a", "text": "Poor quality"},
        {"evidence_id": "b", "text": "Poor quality"},
    ])
    assert result.missing_inputs == [
        "review_timestamps", "review_ratings", "aggregate_review_count"
    ]
    assert all(p.kind not in {"TIMING_BURST", "RATING_TEXT_MISMATCH"} for p in result.suspicious_patterns)


def test_review_volume_signal_only_flags_impossible_aggregate_less_than_captured():
    result = analyze_review_signals([
        {"evidence_id": "a", "text": "neutral one"},
        {"evidence_id": "b", "text": "neutral two"},
        {"evidence_id": "c", "text": "neutral three"},
    ], aggregate_review_count=2)
    pattern = next(p for p in result.suspicious_patterns if p.kind == "REVIEW_VOLUME_INCONSISTENCY")
    assert pattern.details == {"captured_reviews": 3, "aggregate_review_count": 2}
    assert pattern.evidence_ids == ["a", "b", "c"]


def test_large_aggregate_with_bounded_review_sample_is_not_called_suspicious():
    result = analyze_review_signals([
        {"evidence_id": f"r{i}", "text": f"neutral sample {i}"}
        for i in range(20)
    ], aggregate_review_count=2500)
    assert all(p.kind != "REVIEW_VOLUME_INCONSISTENCY" for p in result.suspicious_patterns)


def test_supplier_data_adapter_uses_review_count_when_numeric():
    result = analyze_supplier_reviews({
        "reviews": [
            {"text": "质量差", "source_url": "https://example.test/a"},
            {"text": "质量差", "source_url": "https://example.test/a"},
        ],
        "transaction_signals": {"review_count": 10},
    })
    assert result.aggregate_review_count == 10
    assert result.review_count == 2
    assert result.complaint_topics[0].category == "QUALITY"


def test_duplicate_evidence_ids_are_rejected():
    try:
        analyze_review_signals([
            {"evidence_id": "same", "text": "one text"},
            {"evidence_id": "same", "text": "another text"},
        ])
    except ValueError as exc:
        assert "unique" in str(exc)
    else:
        raise AssertionError("duplicate evidence IDs must fail")


def test_invalid_optional_rating_or_timestamp_is_treated_as_missing_input():
    result = analyze_review_signals([
        {"evidence_id": "a", "text": "neutral one", "rating": "not-a-number", "created_at": "not-a-date"},
        {"evidence_id": "b", "text": "neutral two", "rating": 9, "created_at": "2026-01-01"},
    ])
    assert "review_timestamps" in result.missing_inputs
    assert "review_ratings" in result.missing_inputs


def test_output_never_labels_an_individual_review_fake():
    result = analyze_review_signals(mixed_fixture(), aggregate_review_count=8)
    serialized = result.model_dump_json().casefold()
    assert '"fake"' not in serialized
    assert "fake review" not in serialized
