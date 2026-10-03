---
title: 'Exercise extraction layouts and re-normalization'
type: 'feature'
ticket: '7'
created: '2026-10-03'
status: 'built'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['blind-hunter', 'edge-case-hunter', 'verification-gap', 'intent-alignment']
review_loop_iteration: 0
baseline_revision: '51810d1cc0e8054d3c359510f310c336e52a7377'
context:
  - 'C:/Users/eidel/Desktop/VCT Connect/_bmad-output/initiative-vct-connect-year-one/epic-extraction/epic-extraction.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The three extraction adapters have saved-page tests, but their combined coverage does not prove the layout, missing-field, high-review-volume, redirect, timeout and parser-change matrix required for the extraction epic. Preserved raw snapshots cannot yet be normalized again without fetching the source.

**Approach:** Extend the representative fixture matrix across 1688, Taobao and Alibaba, and add an internal, owner-scoped re-normalization path that derives a new immutable snapshot from retained raw fields using a newer normalizer version without a network request.

## Boundaries & Constraints

**Always:** Keep the seven status values, 12-field completeness denominator, source identity checks, bounded fetch behavior and review limits. Re-normalization must identify its source snapshot, retain the original capture time and method, use only stored fields, recompute coverage, and leave the original analysis and snapshot unchanged. Reject inaccessible, incompatible or insufficient raw evidence explicitly; preserve customer ownership and quota rules.

**Never:** Re-fetch during re-normalization, persist full HTML or credentials, fabricate fields absent from raw evidence, overwrite an old snapshot, broaden supported URL/layout claims, or add a customer-facing re-normalization control in this story.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
| --- | --- | --- | --- |
| Representative layouts | Saved 1688, Taobao and Alibaba product/shop/profile pages | Correct bound evidence, status, provenance, missing fields and coverage | Changed or unrelated structures fail explicitly |
| Sparse and high-volume pages | Missing supplier/reviews or more than 20 reviews | Unknown stays missing; review evidence is bounded and stable | No completeness inflation or duplicate rows |
| Redirect, access and timeout | Identity-preserving or cross-identity redirect, wall, deadline | Appropriate result or terminal status under existing budget | No bypass or unsafe fetch |
| Raw replay | Owned successful/partial public snapshot with retained selected fields and a revised mapping | New versioned snapshot and analysis point to the source; no crawl | Unsupported raw shapes or ownership mismatch produce no write |

</frozen-after-approval>

## Code Map

- `backend/app/extraction/{offer1688,taobao,alibaba}.py` — parsers and bounded public `raw_payload.public_fields`; reuse the field mappings and identity guards, not HTML replay.
- `backend/app/extraction/contracts.py` — shared 12 evidence fields, seven statuses and coverage semantics.
- New `backend/app/extraction/renormalize.py` — pure, versioned dispatch from retained public fields; report unsupported shapes instead of copying unverified normalized values.
- `backend/app/storage.py::{get_for_user,_complete_processing}` — owner check and immutable snapshot persistence; add a narrowly scoped service operation, reusing admission and completion invariants.
- `backend/tests/{test_extraction,test_taobao,test_alibaba,test_browser_fallback,test_postgres_tracer}.py` — existing saved fixtures, fake clock/transport, browser checks and database helpers. Extend only matrix gaps.

## Tasks & Acceptance

**Execution:**
- [x] `backend/tests/test_extraction.py`, `test_taobao.py`, `test_alibaba.py` — add parameterized sparse/layout, >20-review, redirect, changed-parser and timeout cases; assert exact status, coverage and source binding.
- [x] `backend/app/extraction/renormalize.py` — map retained raw fields into the shared contract for supported public shapes, with a new version and explicit unsupported outcome.
- [x] `backend/app/storage.py` — authorize and admit an owner-scoped replay, write a fresh analysis/snapshot with source provenance and no crawl, and preserve the old row.
- [x] `backend/tests/test_postgres_tracer.py` — prove owner isolation, immutable old evidence, fresh version/coverage, idempotent rejection behavior and zero network use; add a compact three-platform queued status matrix where existing tests do not already cover it.

**Acceptance Criteria:**
- Given each supported saved layout and failure fixture, when extraction runs, then its status, bounded review count, missing fields and completeness match the shared contract.
- Given an owned public raw snapshot with a revised field mapping, when the internal replay runs, then a new versioned snapshot reflects the retained source data without invoking an HTTP/browser adapter.
- Given an unrelated owner or raw data that cannot support the revision, when replay is requested, then it fails without changing or creating evidence.

## Implementation Notes

