---
title: 'Integrate permitted multimodal evidence into assessment'
type: 'story'
ticket: '9'
created: '2026-10-07'
status: 'built'
baseline_revision: '702450a8c663a58f9bd7fe0ebd591d9b2c4b4be2'
route: 'full'
review: 'thorough'
---

<frozen-after-approval reason="user approved Epic 3 Story 3.9 on 2026-10-07">

## Intent

**Problem:** Story 3.6 can interpret approved review images and sampled video frames, while Story 3.7 runs the durable text assessment. The two paths are not yet connected.

**Approach:** Make permitted media an optional input to the complete assessment and add a worker media-loader boundary. Media consistency modifies only the reliability of the review claims it is linked to; it never creates an independent supplier-risk verdict. Persist sanitized media findings, private provenance, and model-run metadata alongside the same assessment before REPORTING.

## Acquisition boundary

The current extraction contract and supplier_reviews rows contain review text but no approved media bytes or retention mechanism. Story 3.9 therefore does not fetch arbitrary review-media URLs and does not add raw-media storage.

The worker accepts an optional permitted-media loader with the boundary:

(store, supplier_snapshot_id, supplier_data) -> Sequence[ReviewMediaInput]

If no loader is configured, the worker follows the existing text-only assessment path with no media call or delay. A future source-specific acquisition component may supply transient ReviewMediaInput values only after source terms and retention policy permit it.

## Deterministic media effect

Story 3.6 model output remains constrained to consistency with a linked review claim:

- SUPPORTS base multiplier: 1.10
- PARTIALLY_SUPPORTS: 1.00
- CONTRADICTS: 0.50
- CANNOT_DETERMINE: 1.00

The applied multiplier is confidence-weighted:

1 + (base_multiplier - 1) * media_finding_confidence

Multiple media items for one review are averaged. For a structured semantic review finding, the factors for its cited review evidence IDs are averaged and multiply that review-derived risk signal's reliability. The aggregate factor also adjusts review reliability used in the separate overall Confidence calculation.

This means media can change deterministic risk by changing the relative evidentiary weight of review-derived signals, but it cannot invent a new severity, dimension, critical floor, or supplier-risk label.

## Persistence

Migration 0012:

- permits MEDIA_INTERPRETATION as an assessment-linked llm_review_runs.run_kind;
- adds nullable analysis_assessments.media_analysis JSONB.

Accessible media model runs store prompt/model/token/cost/request provenance using the existing immutable model-run table. Missing-only media has no provider response and therefore no paid model-run row.

analysis_findings stores MEDIA_CONSISTENCY findings.
analysis_evidence stores REVIEW_MEDIA provenance.

Raw data URLs and media bytes are never written to analysis_assessments, llm_review_runs, analysis_findings, or analysis_evidence. Persisted provenance contains private_ref, access state, MIME type, timestamp, and SHA-256 only.

## Replay and report behavior

The Story 3.7 ASSESSING -> REPORTING transaction remains unchanged. Media enrichment is part of the same AssessmentBundle, so successful queue replay still observes REPORTING and spends no additional AI.

Text-only jobs do not require a media loader and keep the existing model-run count/path.

## Verification

- a permitted image fixture is interpreted inside build_assessment;
- contradictory media deterministically reduces the weight of the linked high-severity review claim;
- text-only assessment makes zero multimodal calls;
- raw media data URLs are absent from persistable media payload/provenance;
- PostgreSQL worker fixture proves media_loader -> same REPORTING path;
- persisted worker assessment contains MEDIA_INTERPRETATION, MEDIA_CONSISTENCY, and REVIEW_MEDIA provenance with no raw bytes;
- migration status/rollback coverage includes 0012;
- full repository CI is the merge gate.

</frozen-after-approval>
