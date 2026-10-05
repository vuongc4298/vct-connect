---
title: 'Story 3.1 grounded source interpretation guidance'
type: 'bugfix'
ticket: ''
created: '2026-10-05'
status: 'built'
route: 'oneshot'
route_source: 'auto'
review: 'quick'
review_source: 'auto'
lenses_ran: ['quick']
baseline_revision: '512f7c62b8539000ad6e3b4e539a64165fdb1820'
context: []
---
<frozen-after-approval reason="human-owned intent">
## Intent
Correct the source-grounding instructions supported by the saved READY report: distinguish dispatch from delivery, preserve each starting price and unknown fees, keep product versus shop metrics separate and retain product/title facts and distinct review opinions. Review and test offline, commit locally and deploy to existing dev resources. Preserve immutable READY report95fdb0a2-5c69-475a-87a8-77ac29bbedc5 and all prior dispatches/reservations. Keep language/citation/score/credential guards, uncalibrated model self-report confidence, model/deadline/token settings and secret boundaries. No paid generation, rejected-response capture, report rewrite, Git push or claim of Story3.1 live acceptance in this slice.
</frozen-after-approval>
## Implementation Notes
Under100 code/test lines; oneshot. Prompt vi-text.v7 adds general semantic guidance without fixture-specific numeric values: 发货 is dispatch, 起 qualifies every starting price, absent fees remain unknown, title specifications remain claims and review attributes remain distinct. Known Taobao item parser provenance establishes positive_review_rate_display_text from item rateVO and shop_metrics_display_text from seller-bound DOM. Add field-specific scope mapping to the minimized transaction evidence only for a nonempty item ID, platform TAOBAO and audited extractor versions taobao-http.v1, taobao-upload.v1, public-browser.v1, taobao-raw.v2; preserve source values, E IDs and omission behavior. Do not label the entire mixed metric entry as product. Other provenance is unannotated. Validation vi-prose.v3 and schema text-report.v2 stay unchanged.
Implementation adds general source-term guidance and field-specific constant scope mapping after minimization. New fixture projection/hand-authored settlement case and eight provenance/absence cases pass, bringing focused suite to245. PostgreSQL authentic-owner-reopen test asserts persisted scope. No validation guard change; no model inference occurred.
## Plan Change Log
## Review Triage Log
One medium test-input finding, patch: uploaded_bytes requires bytes, not their length. Both authentic-fixture tests now supply original UTF8 bytes and assert taobao-upload.v1, USER_PROVIDED_SAVED_PAGE and unknown captured_at. Parser mutates supplier provenance before catching the TypeError from hashing an integer; the tests previously missed raw upload-provenance completion. Production parser/upload flow unchanged. All other review checks reported no findings. Rerun tests and rebuild the actual tested image before deployment.
## Verification
Given authentic saved Taobao item evidence, when minimized and dispatched through a fake provider, then original source text/prices/reviews and deterministic product/shop scope reach the provider without raw HTML, identities or URLs, and a hand-authored grounded Vietnamese response settles READY with v7 metadata and uncalibrated labels. Given unsupported provenance or missing item identity/metric fields, when projected, then no unsupported scope/metric is invented. Given original report guards, when the full focused suite runs, then all cases pass. Fake outputs check projection/settlement only, not model translation quality. Run meaningful PostgreSQL owner/reopen regression for the projection addition, actual non-root image tests without networking and independent quick review. Deploy tested image by digest; verify health, unchanged effective settings and read-only ledger. Paid acceptance requires separate approval.

Verification after review patch:245 focused tests pass locally and in the final rebuilt non-root offline image;13 isolated PostgreSQL tests pass with correct original upload bytes and explicit upload provenance. This plan is built for implementation, not accepted Story3.1. Dev release remains the authorized next operation.
