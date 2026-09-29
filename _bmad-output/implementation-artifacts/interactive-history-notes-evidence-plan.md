---
title: 'Add interactive history, supplier notes, and richer evidence to the demo'
type: 'feature'
created: '2026-09-28'
status: 'built'
route: 'quick'
baseline_revision: 'NO_VCS'
review: 'quick'
review_source: 'auto'
lenses_ran: ['quick']
---

<frozen-after-approval reason="user-requested interactive demo features">

## Intent

Extend the frontend demo with useful, interactive product concepts before Story 1.4 without inventing backend persistence contracts.

## Boundaries & Constraints

**Always:** Keep the existing Clerk and live fixture flow working; scope history to the signed-in user; save notes and demo history in browser storage; label seeded evidence as illustrative; support keyboard and responsive use.

**Never:** Add database tables or API endpoints, present demo evidence as live supplier evidence, expose credentials, or change Azure processing behavior.

</frozen-after-approval>

## Tasks & Acceptance

- [x] Add an interactive analysis history with useful filtering and detail selection.
- [x] Persist editable supplier notes for each history entry in user-scoped browser storage.
- [x] Add filterable, expandable risk evidence with source, freshness, confidence, and follow-up guidance.
- [x] Add each completed live fixture run to history without duplicate entries.
- [x] Verify frontend tests, typecheck, production build, and credential scan.

## Implementation Notes

- Added three clearly labeled seeded history entries so the feature is demonstrable immediately.
- Scoped browser storage by Clerk user ID and automatically adds each completed live fixture once.
- Added history search, entry selection, risk summaries, and responsive desktop, tablet, and mobile navigation.
- Added a per-entry notes editor with local autosave and a visible 600-character limit.
- Added reusable evidence profiles with risk, watch, and positive filters plus expandable source, freshness, confidence, rationale, and follow-up details.

## Verification

- Frontend typecheck: passed.
- Frontend API client test: passed.
- Frontend production build: passed.
- Built frontend secret scan: passed.

## Review Triage Log

- Constrained history detail selection to the filtered result set.
- Marked every fixture-derived history entry and detail view as illustrative.
- Repeated evidence confidence inside expanded details so it remains available on tablet and mobile.
- Added explicit accessible labels to collapsed tablet navigation buttons.
- Guarded browser-storage reads and writes and surfaced a visible in-session-only warning when persistence is unavailable.
- Scoped persistence to the currently loaded Clerk user to prevent cross-account writes during account switching.
