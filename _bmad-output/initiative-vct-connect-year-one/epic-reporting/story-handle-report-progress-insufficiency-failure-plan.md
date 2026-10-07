---
title: 'Handle progress, insufficiency, and failure states'
type: 'story'
ticket: '4'
created: '2026-10-08'
status: 'built'
baseline_revision: '1710c3ddbfd78991a229dbcca26a13dffbb2b72c'
route: 'full'
review: 'thorough'
---

## Intent

**Problem:** The web status card still reflected the pre-assessment tracer. It collapsed durable ASSESSING and REPORTING states into generic processing and told completed live extractions that no risk score existed even after the reporting pipeline had been added.

**Approach:** Present the actual durable state machine and keep terminal meaning separate from report meaning. Analysis polling owns queued/processing/assessing/reporting/retry/final/blocked states. Full-report and guest-preview components continue to own sufficient-versus-insufficient assessment meaning.

## State presentation

- QUEUED — request accepted; do not resubmit while waiting.
- PROCESSING — source/evidence processing.
- ASSESSING — evidence is being converted into Risk, Confidence and Coverage.
- REPORTING — assessed values are being persisted into the report before COMPLETED.
- FAILED_RETRYABLE — polling continues; the user is told not to resubmit and sees the next retry time when available.
- FAILED_FINAL — polling stops; the user receives a concrete recovery action.
- COMPLETED with blocked extraction — terminal extraction failure, no claim that a report exists, source-specific recovery remains visible.
- COMPLETED with partial/success evidence — source processing is complete; the UI loads the persisted report when available and otherwise retains extraction evidence.
- report/preview INSUFFICIENT_INFORMATION — remains explicitly distinct from LOW through the Story 4.2 and 4.3 renderers.

## Progress UI

The status card now mirrors four durable phases:

1. URL accepted
2. extraction/data preparation
3. assessment
4. persisted report

The progress marker is informational only; it does not synthesize a risk result. Terminal failures stop animation and show a next action. Retryable failures stay non-terminal and continue polling.

## Verification

- ASSESSING and REPORTING have dedicated labels, details and progress positions.
- retryable and final states expose different next actions.
- blocked source outcomes keep source-specific recovery and never claim report readiness.
- successful/partial source completion no longer uses the obsolete "no risk score" copy.
- existing full-report and guest-preview tests continue to prove insufficient information is not low risk.
- repository CI remains the merge gate.
