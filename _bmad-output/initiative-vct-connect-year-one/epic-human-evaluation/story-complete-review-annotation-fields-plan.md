---
title: Capture complete review annotation fields
type: story
ticket: 2
status: built
created: 2026-10-08
---

## Implementation
The blind reviewer form now requires sentiment, complaint category, severity, suspicious indicators, correctness, and human confidence, and accepts bounded free-text notes. The API validates enumerated values, a confidence between zero and one, notes of at most 2,000 characters, and unique permitted suspicious indicators. PostgreSQL migration 0016 stores every dimension with matching constraints. The submit transaction still inserts a single independent reviewer label before releasing the pinned model output; pre-submit case listing does not select model findings.

Value lists:
- sentiment: POSITIVE, NEGATIVE, NEUTRAL, MIXED, UNCERTAIN
- category: QUALITY, DELIVERY, AFTER_SALES, PRODUCT_MISMATCH, PACKAGING, OTHER, NONE, UNCERTAIN
- severity: NONE, LOW, MEDIUM, HIGH, UNCERTAIN
- suspicious: EXACT_DUPLICATE_TEXT, TIMING_BURST, RATING_TEXT_MISMATCH, REVIEW_VOLUME_INCONSISTENCY, SEMANTIC_NEAR_DUPLICATE, OTHER
- correctness: CORRECT, PARTIALLY_CORRECT, INCORRECT, UNCERTAIN

The correctness field is an independent evidence-consistency assessment; model agreement is evaluated only after the label is saved. Backfilled labels from Story 6.1 receive neutral/unknown migration defaults rather than fabricated evidence-specific values.

## Verification
The authorization and blind-comparison regression now sends a complete annotation, asserts the returned annotation, rejects invalid confidence and indicators, and keeps the repeat-label conflict. Existing migration rollback expectations include 0016. Full repository CI is the merge gate.
