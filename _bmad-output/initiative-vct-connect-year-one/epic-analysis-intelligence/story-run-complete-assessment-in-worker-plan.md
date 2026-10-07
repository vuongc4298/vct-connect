---
title: 'Run the complete assessment in the analysis worker'
type: 'story'
ticket: '7'
created: '2026-10-07'
status: 'built'
baseline_revision: 'b2a18de12bbce92cfff8dca0bacefb59fb7725eb'
route: 'full'
review: 'thorough'
---

<frozen-after-approval reason="user approved Epic 3 Story 3.7 on 2026-10-07">

## Intent

**Problem:** Stories 3.1-3.5 provide independent interpretation, review, identity, and scoring modules, but live queue processing still stops after extraction and cannot hand a reproducible assessment to Reporting.

**Approach:** Add a durable worker checkpoint between extraction and assessment, compose the text-only assessment from normalized SupplierData, persist model provenance/findings/evidence/score atomically, and transition the still-owned job to REPORTING.

## State machine

Queued worker jobs now follow:

QUEUED / FAILED_RETRYABLE
→ PROCESSING
→ ASSESSING
→ REPORTING

- PROCESSING owns extraction.
- Extraction evidence is persisted before paid AI work.
- ASSESSING retains the processing lease and reuses the stored snapshot on retry.
- Successful assessment persistence and REPORTING transition occur in one transaction.
- REPORTING is terminal for the analysis worker; broker redelivery settles without re-extraction or AI calls.
- Synchronous import/capture/re-normalize flows keep their existing COMPLETED extraction behavior for now.

## Assessment composition

The worker composes:

1. Story 3.1 supplier interpretation.
2. Story 3.2 deterministic review signals.
3. Story 3.3 semantic review interpretation when YESCALE_EMBEDDING_MODEL is configured; otherwise review analysis degrades explicitly to deterministic signals rather than failing the whole assessment.
4. Story 3.4 factory/trader identity assessment.
5. Story 3.5 deterministic v0.1.0 Risk, Confidence, and Coverage.

Supplier interpretation is retained as contextual findings and does not directly choose the final score.
Review finding severity labels are converted to fixed deterministic numeric severities before entering the scorer.
Trader classification alone contributes no risk signal.
Contradictory identity evidence may contribute a bounded identity-risk signal; missing identity evidence remains missing rather than zero-risk.

## Persistence

Migration 0011 adds:

- ASSESSING and REPORTING analysis/status-event states;
- analyses.assessed_at;
- analysis_assessments, one per analysis/snapshot;
- analysis_findings with stable per-assessment finding keys;
- analysis_evidence with stable per-assessment evidence IDs;
- llm_review_runs.run_kind and assessment linkage.

Historical/manual Story 3.1 model runs remain valid. Worker uniqueness is scoped to (assessment_id, run_kind), so existing multiple manual runs for one analysis do not block migration.

Supplier model provenance is stored as SUPPLIER_INTERPRETATION.
Semantic review model provenance is stored as REVIEW_INTERPRETATION, with embedding request/model/usage/cost provenance nested alongside chat provenance. Vectors themselves are not persisted.

## Replay / spend boundary

A successful assessment is persisted in the same transaction that moves the job to REPORTING and releases the processing lease. A replay of the same queue message observes REPORTING and performs settlement only.

This guarantees no duplicate AI spend for successful broker replay. As with any external model API without an idempotency-key contract, a process crash after a provider accepts a request but before durable persistence can still produce a repeated external call on retry; YEScale request IDs remain recorded for audit/reconciliation.

## Configuration

- YESCALE_API_KEY remains server-only and comes from Key Vault in Azure.
- YESCALE_MODEL remains the pinned chat candidate.
- YESCALE_EMBEDDING_MODEL is optional. Empty means deterministic review analysis only.
- The analysis Container Apps Job receives all three values; API/web/dispatcher do not receive the key.

## Verification

- pure fixture composes supplier, review, identity and versioned scoring outputs;
- missing embedding model falls back to deterministic review analysis without a second LLM call;
- PostgreSQL worker fixture persists extraction, enters ASSESSING, stores one assessment plus model runs/findings/evidence, and reaches REPORTING;
- replayed local queue work for a REPORTING analysis neither re-extracts nor invokes the assessor;
- migration rollback expectations include 0011;
- full repository CI remains the merge gate.

</frozen-after-approval>
