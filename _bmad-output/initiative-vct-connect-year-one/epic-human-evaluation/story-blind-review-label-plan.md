---
title: Label one review blindly in the internal console
type: story
ticket: 1
created: 2026-10-08
status: built
risk: high
---

## Scope and trust boundary

Introduce the first reviewer-only text-review labeling slice. The API verifies the persisted INTERNAL_REVIEWER role, not a client-supplied role or Clerk custom claim.

- `GET /api/v1/internal/review-cases` returns bounded, completed text-review cases whose pinned `llm_review_runs.run_kind` is REVIEW_INTERPRETATION, excluding the requesting reviewer's prior labels.
- Its SELECT deliberately excludes model output, input payload, model identity and other reviewers' labels.
- `POST /api/v1/internal/review-cases/{run_id}/{ordinal}/label` accepts an independent sentiment from POSITIVE, NEGATIVE, NEUTRAL, MIXED, or UNCERTAIN.
- PostgreSQL stores one immutable label per reviewer/run/review ordinal. The model output and version provenance are fetched and released in the response only after successful insertion in the same transaction.
- Repeat attempts fail with 409 without a comparison; customers, guests, and ADMIN users are not reviewers and cannot access this workflow.
- The pinned model interpretation is run-level and may cite several reviews via evidence IDs. This initial tracer does not claim that a run-level finding is a one-to-one per-review verdict.

## Deliberate deferrals

Complete annotation fields and richer reviewer UI belong to Story 6.2; authenticated private media, double-review sampling, adjudication and benchmark aggregation belong to later stories. The first story exposes a minimal review queue through API for an internal console to consume, without bypassing any blind boundary.

## Verification

Role and pre-submit blindness tests assert customers/guests cannot read cases, model data remains absent before labeling, validation rejects unknown labels, first valid label yields the pinned comparison, and repeat submission is rejected. The PostgreSQL unique key additionally enforces independent-label immutability.

Full CI remains the merge gate.
