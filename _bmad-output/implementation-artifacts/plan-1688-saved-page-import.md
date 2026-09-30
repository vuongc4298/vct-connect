---
title: 'Import a saved 1688 offer page as supplier evidence'
type: 'feature'
ticket: ''
created: '2026-09-30'
status: 'built'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['blind-hunter', 'edge-case-hunter', 'verification-gap', 'intent-alignment']
review_loop_iteration: 0
baseline_revision: '9f0b8c95fa0690c429fdc4cf0ee9e9a4d2665376'
context:
  - '_bmad-output/initiative-vct-connect-year-one/epic-extraction/epic-extraction.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 1688 returns an access challenge to the server even when a buyer can view the offer in a browser. The buyer needs a way to import evidence from a page they have legitimately opened so the app can produce a traceable SupplierData snapshot.

**Approach:** Let a signed-in buyer select a locally saved 1688 HTML page and its offer URL in the web app. Parse the page in memory with the existing 1688 parser, label its method `USER_UPLOAD`, and atomically store the resulting analysis, selected evidence, reviews, and provenance behind owner-scoped polling. Keep the public URL path available.

## Boundaries & Constraints

**Always:** Require Clerk CUSTOMER identity and the existing customer admission quota. Bind the page's canonical or embedded offer ID to the supplied HTTPS offer URL; cap the request and HTML size; reject unsupported encodings/content types. Preserve explicit missing fields and coverage, distinguish upload provenance from public HTTP, and return blocked or parse-failed outcomes without inventing a snapshot. Do not persist or log the complete uploaded HTML. Keep status polling owner-scoped and analysis/snapshot writes atomic.

**Never:** Send 1688 credentials, cookies, or session tokens as an intentional capture field; bypass a source challenge; label an upload as a live server fetch; change guest fixture behavior, scoring, or the current demo history. Browser extension and official API integration are separate follow-on work.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
| --- | --- | --- | --- |
| Representative saved page | Supplied 1688 capture and matching offer URL | Owner can poll a `PARTIAL`/`SUCCESS` SupplierData snapshot with `USER_UPLOAD`, source, timestamp, coverage and accessible reviews | No full HTML retained |
| Challenge or sparse saved page | Valid bounded HTML with challenge or absent evidence | Explicit `BLOCKED` or `PARTIAL` with no fabricated fields | Missing fields stay unknown |
| Wrong offer or oversized/invalid file | Page ID mismatch, unsupported content or more than 2 MB | Reject before analysis or return explicit parse failure as appropriate | No snapshot, no queued fetch |
| Other user | Valid analysis ID belonging to buyer | Owner sees result; another user cannot | Return 404 for non-owner |

</frozen-after-approval>

## Code Map