- Added pure replay mappings for the five audited public layouts and an owner-scoped storage operation. Replay validates raw capture identity/provenance before admission; a successful replay consumes normal customer quota and completes a new analysis in one transaction without queueing or fetching.
- New snapshot versions are `1688-raw.v2`, `taobao-raw.v2` and `alibaba-raw.v2`. Source snapshot/revision and replay time are explicit; capture time, method and retained raw values stay intact. Original snapshots and shared supplier display rows stay intact.
- Review corrections restrict supported source revisions to the matching platform's `http.v1` for HTTP captures and `public-browser.v1` for browser captures. Audited nested selections are checked without changing retained values; unknown revisions, fields and incompatible values fail explicitly.
- Added full-field fixture comparisons, bounded review-volume cases, unsupported raw/render provenance tests, five database replay cases and a 12-case queued failure matrix. Existing sparse, redirect and deadline tests provide the remaining matrix coverage.
- The delegated implementer made partial changes before an account usage limit stopped it; the parent completed the mappings, database guards and tests directly under step 03's unavailable-subagent fallback.
- The same implementer was re-engaged for review corrections and completed the normalizer guards and unit regressions. The parent completed persisted raw/browser assertions and a failure injected after snapshot/review writes. That test observes rollback of quota, analyses, events, results, snapshots and reviews.

## Plan Change Log

## Review Triage Log

Each finding was classified before grouping. Direct corrections below mirror the already audited retained-field schema or add assertions for the existing transaction; they add no public surface or new workflow.

| Finding | Verdict and evidence | Route |
| --- | --- | --- |
| Blind 1: Taobao requires both item identifiers | medium: original `_parse` accepts one matching identifier and rejects conflicts; replay incorrectly requires both. | patch |
| Blind 2: retained Taobao seller conflicts accepted | medium: replay omits `_shop_binding`, accepting incompatible retained seller metadata that the source parser rejects. | patch |
| Blind 3: unsupported source revisions accepted | medium: any nonempty revision passes, including a future or wrong-platform revision. The existing raw compatibility requirement calls for supported source revisions. | patch |
| Blind 4: unknown nested raw fields copied | high: top-level whitelists leave nested fields unchecked; stored arbitrary JSON can retain cookie keys and profile product HTML. Apply the audited nested selections before copying. | patch |
| Blind 5: invalid 1688 scalars become evidence | medium: replay lacks the parser's finite scalar and numeric rating checks; booleans/objects inflate coverage. | patch |
| Blind 6: Alibaba category links unbound | medium: replay ignores retained href host/scheme; restore the original category binding check. | patch |
| Blind 7: shop/profile products deduplicated by full dict | medium: duplicate identities with different titles occupy separate slots, while the original parsers deduplicate by offer id. | patch |
| Blind 8: repeated original replay creates another charged analysis | false: the operation explicitly creates a new analysis for each successful request and applies normal quota. No replay request idempotency contract is specified; the existing guard rejects replay of a replay. | reject |
| Blind 9: late rollback not tested | medium: early raw rejection occurs before quota/write admission and does not protect the replay transaction boundary. | patch |
| Edge 1: invalid 1688 scalar shapes | medium: same demonstrated scalar acceptance as Blind 5. | patch |
| Edge 2: one Taobao item identifier | medium: same valid partial-capture rejection as Blind 1. | patch |
| Edge 3: conflicting Taobao seller metadata | medium: same omitted existing binding guard as Blind 2. | patch |
| Edge 4: profile product unknown nested fields | high: full-dict product copying and raw deep copying preserve unexpected fields, as in Blind 4. | patch |
| Edge 5: source v3 downgraded to v2 | medium: equality-only revision rejection permits unsupported future revisions, as in Blind 3. | patch |
| Verification 1: retained raw not asserted | medium: normalized comparisons and source immutability do not observe new persisted public fields; the review's mutation preserved all helper/layout passes. | patch |
| Verification 2: browser source not replayed through storage | medium: helper-only browser coverage misses storage capture-method preservation. | patch |
| Verification 3: failure after admission not exercised | medium: no late failure assertion protects quota and row rollback, as in Blind 9. | patch |
| Intent: cumulative vs exhaustive matrix readings | false: approved representative matrix permits cumulative coverage and the full backend run executed the unchanged sparse/redirect/deadline checks. All four rows have passing coverage. | reject |
| Intent: no additional saved fixture files | false: five audited saved layouts are exercised and field expectations already have independent parser assertions; intent does not require new captures. | reject |
| Intent: sparse additions vary by platform | false: existing sparse tests across all three platforms ran and passed in the full gate. | reject |
| Intent: review volume tested at parser surface | false: parser assertions establish the extraction bound; persistence coverage retains the bounded review list. Intent does not require every volume case in the queue. | reject |
| Intent: redirects/deadlines rely on existing tests | false: those tests ran and passed, including identity preservation, unsafe redirects and elapsed budgets. | reject |
| Intent: generic changed-layout queue page | false: it verifies terminal settlement; unchanged platform-specific model/DOM mutation tests verify parser changes and ran in the same gate. | reject |
| Intent: simulated old mapping instead of historical bug | false: deleting normalized supplier name while retaining its raw value proves revised output derives from raw evidence. A historical bug is not required. | reject |
| Intent: fixed revision rather than arbitrary evolution | false for generalized revision selection: a concrete newer mapping is the intended operation. Unsupported source revisions are corrected under Blind 3/Edge 5. | reject |

