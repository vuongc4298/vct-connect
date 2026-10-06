---
title: 'Find recurring complaints and statistical review anomalies'
type: 'story'
ticket: '2'
created: '2026-10-07'
status: 'built'
baseline_revision: 'bdc6961d5d8f2dda1b577e8d352a8918a8845313'
route: 'full'
review: 'thorough'
---

<frozen-after-approval reason="user approved Epic 3 Story 3.2 on 2026-10-07">

## Intent

**Problem:** SupplierData can retain selected review text, but VCT Connect does not yet turn review evidence into reproducible complaint groups or statistical reliability signals.

**Approach:** Add a pure deterministic review-analysis module. Group recurring complaint topics with a fixed multilingual lexical taxonomy and calculate exact-duplicate, 24-hour timing-burst, high-rating/complaint-text mismatch, and impossible aggregate-volume signals. Every finding carries stable review evidence IDs and an explicit reliability value.

## Boundaries & Constraints

**Always:** Preserve review uncertainty. Treat missing timestamps, per-review ratings, and aggregate review counts as missing inputs rather than inferred facts. Keep the output reproducible for the same input. Keep evidence IDs linked to each topic and pattern.

**Never:** Label an individual review fake. Do not use embeddings or an LLM in this story; semantic near-duplicate clustering and structured interpretation are Story 3.3. Do not make these signals affect the final supplier risk score yet; scoring is Story 3.5. Do not integrate into the durable worker or add finding tables yet; Story 3.7 owns worker/persistence integration.

</frozen-after-approval>

## Contract

- schema version: `review-signals.v1`
- recurring complaint categories: Quality, Delivery, After-sales, Product mismatch, Packaging
- deterministic suspicious-pattern kinds:
  - exact duplicate text after Unicode/case/punctuation normalization
  - at least 3 timestamped reviews with at least 60% of the timestamped sample inside 24 hours
  - at least 2 complaint-bearing reviews carrying rating >= 4/5
  - aggregate review count lower than the number of captured review records
- review reliability combines a bounded sample-size factor with transparent pattern penalties; it is an evidence-reliability measure, not a supplier risk score.

## Current extraction limitation

The existing marketplace adapters intentionally retain only a bounded selected review sample and commonly omit per-review timestamp/rating fields. Some adapters also deduplicate selected review text during extraction. Therefore Story 3.2 exposes missing inputs explicitly and provides a fixture-level core API. Story 3.3/3.7 can consume richer permitted review evidence without changing this deterministic contract.

## Verification

- mixed fixtures expose recurring complaint topics plus duplicate/timing/rating-text signals with stable evidence IDs
- a single ambiguous complaint creates no recurring-topic or mismatch finding
- missing timestamps/ratings are reported instead of guessed
- aggregate counts larger than a bounded 20-review sample do not create a false volume anomaly
- no output field or message labels an individual review fake
