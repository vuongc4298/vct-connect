---
title: 'Extract a 1688 URL into the shared SupplierData contract'
type: 'feature'
ticket: '1'
created: '2026-09-29'
status: 'built'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['blind-hunter', 'edge-case-hunter', 'verification-gap', 'intent-alignment']
review_loop_iteration: 0
baseline_revision: 'a0265a114bccee50c7d870712caf59cc9393bd7b'
context:
  - '_bmad-output/initiative-vct-connect-year-one/epic-extraction/epic-extraction.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The queued analysis path accepts only a fabricated 1688 fixture URL and returns a fixture result. It cannot capture a live, auditable supplier snapshot.

**Approach:** Define the cross-platform SupplierData shape, extract accessible public 1688 offer data with httpx/selectolax, and atomically persist raw evidence, normalized fields, reviews, and provenance behind the existing submission and polling path. Use the supplied offer `996518024136` page capture for parser acceptance; report the server's anti-bot challenge as blocked, without claiming a live snapshot.

## Boundaries & Constraints

**Always:** Preserve guest/customer authorization, quota, queue/replay semantics, and a working fixture path for existing demo smoke checks. Validate HTTPS 1688 offer URLs and every redirect before fetching; stop at login/CAPTCHA/block. Require platform, source URL, and extraction timestamp; make every evidence field optional, enumerate each absence in `missing_fields`, and document the completeness denominator. Keep missing evidence distinct from a safe-risk signal. Scope public HTTP to the first 1688 adapter.

**Never:** Collect platform credentials/cookies, bypass access controls, scrape unrelated hosts, present fixture claims as live evidence, or implement Playwright, Taobao, Alibaba, scoring, or extension merge in this story.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
| --- | --- | --- | --- |
| Public offer | Verified representative 1688 URL with accessible data | Pollable analysis links a SupplierData snapshot and accessible reviews; result names source, method, mode, version, completeness, missing fields, timestamp | Missing fields stay explicit |
| Sparse offer | Accessible page omits fields or reviews | Preserve available evidence; mark absent fields and partial coverage | Never convert absence to zero risk |
| Unsafe URL or redirect | Invalid scheme, host, path, private destination, or off-platform redirect | Reject submission or stop extraction before unsafe fetch | No request to an unapproved destination |
| Login, block, or parser failure | Page cannot yield public supplier evidence | Expose an explicit extraction outcome, without a fabricated snapshot | No credential bypass; detailed retry classification belongs to Story 2.2 |
| Replay | Duplicate queue delivery after commit | Keep first immutable result and linked snapshot | No orphan or duplicate rows |

</frozen-after-approval>

## Code Map

