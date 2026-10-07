---
title: 'Show a limited and honest guest preview'
type: 'story'
ticket: '3'
created: '2026-10-08'
status: 'built'
baseline_revision: 'd2e2cb22e488f00e055d90a699eb9cad16012d4f'
route: 'full'
review: 'thorough'
---

## Intent

**Problem:** Anonymous users can submit and poll a guest analysis, but the completed state previously showed only placeholder fixture copy. Story 4.3 needs a real preview without exposing the authenticated full report or implying that sparse public evidence means low risk.

**Approach:** Derive a deterministic `guest-preview.v1` projection from the persisted `report.v1`. Authorize it with the same opaque guest-browser key used for guest status reads. Render only coverage, confidence, missing-data context, uncertainty/limitations, and a registration/extension next step.

## Public projection

The guest preview may expose:

- analysis/platform/supplier identity needed to identify the preview;
- extraction timestamp;
- actual Confidence and Coverage values;
- whether the underlying assessment is explicitly `INSUFFICIENT_INFORMATION` or merely withheld as a limited preview;
- missing source fields, missing risk dimensions, uncertainty statements, and report limitations;
- a registration-required flag.

It must not expose:

- overall Risk score or LOW/MODERATE/HIGH verdict;
- per-dimension risk scores;
- key risks, positive findings, or other findings;
- evidence payloads or evidence IDs;
- detailed recommended-action output;
- factory/trader or review-analysis internals.

## Authorization

Route: `GET /api/v1/guest-analyses/{analysis_id}/preview`.

The backend hashes the opaque guest key and requires it to match the original GUEST analysis. The same 30-day guest-read window applies. A missing, expired, foreign-browser, non-completed, or report-less analysis returns 404.

The customer endpoint `GET /api/v1/analyses/{analysis_id}/report` remains unchanged and Clerk/CUSTOMER protected.

## Meaning boundary

**Always:** show real Confidence and Coverage; preserve missing evidence; state insufficient information explicitly; explain that the preview is limited; point users toward registration/extension for richer evidence.

**Never:** synthesize a guest risk score; map absent evidence to LOW; reveal protected findings/evidence/actions; accept a caller-supplied guest identity header at the web boundary.

## Verification

- backend authorization test proves another guest key gets 404;
- serialized guest preview contains no overall risk, full risk object, findings, evidence, or detailed actions;
- web proxy refuses requests without the HttpOnly guest cookie and forwards only the trusted opaque key;
- API client uses same-origin cookie credentials and no bearer identity;
- UI renders actual confidence/coverage and an explicit insufficient-information message without a risk score;
- full repository CI remains the merge gate.