Grouped patches: Taobao binding (Blind 1/2, Edge 2/3); raw revision compatibility (Blind 3, Edge 5); nested audited selections (Blind 4, Edge 4); 1688 scalars (Blind 5, Edge 1); category binding (Blind 6); identity deduplication (Blind 7); retained raw assertions (Verification 1); browser storage replay (Verification 2); late rollback (Blind 9, Verification 3). No intent gap, plan loopback or deferred item remains.

Patch verification: 543 parser/replay tests passed. Targeted PostgreSQL replay checks passed all ten HTTP/browser layouts and unsupported-raw rollback; the new late-failure test initially named the status-event table incorrectly. Corrected it to `analysis_status_events` before the final full backend gate. Final gate results are recorded in Verification below.

## Design Notes

Existing public raw payloads store selected values and an HTML hash, not HTML. Replay can correct normalization of retained values; it cannot recover a selector's missed page content. Keep that limitation explicit in result/provenance and tests. Use a new analysis because snapshots have a unique analysis association and completed analyses reject changed evidence.

Migration `0009_allow_snapshot_replay` removes capture-time uniqueness while retaining unique analysis association. Rollback refuses to restore that constraint when replay rows share a capture time; it never deletes preserved evidence. Current replay deliberately rejects already-replayed snapshots and snapshots already using the requested revision.

## Verification

Matrix audit (executed parser gate: 418 passed; database gate: 81 passed, one Azure skip and two unrelated legacy migration assertions subsequently corrected):

| Approved matrix row | Passing executed covering tests |
| --- | --- |
| Representative layouts | `test_supplied_1688_capture_yields_auditable_supplier_data`, `test_audited_snapshots_have_bound_public_evidence`, `test_audited_evidence_and_selected_raw_values`, and five replay layout comparisons |
| Sparse and high-volume pages | `test_sparse_offer_preserves_missing_fields_without_risk_claim`, `test_missing_fields_remain_unknown_and_reviews_are_scoped`, `test_sparse_bound_evidence_remains_partial`, `test_saved_1688_review_volume_is_bounded_and_coverage_exact`, and Taobao/Alibaba more-than-twenty-review tests |
| Redirect, access and timeout | `test_redirect_loop_and_cross_offer_never_fetch_rejected_target`, `test_retry_budget_does_not_repeat_a_normalized_redirect`, `test_redirects_follow_only_same_audited_identity`, `test_fetch_redirects_preserve_identity_and_never_contact_rejected_target`, `test_fetch_has_an_absolute_deadline`, `test_failed_stream_discarded_and_shared_deadline_limits_retries`, and all 12 `test_three_platform_failure_matrix_settles_without_snapshot` cases |
| Raw replay | All five `test_owned_public_raw_replay_creates_immutable_versioned_evidence_without_fetch` cases; `test_unsupported_raw_replay_rolls_back_without_spending_quota`; `test_incompatible_revision_and_source_provenance_are_rejected`; retained-field and browser-provenance rejection tests |

No skipped test is used to cover a matrix row. Full backend regression before review patches passed: **655 passed, 32 skipped** in 508.27 seconds. The JUnit report confirmed all five persisted replay cases, all 12 queued failure cases, all three 1688 review-volume cases and both Taobao/Alibaba review-volume cases passed. Skips: 31 opt-in actual Chromium checks and one opt-in live Azure check.

Final verification after all review corrections:
- Parser/replay gate: **543 passed** in 4.66 seconds.
- Full backend gate, `.venv/Scripts/python.exe tmp/run-story27-tests.py backend/tests -q --junitxml=tmp/story27-final-backend-junit.xml`: **782 passed, 32 skipped** in 209.78 seconds against a disposable loopback PostgreSQL 16 database. The helper creates and drops a uniquely named test database; no application database is used.
- Final JUnit audit: all ten HTTP/browser stored replay cases, late persistence rollback, 24 unknown nested-field cases, 52 incompatible scalar cases, two sparse item bindings, two product identity deduplication cases and guarded migration rollback passed. The approved matrix remains covered without skipped tests.
- Existing FastAPI test-client deprecation warning only. Opt-in skips remain 31 actual Chromium checks and one live Azure check.
- `git diff --check` and `git diff --cached --check`: clean. Approved frozen intent and original baseline preserved.
- Four review lenses completed; verified findings corrected, no deferred findings or unresolved acceptance gaps.

**Commands:**
- `.venv/Scripts/python.exe -m pytest backend/tests/test_extraction.py backend/tests/test_taobao.py backend/tests/test_alibaba.py backend/tests/test_browser_fallback.py -q` — extraction matrix passes.
- `.venv/Scripts/python.exe -m pytest backend/tests/test_postgres_tracer.py -q` against an isolated temporary PostgreSQL database — replay, ownership and queued cases pass.
- `.venv/Scripts/python.exe -m pytest backend/tests -q` — backend regression suite passes, recording opt-in skips separately.
- `git diff --check` — no whitespace errors.