- `backend/app/fixture.py`, `backend/app/main.py` — current exact-URL validator and API submission; retain fixture smoke and add strict public 1688 offer validation.
- `backend/worker/main.py` — local/Azure processing both default to `fixture_result`; dispatch live adapter without changing claim/settlement behavior.
- `backend/app/storage.py` — `claim_processing` returns URL only; `complete_processing` stores JSON result but no supplier/snapshot; add mode and transactional persistence/linkage. `_SELECT` drives authorized polling.
- `backend/db/migrations/0003_align_core_schema_to_spec.py` — canonical supplier/snapshot columns already exist; add a new migration for accessible reviews and any extraction metadata absent from those tables, never edit old migrations.
- `backend/requirements.txt`, `backend/Dockerfile` — httpx present, selectolax absent; image installs requirements.
- `frontend/packages/contracts/`, `frontend/apps/web/app/page.tsx` — demo fixes URL and labels report as fixture; allow live URL entry and distinguish live extraction metadata from mock report evidence.
- `backend/tests/test_tracer.py`, `backend/tests/test_postgres_tracer.py` — queue/replay and PostgreSQL integration checks; retain fixture assertions and add live adapter fixtures. PostgreSQL cleanup must delete new linked rows.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/extraction/` and `backend/requirements.txt` — add versioned SupplierData/status contract, strict URL normalization, bounded public HTTP fetch, 1688 parser, and representative saved-page tests.
- [x] `backend/db/migrations/0007_*.py` and `backend/app/storage.py` — persist supplier, raw/normalized snapshot, provenance, reviews, and analysis link in one lease-checked transaction; expose them through owner-scoped polling.
- [x] `backend/app/main.py`, `backend/worker/main.py` — submit supported 1688 URLs and run live extraction for them while retaining explicit fixture mode for existing smoke tests.
- [x] `frontend/packages/contracts/` and `frontend/apps/web/app/page.tsx` — make signed-in URL entry interactive and show extraction coverage/status distinctly from the mock risk report.
- [x] `backend/tests/` and relevant frontend tests — cover representative/sparse/blocked/unsafe pages and transactional replay.

**Acceptance Criteria:**
- Given the supplied representative page capture, when parsed, then it yields a versioned SupplierData snapshot with source, method, mode, completeness, missing fields, timestamp, and available reviews; a live accessible offer follows the same queued persistence path.
- Given missing page data, when extraction completes, then the unavailable fields and coverage are explicit and no risk claim is inferred.
- Given an unsafe URL, redirect, or blocked page, when extraction runs, then no unsafe request or fabricated success occurs.
- Given duplicate delivery, when the result already committed, then the same result and one snapshot remain.

## Implementation Notes

- The supplied local HTML was parsed directly during verification. The committed parser fixture contains only public fields needed for repeatable tests; the original browser capture and asset directory stay local and untracked.
- Live extraction of the supplied URL returned a 1688 HTTP 200 JavaScript access challenge. The adapter reports `BLOCKED / ACCESS_CHALLENGE` and writes no supplier snapshot. An accessible public page is covered by a mock HTTP response and PostgreSQL queue/polling integration tests; Azure live extraction remains unverified.
- Raw evidence stores selected source fields, review text when available, and a SHA-256 of the fetched HTML. Full page HTML is not stored. The existing demo risk report and mock history remain separate from live extraction evidence.

## Plan Change Log

## Review Triage Log

| Finding | Verdict | Route | Evidence and resolution |
| --- | --- | --- | --- |
| Blind B1: DNS can change between validation and connection | high | patched | The prior check was vulnerable; `PublicOnlyBackend` connects to a validated literal public IP while retaining hostname TLS verification. Private DNS and rebinding tests pass. |
| Blind B2: slow chunks can evade a per-read timeout | medium | patched | Streaming now has a 25-second absolute deadline, tested with a controlled clock. |
| Blind B3: selected raw fields cannot reproduce every later parser rule | low | rejected | The snapshot keeps the source values used by v1 normalization, individual review text when present, and the HTML hash. Full-page archival is not required by the captured intent and would add retention of unrelated page content. |
| Blind B4: unverified page can be attributed to requested offer | high | patched | Parser now requires a matching canonical URL or embedded offer ID; a mismatched or unverified page fails. |
| Blind B5: malformed first model hides a later valid model | medium | patched | Model scan continues after malformed JSON; regression test covers a later valid model. |
| Blind B6: replay ignores changes to saved evidence | medium | patched | Replay compares normalized data, raw payload, and ordered reviews with the committed snapshot. |
| Blind B7: supplier upsert leaves name/source stale | low | patched | Upsert refreshes available name and current source URL. |
| Blind B8: live extraction is absent from demo history | low | rejected | The existing history is a mock scored risk report; the intent calls for owner-scoped polling of extraction evidence, which is implemented. Inserting an unscored live extraction into that report would misrepresent its meaning. |
| Blind B9: UI shows review count without accessible text | medium | patched | Live evidence now renders fetched review text; frontend render test checks it. |
| Blind B10: blocked completion is shown as a ready report | high | patched | Status presentation distinguishes blocked extraction and says no snapshot or risk score exists. |
| Blind B11: reduced parser fixture and no successful HTTP integration | medium | patched | The supplied full capture was parsed directly; sanitized fixture is committed for CI, and a mock accessible HTTP response plus PostgreSQL queue/polling tests cover the path without retaining the private browser capture. |
| Edge E1: DNS rebinding | high | patched | Same verified defect and literal-IP connection as B1. |
| Edge E2: page not bound to offer | high | patched | Same verified defect and offer identity checks as B4. |
| Edge E3: malformed initial embedded model | medium | patched | Same verified defect and model scan test as B5. |
| Edge E4: nonstring title/name reaches frontend | medium | patched | Parser accepts only strings for those fields; malformed embedded values are tested. |
| Edge E5: endless slow response chunks | medium | patched | Same verified defect and absolute deadline as B2. |
| Edge E6: successful payload without supplier evidence completes | high | patched | Transaction rejects a success/partial result without matching supplier data, raw evidence, and reviews; PostgreSQL test checks no completion. |
| Edge E7: blocked result presented as report ready | high | patched | Same verified defect and presentation test as B10. |
| Edge E8: representative capture not fully committed | low | rejected | The complete local capture was manually parsed, while the committed test fixture deliberately contains only relevant public evidence. |
| Verification V1: accessible fetch was not exercised | medium | patched | Mock HTTP response now reaches parser, and PostgreSQL integration tests exercise queue, persistence, and owner-scoped poll. |
| Verification V2: live evidence rendering was not asserted | medium | patched | Server-render test asserts status, coverage, and accessible review text. |
| Intent I1: Azure live snapshot not demonstrated | medium | deferred | The supplied URL serves an anti-bot challenge and Step 5 forbids auto-push. A deployed smoke check needs an accessible public URL after this commit is pushed. |
| Intent I2: reduced fixture versus supplied full capture | low | rejected | Full local capture was parsed directly; a sanitized public-field fixture exercises its parser shape in CI without committing browser state. |
| Intent I3: raw evidence narrower than complete HTML | low | rejected | The v1 audit trail includes used source values and a full-page hash; complete HTML retention is outside the stated contract. |
| Intent I4: frontend contract only permits 1688/required offer ID | medium | patched | Platform is a cross-platform union and `offer_id` is nullable in the TypeScript contract. |

## Verification

**Commands:**
- `.venv/Scripts/python.exe -m pytest backend/tests -q` — extraction and regression checks pass with PostgreSQL where configured.
- `npm test --prefix frontend` and `npm run typecheck --prefix frontend` — web contract and UI checks pass.
- GitHub CI and Azure dev smoke using an agreed real URL — queued live snapshot can be polled and audited after deployment.

**Observed:** PostgreSQL-backed backend suite: 127 passed, 1 skipped. Frontend: 17 passed; typecheck passed. `git diff --check` passed. The supplied live URL produced `BLOCKED / ACCESS_CHALLENGE` without a snapshot, as required for an inaccessible page. GitHub CI and Azure smoke are pending a push and an accessible public URL.
