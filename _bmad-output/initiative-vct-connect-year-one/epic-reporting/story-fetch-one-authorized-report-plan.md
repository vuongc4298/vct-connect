---
title: 'Fetch one authorized report from an assessment'
type: 'story'
ticket: '1'
created: '2026-10-07'
status: 'built'
baseline_revision: '44a2d2a3032a202b43aa57941db6968066520136'
route: 'full'
review: 'thorough'
---

<frozen-after-approval reason="user approved Stage 4 / Story 4.1 on 2026-10-07">

## Intent

**Problem:** Epic 3 persists an assessment and stops at REPORTING. Queue settlement can therefore occur before a buyer-facing report exists, and there is no owner-authorized report endpoint.

**Approach:** Build a deterministic Vietnamese report.v1 projection from persisted assessment/findings/evidence, persist it while the worker still owns the processing lease, then atomically transition REPORTING -> COMPLETED. Expose the full report only to the owning CUSTOMER.

## Report contract

report.v1 contains analysis ID, normalized source URL, platform and extraction timestamp; supplier identity fields when available; Vietnamese supplier summary; Risk, Confidence and Coverage as separate values; scoring version and dimensions; factory/trader assessment; review summary; evidence-linked findings; missing data; limitations; and pre-order verification actions.

No new LLM call is used to write the report. Report meaning is a reproducible projection of persisted versioned analysis output.

## Evidence linkage

Finding evidence IDs are resolved deterministically from review evidence IDs, media IDs plus linked review IDs, identity supporting evidence IDs, and supplier:<field> IDs. Raw snapshot review rows are exposed as review:<ordinal> evidence when a cited review did not already create a dedicated analysis_evidence row.

## State machine and replay

Queued supported analysis becomes PROCESSING -> ASSESSING -> REPORTING -> COMPLETED.

Assessment persistence retains the processing lease at REPORTING. claim_processing resumes REPORTING when an assessment already exists, ASSESSING when only a snapshot exists, and PROCESSING when no snapshot exists.

A report-stage failure becomes FAILED_RETRYABLE. On retry, the existing assessment causes direct REPORTING resume, so extraction and AI are not repeated.

Report insert plus COMPLETED transition and lease release occur in one transaction. Service Bus/local settlement happens only after that transaction commits.

## Authorization

Full report route: GET /api/v1/analyses/{analysis_id}/report.

Rules: valid Clerk session required; CUSTOMER role required; report must belong to that customer's analysis; non-owner receives 404; INTERNAL_REVIEWER/ADMIN are not granted this buyer-owner endpoint; no public/share-token route is introduced.

Public report sharing remains disabled pending a separate authorization/expiry policy.

## Persistence

Migration 0013_reports adds one immutable report per analysis and assessment with schema_version, language vi, JSON payload and created_at. The completed analysis also stores the assessment scoring version in analyses.scoring_version.

## Safety / meaning boundaries

**Always:** Keep Risk, Confidence and Coverage distinct; preserve missing evidence; show INSUFFICIENT_INFORMATION explicitly; retain evidence linkage and source provenance; generate report before queue acknowledgment.

**Never:** Turn missing evidence into low risk; invent evidence or fresh model findings during reporting; repeat AI because report generation failed; expose a full report to another customer or anonymous user; enable public sharing in Story 4.1.

## Verification

- report.v1 fixture exposes separate risk/confidence/coverage, evidence IDs, missing data, limitations and actions;
- insufficient-information fixture never becomes LOW;
- owner-only API test covers unauthenticated, foreign-customer and admin access;
- PostgreSQL worker test requires report persistence before COMPLETED;
- report-stage failure/retry reuses the stored assessment and causes no extra AI calls;
- multimodal report persistence contains no raw media bytes/data URLs;
- migration status/rollback includes 0013;
- full repository CI is the merge gate.

</frozen-after-approval>
