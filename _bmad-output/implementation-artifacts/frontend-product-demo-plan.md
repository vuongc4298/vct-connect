---
title: 'Create a frontend-only VCT Connect product demo'
type: 'prototype'
created: '2026-09-28'
status: 'built'
route: 'quick'
baseline_revision: 'NO_VCS'
review: 'quick'
review_source: 'auto'
lenses_ran: ['quick']
---

<frozen-after-approval reason="user-requested demo scope">

## Intent

Turn the authenticated developer tracer into a polished, presentation-ready preview of the intended supplier-risk workflow before Story 1.4 begins.

## Boundaries & Constraints

**Always:** Keep the existing Clerk sign-in and real fixture submit/poll path working; use the current frontend contracts; make fixture and illustrative assessment content unmistakably demo-only; present the core report concepts from the product plan; work on the frontend only.

**Never:** Change the API, worker, database, Azure flow, or Story 1.4 behavior; imply that illustrative risk scores are extracted supplier evidence; add history, Watchlist, billing, entitlements, or report APIs.

</frozen-after-approval>

## Tasks & Acceptance

- [x] Replace the tracer layout with a responsive product shell and signed-out product preview.
- [x] Keep signed-in submission and polling functional through the existing authenticated API client.
- [x] Present a clearly labeled illustrative report after the fixture reaches COMPLETED.
- [x] Verify frontend tests, typecheck, and production build.

## Implementation Notes

- Replaced the developer tracer with a responsive Vietnamese product shell for signed-out and signed-in states.
- Preserved Clerk authentication and the existing authenticated fixture submission and polling flow.
- Added a presentation-ready illustrative supplier report that appears only after the live fixture reaches `COMPLETED`.
- Labeled illustrative scores, signals, and report content as demo data throughout the experience.
- Kept the implementation frontend-only; no API, worker, database, Azure, or Story 1.4 behavior changed.

## Verification

- Frontend typecheck: passed.
- Frontend unit test: passed.
- Frontend production build: passed.
- Built frontend secret scan: passed.

## Review Triage Log

- Removed future History and Watchlist navigation plus the fabricated Pilot quota so the shell stays within the agreed frontend demo scope.
- Replaced multi-platform claims with an accurate single 1688 fixture description.
- Made the fixture URL read-only and labeled the exact demo constraint beside the control.
- Cleared the active analysis after terminal polling errors so the UI cannot remain in a false processing state.
- Changed the document language from English to Vietnamese for the Vietnamese interface.

## Runtime and Typography Follow-up — 2026-09-28

- Restored the stopped PostgreSQL container, API process, and Azure Service Bus worker after the demo returned HTTP 500.
- Replaced the serif display typography with a Vietnamese-safe `Segoe UI`, Arial, and `Noto Sans` stack across the interface.
- Confirmed the frontend returns HTTP 200 and its API rewrite reaches the backend; an unauthenticated submission now returns the expected HTTP 401.
- Re-ran frontend type checking and the authenticated API client test successfully.
