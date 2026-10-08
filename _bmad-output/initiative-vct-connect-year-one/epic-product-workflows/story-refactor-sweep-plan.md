---
title: Stage 5 refactor sweep
type: story
ticket: 8
status: built
created: 2026-10-08
---

## Scope

Review Stage 5 account, history, Watchlist, trial, and extension changes without loosening authorization, evidence minimization or trial expiry. Existing backend owner-scoped SQL, quota-at-admission checking and selected DOM boundaries remain authoritative and unchanged.

### Hardening applied

Extension verdict presentation now accepts a risk label, confidence, or coverage only when a persisted report belongs to the currently displayed analysis ID and that analysis has reached COMPLETED. This prevents displaying a previous or unrelated report after an asynchronous result transition, even if stale data reaches the renderer.

Regression tests cover a foreign analysis report and a stale report associated with an ASSESSING analysis, alongside the existing incomplete and blocked cases. No new scoring, payment, source-site permission, or report-sharing paths were introduced.

## Verification

Full repository CI remains required before merge. The backend access and trial tests, extension page admission/privacy tests, report tests and Chromium/PostgreSQL integration suites remain in the existing pipeline.
