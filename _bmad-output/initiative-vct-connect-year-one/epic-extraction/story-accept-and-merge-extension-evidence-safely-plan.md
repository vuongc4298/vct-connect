---
title: 'Accept and merge extension evidence safely'
type: 'feature'
ticket: '6'
created: '2026-10-02'
status: 'built'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: []
review_loop_iteration: 0
baseline_revision: '1d31eace75452d5a5022d64fcabb1785ea228648'
context:
  - '_bmad-output/initiative-vct-connect-year-one/epic-extraction/epic-extraction.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Extension captures currently create isolated snapshots, so permitted rendered evidence cannot enrich the server evidence already held for the same buyer and page. Repeated capture may repeat evidence.

**Approach:** Keep the narrow, selected page-state payload; merge it with the latest owner-scoped, same-source snapshot in a separate module before persisting a new immutable extension snapshot. Preserve source references, recompute coverage, and deduplicate reviews and products.

## Boundaries & Constraints

**Always:** Match canonical source and customer ownership. Accept only schema-declared visible fields; reject secret-like text and extra page state. Keep extension and prior evidence separately attributable. Preserve raw source snapshots and quota, authorization, replay, and missing-field semantics. An extension capture without prior evidence remains valid.

**Never:** Transmit source cookies, passwords, session tokens, scripts, page globals, or full HTML; edit platform adapters or prior snapshots; merge unrelated, guest, or another owner's evidence; treat missing evidence as safe; begin production media collection before terms review.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
| --- | --- | --- | --- |
| Same-owner same-page prior snapshot | Public or historical snapshot plus selected extension fields | New combined snapshot, source reference, recalculated coverage | Original snapshot remains immutable |
| Repeated evidence | Overlapping review/product fields | One stable copy per identity | No duplicate rows or items |
| No eligible prior snapshot | Selected capture only | Extension snapshot as before | No unrelated merge |
| Unsafe page state | Extra fields or secret-like selected text | Reject capture | No stored payload or quota use |

</frozen-after-approval>

## Code Map

- `backend/app/extraction/extension1688.py`, `extensiontaobao.py` — strict selected capture models and normalizers; preserve platform-specific selectors and URL binding.
- `backend/app/extraction/contracts.py` — SupplierData 12-field denominator and provenance fields.
- `backend/app/storage.py: capture_customer_page` — quota transaction and immutable snapshot persistence; find eligible owner/source baseline here, call separate merge module.
- `backend/app/main.py: capture_browser_evidence` — 16 KB JSON ingress; preserve role checks and add secret rejection before persistence.
- `frontend/apps/extension/src/capture.ts`, `popup.tsx` — invoked activeTab selection and JSON submission; avoid expanding source access.
- `backend/tests/test_postgres_tracer.py`, `test_extraction.py` — fixture-based merge, ownership, deduplication, and secret rejection checks.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/extraction/extension_merge.py` — deterministic SupplierData merge with field provenance, stable product/review deduplication, and coverage recomputation.
- [x] `backend/app/storage.py` — select latest eligible same-owner/same-source snapshot inside capture transaction and persist merged result with baseline reference.
- [x] `backend/app/main.py` and `backend/app/storage.py` — reject non-permitted or secret-like page-state content before persistence, using the existing strict capture normalizers.
- [x] `backend/tests/` — verify enrichment, no duplicate evidence, owner/source isolation, immutable source snapshot, and rejected secrets.

**Acceptance Criteria:**
- Given a completed owner-scoped public snapshot for a source, when that owner captures the same page, then the new extension snapshot contains both available sources without duplicate evidence and identifies their provenance.
- Given no eligible matching snapshot, when a customer captures selected page evidence, then the existing extension-only behavior persists.
- Given source credentials, session state, or extra payload keys, when submitted, then the request fails before storing them.

## Implementation Notes

- The existing extension capture schemas remain the permitted page-state contract. Both 1688 and Taobao paths use the same merge module; Alibaba extension capture remains unsupported.
- The newest completed snapshot for the authenticated customer and exact canonical source is used as the baseline. The new snapshot holds selected browser fields, a baseline snapshot ID, field source labels, and the baseline extraction time/method; previous snapshots stay immutable.
- No media collection was added. Production collection still requires the source-platform terms review named in the epic.
- Independent review agents could not run because the account hit its usage limit. A local staged-diff audit found and fixed inaccurate provenance for overwritten scalar fields and missing baseline freshness metadata.

## Plan Change Log

## Review Triage Log

| Finding | Verdict | Resolution |
| --- | --- | --- |
| Overwritten scalar fields were attributed to both snapshots | medium | Patched field_sources to name only the contributing extension field. |
| Historical field freshness was not surfaced | medium | Added baseline extraction time and method to raw provenance and the web evidence view. |
| Taobao's selected review shape was not exercised by merge tests | medium | Added a Taobao duplicate-review test. |

## Verification

**Commands:**
- `.venv/Scripts/python.exe -m pytest backend/tests/test_extension_merge.py backend/tests/test_postgres_tracer.py -q` with a temporary local PostgreSQL database — 50 passed, 1 opt-in skipped; the final added Taobao unit test passed separately (7 passed).
- `npm test --prefix frontend` and `npm run typecheck --prefix frontend` — 72 tests passed and typecheck passed.
- `git diff --check` — clean diff.
