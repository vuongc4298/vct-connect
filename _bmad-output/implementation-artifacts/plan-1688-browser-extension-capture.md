---
title: 'Capture selected 1688 page evidence from a signed-in Chrome extension'
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
baseline_revision: '23a527fc60eaae8d6eab0568ec8a917caf89d2cd'
context:
  - '_bmad-output/initiative-vct-connect-year-one/epic-product-workflows/epic-product-workflows.md'
  - '_bmad-output/initiative-vct-connect-year-one/epic-extraction/epic-extraction.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A signed-in buyer can view a 1688 offer after completing the platform's browser challenge, but VCT Connect's server fetch is blocked. Saving an HTML file works, yet adds several manual steps and can miss rendered content.

**Approach:** Add a user-invoked Chrome extension that reads a small allowlist of visible offer evidence from the active 1688 tab, sends it to an authenticated VCT Connect capture endpoint, shows the resulting evidence status and coverage, and opens the owner-scoped web result. Keep the saved-page and public URL paths available.

## Boundaries & Constraints

**Always:** Require a valid Clerk CUSTOMER session and the customer quota; bind the captured offer ID and optional canonical URL to the active page URL; cap request and field sizes; create an `EXTENSION_ENHANCED` SupplierData snapshot with `EXTENSION_DOM` provenance and explicit missing fields. Mark it as user-provided browser evidence. Use `activeTab` so page inspection occurs only on invocation; transmit only selected DOM text and source URL; keep backend ownership checks. A sparse page must yield a clear non-fabricated result.

**Never:** Read or transmit 1688 passwords, cookies, local/session storage, complete HTML, script bodies, platform request headers, or arbitrary page JSON. Do not bypass the 1688 challenge, claim an official API response, invent a risk score, add persistent source-site host access, or alter fixture/report scoring.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
| --- | --- | --- | --- |
| Visible offer | Signed-in customer invokes extension on 1688 offer page | Selected evidence becomes owner-scoped `PARTIAL`/`SUCCESS` snapshot; popup reports coverage and opens result | No raw page or source session data is stored |
| Sparse/challenge page | Offer URL but no selected supplier or product evidence | Explicit blocked/parse-failed outcome without snapshot or risk score | Explain the capture limitation |
| Wrong/unsupported page | Non-1688 tab, canonical/offer ID mismatch, oversized fields | Reject before storing supplier evidence | Show actionable error |
| Unauthorized/other owner | No Clerk session, non-CUSTOMER, quota exceeded, or foreign analysis ID | No capture or foreign result | 401/403/429/404 as appropriate |

</frozen-after-approval>

## Code Map

