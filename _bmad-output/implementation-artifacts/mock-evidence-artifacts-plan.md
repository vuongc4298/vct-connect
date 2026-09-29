---
title: 'Add claim-linked mock evidence artifacts'
type: 'feature'
created: '2026-09-28'
status: 'built'
route: 'quick'
baseline_revision: 'NO_VCS'
review: 'quick'
review_source: 'auto'
lenses_ran: ['quick']
---

<frozen-after-approval reason="user-requested richer mock evidence">

## Intent

Make risk claims in the interactive demo feel inspectable by linking them to concrete, clearly illustrative source artifacts.

## Boundaries & Constraints

**Always:** Label every artifact as mock evidence; link artifacts to a specific claim with stable reference IDs; show Chinese excerpts with Vietnamese translations; keep the interaction frontend-only and responsive.

**Never:** Present invented comments, trends, identities, or payment details as real supplier data; add scraping or evidence APIs; change the live fixture pipeline.

</frozen-after-approval>

## Tasks & Acceptance

- [x] Add reusable quote, trend, and structured-record evidence artifacts.
- [x] Reference artifacts from relevant analysis claims and expose them in expanded details.
- [x] Include Chinese comment excerpts, Vietnamese translations, and a visible 5-star review surge.
- [x] Verify frontend tests, typecheck, production build, and credential scan.

## Implementation Notes

- Added typed mock artifact models for translated quote samples, time-series trends, and structured records.
- Linked claims to stable evidence references displayed in both collapsed summaries and expanded evidence details.
- Added Chinese review excerpts with Vietnamese translations and timestamps/account labels that are visibly synthetic.
- Added responsive five-period charts for review surges and transaction shifts, including text annotations and accessible chart descriptions.
- Added mock company-profile and beneficiary comparisons with flagged missing or mismatched fields.

## Verification

- Frontend typecheck: passed.
- Frontend API client test: passed.
- Frontend production build: passed.
- Built frontend secret scan: passed.

## Review Triage Log

- Corrected the `RV-12` annotation to match the displayed increase from 9 to 58 reviews: 6.4× from week 3 to week 5.
- Added `CP-03` factory-video metadata to the stale-capacity claim.
- Added `ID-09` store-age comparison data to the young-store claim.
