---
title: 'Refactor sweep'
type: 'story'
ticket: '6'
created: '2026-10-08'
status: 'built'
baseline_revision: '8e24f9c2bb165491b5d29b3d004ec957afc3a0be'
route: 'full'
review: 'thorough'
---

## Intent

**Problem:** Stories 4.2 through 4.5 introduced the correct report semantics but accumulated duplicate UI formatting and a guest-preview schema defined outside the canonical reporting contracts.

**Approach:** Consolidate presentation helpers and reporting schema ownership without changing authorization, payload meaning, scoring, freshness thresholds, evidence rules, or status behavior.

## Frontend cleanup

Shared report presentation logic now owns:

- frozen Vietnamese risk-dimension labels;
- source-kind labels;
- percentage and meter formatting;
- buyer-facing risk-label text/tone;
- stable evidence anchors;
- finding display-text extraction.

The full report and guest preview both consume the shared helpers where applicable. Story 4.5's shared freshness classifier remains unchanged at 30 days.

## Backend cleanup

`GuestPreviewPayload` and `GUEST_PREVIEW_SCHEMA_VERSION` now live beside `ReportPayload` and `REPORT_SCHEMA_VERSION` in the canonical reporting contracts module.

The guest preview builder remains a deterministic projection only. Its serialized `guest-preview.v1` fields and authorization route are unchanged.

## Explicit non-changes

This story does not change:

- Risk v0.1.0 weights, thresholds, confidence, or coverage calculations;
- `report.v1` or `guest-preview.v1` serialized field names;
- owner-only full-report authorization;
- guest browser-key authorization or expiry window;
- evidence provenance or dangling-evidence behavior;
- stale-source threshold or warning meaning;
- progress, retry, blocked, failed, or insufficient-information state behavior.

## Verification

- existing full-report and guest-preview render tests continue to pass;
- shared presentation helper tests lock frozen dimension labels, percentage formatting, evidence anchors, and insufficient-information text;
- backend reporting/auth tests continue to validate both report contracts and access boundaries;
- repository CI remains the merge gate.