- `backend/app/extraction/offer1688.py`, `contracts.py` — existing URL normalization, coverage denominator and SupplierData v1; reuse field rules, keep HTTP/upload parser defaults.
- `backend/app/main.py`, `storage.py` — Clerk role dependency, quota, atomic snapshot persistence and owner-scoped status; add bounded capture endpoint and `EXTENSION_ENHANCED` admission without a queue.
- `frontend/apps/web/app/api/_backend.ts`, `frontend/apps/web/app/page.tsx`, `frontend/apps/web/app/extraction-evidence.tsx` — authenticated proxy, result polling, source labels; add capture proxy and deep-link result loading.
- `frontend/apps/extension/` — new Manifest V3 popup using Clerk's Chrome SDK, `activeTab` + `scripting` capture, narrow web/Clerk host permissions, and a build script that injects the existing publishable key. Clerk Native API is enabled; stable extension ID and allowed origin must be configured for browser sign-in.
- `backend/tests/`, `frontend/**.test.ts*` — existing auth, PostgreSQL, proxy and rendering patterns. Test selected payloads, negative binding, quota, ownership, and no session material in the capture contract.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/extraction/` — normalize an allowlisted DOM capture into SupplierData v1, with strict offer binding, bounded fields, coverage and `EXTENSION_DOM` provenance.
- [x] `backend/app/main.py`, `backend/app/storage.py` — authenticate, validate and atomically persist capture under `EXTENSION_ENHANCED`, using existing quota and owner polling.
- [x] `frontend/apps/web/app/api/`, `frontend/apps/web/app/page.tsx`, `frontend/apps/web/app/extraction-evidence.tsx` — proxy capture, open an analysis by deep link, and label browser evidence accurately.
- [x] `frontend/apps/extension/` — build a local Manifest V3 popup with Clerk sign-in, active-tab selected DOM capture, submit/poll/status, and open-report action; configure a stable ID and exact allowed origin.
- [x] `backend/tests/`, `frontend/**.test.ts*` — exercise every matrix row and ensure existing HTTP/upload paths still pass.

**Acceptance Criteria:**
- Given a signed-in buyer on a supported offer, when they invoke capture, then they can open their owner-scoped evidence result with accurate method, coverage and missing-field labels.
- Given a different buyer or a challenged/sparse page, when they attempt capture or polling, then no unsupported supplier claims or foreign evidence appear.

## Implementation Notes

- Built an unpacked Manifest V3 extension with a stable ID, Clerk session, active-tab selection, bounded capture, last-result recovery scoped to the Clerk user, and an owner-scoped web link. The old public URL and saved-page paths are intact.
- Pin `@clerk/chrome-extension` to 2.0.0. The npm registry available here did not serve versions required by newer Clerk releases; the pinned release typechecks, builds, and passed the user's live sign-in/capture flow.
- The selected DOM selectors were checked against the user's saved 1688 offer page. They deliberately leave unsupported fields unknown. The backend records server receipt time as the capture timestamp.
- Clerk extension origin registration succeeded and a second read confirmed it was already registered. Adding an explicit API client User-Agent resolved the observed network-protection rejection. Docker became available, PostgreSQL integration checks passed, and the user confirmed the live Chrome capture/result flow works.
- The user-supplied Alibaba.com token API documentation was reachable, but requires approved application credentials and an authorization code; 1688 coverage is unestablished. The official route is deferred under the user's registration constraint, as recorded in `1688-official-api-feasibility.md`.
- Windows reserves ports 7953–8052 in this session, so API port 8000 cannot bind. Started the API on 8080 and the web app on 3000 with `API_INTERNAL_ORIGIN=http://127.0.0.1:8080` in the web process environment; documented the restart override in the extension README.
- The user encountered a spinner after password submission in the extension modal. Replaced popup sign-in with a web-tab action and configured Clerk Sync Host (development web origin; production Clerk Frontend API host), preserving same-account backend authentication. The popup explains reopening after web sign-in and shows guidance after prolonged auth loading. Cached display state is cleared when the Clerk user changes. The user subsequently confirmed successful sign-in.
- The user confirmed the extension signed in, but capture returned 401. Inspection of effective settings showed the local `.env` lacked `CLERK_AUTHORIZED_PARTIES`, so the API trusted only its default web origins. Added the exact stable extension origin to the ignored local `.env` and restarted the API on 8080. Added signed-JWT coverage for the permitted extension and a different, rejected extension origin; live retries subsequently succeeded.
- Further live attempts rejected the authorized-party claim, followed by a successful strict validation on the next retry. No authentication rule was relaxed. The recorded capture `0de04712-826d-468c-8afc-07ec826dcf56` returned HTTP 201, with owner status GET 200, and persisted `COMPLETED` / `PARTIAL` / `EXTENSION_DOM` evidence at 25% coverage: supplier name, product title, and price text. Earlier cache reuse is a possible explanation, not a proved cause. The extension now requests a fresh token for capture/status; TypeScript, rebuild, and all 25 authentication tests pass. Only fixed rejection codes are logged; the temporary second-pass diagnostic was removed. The user confirmed the flow works and authorized closeout, noting limited extraction coverage.

## Plan Change Log

- 2026-09-30: During closeout, the user clarified that a successful extension capture should automatically open its web result. Added navigation after capture persistence and successful owner-status lookup; retained the manual reopen/recovery actions. The saved-HTML upload behavior and selected-fields-only capture boundary remain intact.

## Review Triage Log

| Finding | Verdict and evidence | Route |
| --- | --- | --- |
| Blind 1: price-only fields discarded | Low: the normalizer records no supplier snapshot without a supplier or product title, as the plan's sparse-page rule requires. Rejected; storing price alone as a supplier claim would weaken that boundary. | reject |
| Blind 2: mismatched canonical rejected | Low: a conflicting canonical does cause rejection, matching the explicit offer-binding requirement. Rejected. | reject |
| Blind 3: broad DOM selectors | Medium: generic `.price` and `.company-name` could select unrelated text. Replaced with selectors present in the saved offer page. | patch |
| Blind 4: localized review counts missed | Low: a nonnumeric aggregate stays unknown; guessing a localized count could fabricate precision. Rejected for this narrow capture version. | reject |
| Blind 5: loading page consumes quota | Maybe-false: it is unknown whether the live page shows the chosen fields while still loading. A live 1688 browser check would settle it; the current sparse result is explicit. | defer |
| Blind 6: server time differs from observation | Low: `captured_at` currently means trusted server receipt time; exact browser observation time is not established. Rejected as a provenance claim; notes now state the limit. | reject |
| Blind 7: POST success followed by GET failure loses ID | Medium: the popup previously dropped the created ID. It now saves the ID before GET and offers reload/open actions. | patch |
| Blind 8: popup close loses capture | Medium: web history only stores fixture reports. Extension-owned storage now keeps the last analysis ID, source URL, and owner ID. | patch |
| Blind 9: stale deep-link query after New Analysis | Low: refresh would reopen the old result. The query is removed on New Analysis and submit. | patch |
| Blind 10: form URL remains fixture | Medium: the captured result could be shown beside an unrelated fixture URL. Polling now updates the form URL for `EXTENSION_DOM`. | patch |
| Blind 11: separate web account gives unclear 404 | Low: owner scoping is correct but guidance was missing. The popup and web error now explain using the same account. | patch |
| Blind 12: cookies permission unused | False: Clerk's official Chrome extension quickstart requires `cookies` and `storage` permissions for its SDK, even though our code does not read 1688 cookies. | reject |
| Blind 13: selector test uses synthetic elements | Medium: it cannot prove a live 1688 page still uses the selectors. Checked the supplied saved page; live browser verification remains pending. | defer |
| Edge 1: Unicode truncation splits surrogate pair | Medium: JavaScript `slice` could produce malformed text. Truncation now uses Unicode code points and has a focused test. | patch |
| Edge 2: GET failure causes duplicate retry | Medium: retry used to create another capture. Reload now uses the saved analysis ID; a POST timeout before any ID is returned remains an explicit uncertainty. | patch |
| Edge 3: network request never resolves | Low: requests had no deadline. The popup now uses a 45-second timeout with distinct POST and GET messages. | patch |
| Gap 1: popup interaction has no mounted test | Medium: unit tests cover selection, API behavior, and rendering, but not the mounted popup click. Deferred to the required live Chrome click-through because no browser session is exposed here. | defer |
| Gap 2: analysis GET preflight untested | Medium: failure would block popup status after a successful POST. Added an OPTIONS assertion for the owner-status route. | patch |
| Gap 3: web deep-link navigation untested | Medium: a mounted page/browser check is still needed for `/?analysis=<id>` to status polling. The production build passes; live click-through remains pending. | defer |
| Intent alignment: real-browser boundary | Medium: the diff implements the literal workflow but synthetic tests cannot prove Clerk sign-in or a challenge-cleared live 1688 tab. The live check is pending. | defer |
| User click-through: sign-in hangs after password | Medium: the screenshot confirms the popup modal remains on a spinner after password submission; the exact Clerk network failure is not yet observed. Replaced modal authentication with web sign-in and the documented SDK Sync Host integration. Rebuild, TypeScript, and existing 26 frontend tests pass; the user must reload the extension and retry to verify live synchronization. | patch |
| User click-through: capture Unauthorized | Medium: effective backend settings omitted the stable extension origin; configured it. A later retry also reported an origin-claim rejection, then succeeded with strict validation unchanged. Added exact-extension JWT acceptance/rejection coverage and fresh client token requests; live capture persistence and owner lookup now pass. | patch |

## Verification

**Commands:**
- `.venv/Scripts/python.exe -m pytest backend/tests -q` with PostgreSQL test URL — backend regression passes.
- `npm test --prefix frontend`, `npm run typecheck --prefix frontend`, `npm run build --prefix frontend` — web and extension checks pass.

**Observed:** Final full backend regression passed 139 tests with one opt-in live Azure test skipped, using the dedicated `vct_closeout_20260930_01` database. An initial run against the shared app database exposed a test claiming an unrelated existing outbox job; the clean isolated run resolved that interference. All 26 frontend tests, frontend TypeScript, web production build, and extension build passed. Clerk allowed-origin registration was verified. The user's live sign-in, capture, owner status lookup, and result flow succeeded; the captured snapshot has 25% coverage with three visible fields. The final automatic-opening addition passed compilation and a focused read-only review; it requires extension reload to activate and has not been separately observed in the user's Chrome session.

**Matrix audit:** Supported offer and provenance are covered by capture/auth/PostgreSQL/rendering tests and the live capture. Sparse/empty fields, mismatched IDs/canonical URLs, unsupported tabs, over-limit input, unauthorized/non-CUSTOMER/quota/other-owner requests are covered by the passing extraction, auth, capture, and proxy tests. HTTP and saved-HTML import paths passed the full regression suite.

**Manual checks:** Load the built unpacked extension, sign in with Clerk, capture an opened 1688 offer, inspect Network payload for selected fields only, and open the owner-scoped result. Browser sign-in and 1688 page behavior require a live Chrome session.