- `backend/app/extraction/offer1688.py::parse_1688_page` already validates offer binding and builds selected raw evidence; parameterize provenance without changing public HTTP defaults.
- `backend/app/main.py::current_principal/submit/status` provides Clerk CUSTOMER auth and owner scope; add a bounded import endpoint, leaving guest routes untouched.
- `backend/app/storage.py::_insert_analysis/_admit/complete_processing/_SELECT` owns quota, state events, atomic snapshot writes, and owner polling; share persistence logic for direct import without a queue race.
- `frontend/apps/web/app/page.tsx` contains signed-in URL form and polling; `frontend/packages/api-client/src/index.ts` supplies bearer-token requests; `frontend/apps/web/app/api/_backend.ts` proxies requests; `ExtractionEvidence` already renders SupplierData.
- `backend/tests/test_extraction.py`, `test_postgres_tracer.py`, `test_auth.py`; frontend API client/status/proxy tests cover the new input route and existing regression paths.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/extraction/offer1688.py` — allow an explicit `USER_UPLOAD` method/version for in-memory parsing; retain strict offer binding and public HTTP defaults.
- [x] `backend/app/storage.py` — add atomic, quota-limited signed-in import using the existing result/snapshot persistence path, with owner-scoped polling and no queue publication.
- [x] `backend/app/main.py` — add a 2 MB bounded authenticated HTML import endpoint with clear validation and no raw HTML retention or logging.
- [x] `frontend/packages/api-client/src/index.ts`, `frontend/apps/web/app/api/`, `frontend/apps/web/app/page.tsx` — accept a saved HTML file beside the URL, upload through the authenticated proxy, then display the imported result with its source method.
- [x] `backend/tests/`, `frontend/**.test.ts*` — verify matching/blocked/mismatched/oversized pages, quota, ownership, atomic persistence, frontend request/status, and the fixture/public URL regression.

**Acceptance Criteria:**
- Given the supplied saved page and matching URL, when the signed-in buyer imports it, then polling returns an owner-scoped SupplierData snapshot with `USER_UPLOAD`, explicit coverage and no full HTML stored.
- Given a challenge, wrong offer, invalid or oversized input, when imported, then the app gives an explicit safe outcome and stores no fabricated supplier snapshot.
- Given a buyer at their quota or a different user's analysis ID, when submitting or polling, then existing admission and owner rules apply.

## Implementation Notes

- The signed-in import sends a UTF-8 HTML file through a 2 MB bounded Next.js proxy to FastAPI. Parsing runs in a threadpool and persistence uses one PostgreSQL transaction. A successful import returns an analysis ID for the existing owner-scoped polling route; no queue message or complete HTML page is stored.
- Uploaded evidence carries `USER_UPLOAD`, `1688-user-upload.v1`, a SHA-256 of the original file bytes, an import timestamp, and an explicitly unknown original capture time. An upload cannot overwrite a supplier's existing shared name or source URL.
- The buyer form keeps URL-only extraction available. Upload labels and evidence wording identify a saved page, and file selection clears after a successful import or when the buyer starts a new analysis.

## Plan Change Log

## Review Triage Log

| Finding | Verdict and evidence | Route |
| --- | --- | --- |
| B1 import proxy route without query bypassed the size cap | medium: the original predicate only matched `import?`, so a POST to `import` read its full body before the backend rejected it. The predicate now also matches the bare route. | patch |
| B2 quota checked after bounded parsing | low: an exhausted signed-in customer can submit up to 2 MB of HTML for parsing before admission fails. This is unlikely in ordinary use and an early quota check adds a second admission path or a race; retain atomic admission. | reject |
| B3 synchronous work in async import route | medium: parsing and PostgreSQL calls held the event loop. Both now run in the threadpool. | patch |
| B4 uploaded supplier ID overwrote shared supplier metadata | high: the shared supplier upsert changed name and URL from untrusted upload evidence. Uploads now reuse an existing supplier ID without updating those fields. | patch |
| B5 saved file survived identity change | medium: a selected file could remain ready to submit under a different signed-in user. The form now clears file state and native input on user change. | patch |
| B6 saved file survived completed import or new analysis | medium: the form could silently reuse a prior page and mismatched URL. It now clears the file after successful import and on new analysis. | patch |
| B7 BOM affected upload hash | medium: hashing decoded HTML lost the original UTF-8 BOM. The parser now receives and hashes original uploaded bytes. | patch |
| B8 upload time mislabeled as source capture time | medium: the source capture time is unknown for a saved file. Raw evidence now has null `captured_at` and a separate `imported_at`; the UI explains this. | patch |
| B9 quoted or spaced charset escaped validation | medium: simple string matching missed `charset = "gbk"`. MIME parsing now rejects non-UTF-8 declarations and HTML meta charset is checked. | patch |
| B10 upload used fixture report labels and public-page wording | medium: `USER_UPLOAD` was absent from the extraction branch and the evidence copy claimed a public page. Both now identify uploaded evidence. | patch |
| E1 deeply nested page caused parser recursion error | medium: bounded HTML can still contain pathological nested JSON. The endpoint now yields a pollable `PARSE_FAILED` result with no snapshot. | patch |
| E2 shared supplier metadata overwrite | high: same root cause as B4, independently confirmed by a PostgreSQL regression assertion. | patch |
| V1 form upload-to-poll path lacked a test | medium: the request helper now has a focused test showing selected file bytes use the import route and the returned ID is polled. The page calls that helper. | patch |
| V2 rendered upload provenance lacked a test | medium: the evidence component now has a `USER_UPLOAD` rendering assertion for source method, version and unknown capture time. | patch |
| I1 live rendered browser capture is outside this saved-file change | false for this build: the frozen intent specifically selects a locally saved HTML page and lists the browser extension as separate follow-on work. | reject |
| I2 buyer workflow needed an integrated check | medium: the page's selected-file branch is factored through a tested submit helper; backend route, owner polling, persistence, and rendering also have separate focused tests. | patch |

## Verification

**Commands:**
- `.venv/Scripts/python.exe -m pytest backend/tests -q` with PostgreSQL test URL — backend extraction/auth/persistence regression passes.
- `npm test --prefix frontend` and `npm run typecheck --prefix frontend` — web request and rendering checks pass.
- Parse the supplied local capture against its matching URL — imported result has selected fields and expected missing-field coverage.

**Observed:** PostgreSQL-backed backend suite: 133 passed, 1 skipped; frontend suite: 21 passed; TypeScript typecheck and production build passed. The supplied 851,376-byte saved page parsed against its offer URL as `PARTIAL` with 50% coverage and explicit missing fields. `git diff --check` found no whitespace errors.
