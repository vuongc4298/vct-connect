---
title: 'Refactor analysis intelligence boundaries'
type: 'story'
ticket: '8'
created: '2026-10-07'
status: 'built'
baseline_revision: 'b17d71b1800920a32928224e4a9a8513771ab517'
route: 'full'
review: 'thorough'
---

<frozen-after-approval reason="user approved Epic 3 Story 3.8 on 2026-10-07">

## Intent

**Problem:** Epic 3 is functionally complete, but complete-assessment orchestration mixes deterministic policy, provider calls, persistence serialization, and queue execution. Story 3.2 recurring complaint topics are computed but were not emitted into the integrated finding set.

**Approach:** Refactor internal module boundaries without changing the public assessment API, scoring version, database schema, worker state machine, replay semantics, model provenance shape, or multimodal privacy contract. Close the deferred complaint-topic finding gap without making complaint topics risk signals.

## Frozen contracts

Story 3.8 must not change:

- scoring_version v0.1.0 or supplier-risk.v0.1 output rules;
- seven dimension weights, confidence factors, thresholds, manipulation adjustments, or critical-floor eligibility;
- build_assessment(...) public call shape and AssessmentBundle fields;
- finding/evidence keys already emitted by Stories 3.7/3.9;
- persisted assessment/model-run JSON shapes;
- PROCESSING -> ASSESSING -> REPORTING semantics;
- successful replay behavior (no repeated assessment/model calls after REPORTING);
- permitted-media privacy boundary: raw media/data URLs remain transient and unpersisted.

No database migration is required.

## Refactored boundaries

### assessment.py

Now owns orchestration only: supplier interpretation, deterministic/semantic review interpretation, optional permitted-media interpretation, identity assessment, deterministic scorer invocation, and final AssessmentBundle assembly.

### assessment_policy.py

Owns deterministic transformations only: stable review evidence IDs and aggregate review count, media consistency reliability multipliers, structured review finding -> deterministic risk-signal mapping, review manipulation findings/signals, factory/trader contradiction mapping, supplier/media finding and evidence records, and first-write-wins evidence deduplication. This module performs no provider calls and no persistence.

### assessment_provenance.py

Owns immutable persistence serialization only: supplier/review/media model-run dictionaries, token/cost/latency/request provenance, deterministic vs semantic review JSON payload, and sanitized media payload. assessment_store.py remains responsible for database locking, inserts, and the atomic REPORTING handoff.

### worker_assessment.py

Owns the worker-facing assessment execution boundary: provider capability check, durable snapshot loading, optional permitted-media loader, YEScale construction, complete AssessmentBundle construction, and atomic persistence/handoff. backend/worker/main.py remains focused on extraction, queue ownership, retries, settlement, and DLQ behavior.

## Deferred review findings

Story 3.2 complaint_topics are now emitted as REVIEW_COMPLAINT_TOPIC findings with stable key review-topic:<index>:<category>, reporting-only dimension mapping, null severity, deterministic topic reliability, and the original ComplaintTopic payload.

Complaint topics do not create RiskSignal values and therefore do not change risk dimensions or overall scoring.

Their review evidence IDs are linked into analysis_evidence when no earlier suspicious-pattern evidence row owns that ID. Existing suspicious-pattern evidence payloads retain precedence, preserving prior evidence linkage.

## Verification

- fixed v0.1.0 scoring fixtures remain unchanged;
- deterministic recurring complaint topics appear as findings while PRODUCT_QUALITY remains missing when no semantic severity finding exists;
- existing suspicious-pattern evidence payloads remain unchanged when complaint-topic linkage overlaps;
- semantic review and multimodal fixtures retain existing risk/provenance behavior;
- live PostgreSQL worker assessment still reaches REPORTING with the same scoring version and replay behavior;
- raw media privacy tests remain unchanged;
- no migration is introduced;
- full repository CI is the merge gate.

</frozen-after-approval>
