---
title: 'Recover blocked Taobao analyses using captured or saved evidence'
type: 'feature'
ticket: ''
created: '2026-10-01'
status: 'built'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: [blind-hunter, edge-case-hunter, verification-gap, intent-alignment]
review_loop_iteration: 0
baseline_revision: '968273095d2693fac4d71d9f09a2327385264816'
context:
  - 'C:/Users/eidel/Desktop/VCT Connect/_bmad-output/initiative-vct-connect-year-one/epic-extraction/story-add-the-taobao-source-adapter-plan.md'
  - 'C:/Users/eidel/Desktop/VCT Connect/_bmad-output/initiative-vct-connect-year-one/epic-extraction/taobao-sample-audit.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Taobao public requests encounter challenges; buyers need reliable evidence from pages they can access. Follow-up review also confirmed parser defects that would affect imported evidence.

**Approach:** Correct every confirmed follow-up finding, then extend authenticated HTML import and user-invoked Chrome capture to the audited Taobao product/shop forms. Reuse atomic owner-scoped results and automatic opening, with honest provenance.

## Boundaries & Constraints

**Always:** Preserve 1688, SupplierData v1, 12 fields, explicit unknowns, seven statuses, quota, ownership, immutable replay and bounded public fetching. Bind source identity and canonical hints; reject ambiguity. Capture selected visible text/links only, within 16,384 bytes; import within 2,000,000 original bytes. Exclude inactive/hidden capture nodes. Keep full HTML only in memory; retain selected raw values and truncation extent. Uploads use ACCOUNT_PUBLIC/USER_UPLOAD, original-byte hash, import time and unknown capture time. Captures use EXTENSION_ENHANCED/EXTENSION_DOM and user-provided provenance. User evidence cannot overwrite shared supplier metadata.

**Never:** Transfer source credentials, cookies, tokens, storage, page globals, scripts or full HTML from the extension; execute imported scripts, bypass challenges, add persistent source host permissions, guess fields, add Tmall/mobile/short-link support, scoring, merge/deduplication, or change the original Story 2.3 intent.

## I/O & Edge-Case Matrix

| Scenario | Input | Outcome | Handling |
| --- | --- | --- | --- |
| Saved page | Matching audited item UTF-8 or shop GBK | Owner-scoped uploaded snapshot | No public-fetch claim or queued work |
| Capture | Customer invokes on accessible item/shop | Selected evidence and automatic web result | Safe last-result recovery |
| Missing evidence | Challenge/sparse page | Explicit failure or partial unknowns | No fabricated supplier snapshot |
| Wrong identity | Different item/shop/canonical or prior context | Rejection/failure without snapshot | No source reassignment |
| Invalid input | Oversize, unknown fields/encoding, unsupported URL | Bounded 413/415/422 | No analysis for admission errors |
| Unauthorized | Missing/wrong role, quota, foreign owner | Existing 401/403/429/404 | Atomic admission and ownership |

</frozen-after-approval>

## Code Map

- `backend/app/extraction/taobao.py` — resolve all 13 context-plan Code Review patches; add upload provenance/encoding.
- `backend/app/extraction/extension1688.py`, new Taobao normalizer — preserve legacy schema; dispatch strict bound Taobao fields.
- `backend/app/main.py`, `storage.py` — CUSTOMER import/capture, explicit method/mode/platform guards matching analysis provenance; retain atomic non-overwriting storage.
- `frontend/apps/extension/src/{capture.ts,popup.tsx}`, `build.mjs` — audited visible DOM, stable key/auth, automatic navigation.
- `frontend/apps/web/app/` status/evidence/page, `frontend/packages/api-client/src/index.ts` — recovery wording, provenance, unchanged bytes without false UTF-8 declarations.
- `infra/azure/main.bicep` — allow existing exact stable extension origin alongside web origin; preserve strict Clerk validation.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/extraction/taobao.py`, fixtures/tests — all review patches and regression gaps; preserve full-capture parsing.
- [x] `backend/app/extraction/`, `main.py`, `storage.py` — import/capture, encoding, provenance and guards.
- [x] `frontend/apps/extension/` — bound item/shop visible selection, byte caps and open/reload.
- [x] `frontend/apps/web/`, API client, `infra/azure/main.bicep` — truthful recovery, file flow and exact extension trust.
- [x] `backend/tests/`, frontend tests — matrix, privacy, DOM scope, production transport, persistence and 1688 regressions.

**Acceptance Criteria:**
- Given a customer and matching saved product/shop page, when imported, then owner polling renders traceable Taobao evidence and another account gets 404.
- Given a customer on an accessible Taobao tab, when captured, then selected evidence is saved and its web result opens automatically, with no source session data in the request.
- Given existing 1688 workflows, when regressions run, then HTTP, import, capture and fixture behavior remain valid.

## Implementation Notes

User approval covers fixes and recovery; original intent stays intact. Full route: over 100 lines across layers. Dirty review notes belong to this authorized run; preserve user untracked files.

## Plan Change Log

- 2026-10-01: Added focused `capture-result.ts` / `capture-result.test.ts` helpers and registered their tests in `frontend/package.json` to verify automatic opening and owner recovery. Approved intent is unchanged.

## Review Triage Log

### Build review — 2026-10-01

All four lenses completed before triage. Capacity allowed three concurrent children; intent started after the edge lens finished. No lens was skipped. 25 findings receive individual verdicts below; duplicates are grouped only afterwards. Ten patch entries, zero intent gaps/bad plans/deferred entries, nine rejected findings.

| ID | Verdict | Route | Finding and verified evidence |
| --- | --- | --- | --- |
| B1 | medium | patch | **Quoted/commented ICE writes:** Parent prepended quoted and commented assignment examples to a valid fixture; each incorrectly returned PARSE_FAILED. |
| B2 | high | patch | **Hidden executable ICE writes:** A hidden inline script assigning a conflicting ICE context still executes in browsers; parent reproduction incorrectly retained PARTIAL requested-item evidence. |
| B3 | medium | patch | **Transparent selected descendants:** Parent injected opacity:0 and visibility:collapse review descendants; both survived normalized and raw evidence. |
| B4 | medium | patch | **Hidden access-barrier text:** Sparse HTML containing hidden captcha or sign-in text incorrectly returned BLOCKED or AUTH_REQUIRED; access classification does not prune hidden descendants. |
| B5 | medium | patch | **Canonical rel token matching:** Exact rel selector omits alternate canonical and case variants; backend validation cannot reject an omitted hint. |
| B6 | medium | patch | **Malformed shelf links abort capture:** Parent collector reproduction placed an invalid visible URL before a valid card; URL construction threw and aborted all evidence. |
| B7 | low | reject | **display:contents wrapper visibility:** The collector omits rectangles-free wrappers under this CSS value. Audited samples do not use it for selected regions; normal supported use does not encounter it. Supporting it adds visibility branches, so reject this low improvement. |
| B8 | medium | patch | **Rendered paragraph boundaries:** Parent collector reproduction yielded firstsecond from distinct visible paragraphs after a hidden child triggered the text-walker fallback. |
| B9 | high | patch | **Unrelated supplier name selection:** Parent collector with only an unrelated shopName recommendation retained it as supplier_name. Original item/shop samples establish narrower supplier ancestry. |
| B10 | false | reject | **Collection omission disclosure:** The capture stores selected evidence, not a claim of complete source collections. Limits are documented; retained review original_length discloses text extent, and the UI does not claim collection totals. No incorrect total or completeness claim was demonstrated. |
| B11 | low | reject | **Malformed stored analysis ID:** Manually corrupted local records can restore unusable string IDs, but successful API submissions provide UUIDs. This is not an ordinary reachable record and adding a restoration guard would add complexity. |
| E1 | high | patch | **Hidden executable context assignment:** Same demonstrated execution-eligibility root as B2; visual hiding does not make scripts inert. |
| E2 | medium | patch | **Quoted/commented assignment example:** Same reproduced lexical false-positive root as B1. |
| E3 | medium | patch | **Transparent/collapsed descendants:** Same parent reproductions and DOM visibility root as B3. |
| E4 | medium | patch | **Canonical rel token matching:** Same verified exact-selector omission as B5. |
| E5 | medium | patch | **Invalid visible shelf URL:** Same parent Invalid URL reproduction as B6. |
| E6 | high | patch | **Claimed prior-context fix misses hidden scripts:** Same demonstrated execution-eligibility root as B2/E1, retained individually before grouping. |
| G1 | medium | patch | **Captured review normalization regression gap:** Reviewer mutated normalized reviews away and relevant API cases still passed. Add exact raw/normalized owner response and PostgreSQL review assertions. |
| G2 | medium | patch | **Cross-kind field restriction regression gap:** Reviewer disabled both page-kind restrictions and relevant API cases still passed. Exercise every forbidden field with 422 and unchanged admission count. |
| I1 | false | reject | **Simulated DOM versus actual Chrome:** Descriptive verification boundary; real Chrome capture is explicitly pending and no rendered-browser success is claimed. |
| I2 | false | reject | **Callback order versus tab lifetime journey:** Actual tab call is wired to the tested helper. Browser lifetime/authentication acceptance remains pending; no incorrect order or navigation result was demonstrated. |
| I3 | false | reject | **Layered import checks versus continuous browser journey:** Separate admission, persistence, client and presentation tests establish their boundaries. A continuous browser journey is not claimed as verified. |
| I4 | false | reject | **Deployment pending:** Deployment remains the authorized next phase and no deployed success is claimed. |
| I5 | false | reject | **Consistency versus independent source authentication:** USER_PROVIDED provenance correctly identifies trust; the intent requires bound source identity and traceability, not independent authentication of user-supplied bytes. |
| I6 | false | reject | **Fixture cases versus live layout compatibility:** Audited layout bounds are explicit and original captures were checked; current live Chrome compatibility remains an operational check without a success claim. |

Patch groups: B1/E2; B2/E1/E6; B3/E3; B4; B5/E4; B6/E5; B8; B9; G1; G2. Each smallest correction uses existing fields and demonstrated state; no public surface or frozen-intent amendment is needed. B7/B11 are low improvements rejected under the workflow rule; the remaining rejected rows are refuted as above.

## Design Notes

Audited DOM: ItemTitle/MainTitle, Comments/Comment/contentWrapper/content, matching shop name/metrics and shopProductShelfArea/title links. Shop age/evaluations lack verified visible fields: leave unknown. Taobao uploads allow UTF-8/GBK-family with explicit MIME/meta precedence; reject unsupported/conflicting declarations and retain 1688 UTF-8 rules. Reject ambiguous prior ICE overrides. Raw review segments retain original text and truncation extent. Public access can remain blocked.

## Verification

- Full backend pytest against isolated PostgreSQL with fresh workspace basetemp/cache disabled.
- Frontend tests, typecheck, production builds and credential scan; pass.
- Original product/GBK shop audit: matching identities/provenance and existing coverage; no private-state output.
- `git diff --check`; commit reviewed files only.
- Parent phase after review: existing dev deployment, ingress/challenge/upload/ownership/1688 checks, deployed-origin extension build. Pause for missing credentials. User's real Chrome capture remains pending until observed.

### 2026-10-01 execution checkpoint

- Parent full backend run: **316 passed, 51 skipped**, fresh `tmp/recovery-root-20261001-03`, cache disabled. Database tests did not run; do not count them as passed.
- Final parent frontend run: **63 passed, zero skipped**; TypeScript passed. Final extension rebuild passed for `http://127.0.0.1:3000`. Earlier web production build passed; Bicep compilation and tracked diff whitespace check passed.
- Original upload audit: product 472,468 bytes, PARTIAL 6/12, two reviews; GBK shop 722,085 bytes, PARTIAL 4/12, 20 products. Original-byte hashes and USER_UPLOAD provenance checked.
- Original DOM projection audit: product selected request 622 bytes; shop 3,356 bytes with 20 products. Visibility was simulated; this does not establish real Chrome capture success.
- Parent reproduced and corrected JSONB-invalid text admission and deeply nested JSON errors. Registered regressions pass. Collector also handles repeated equivalent shop names, anchor cards and hidden descendants; automatic-opening/storage-failure/owner-recovery tests pass.
- Current blocker: Docker Desktop's engine is unresponsive and its Windows service is stopped. Parent requested a restart and an “Engine running” confirmation from the user. Portable database download was abandoned; no database setup completed.
- Remaining: full isolated PostgreSQL run; final unified diff including the new helper/test and plan; BMad build review; reviewed commit; approved Azure dev deployment and deployed-origin extension build; real Chrome capture check. Status remains in-progress. No commit, push or deployment in this continuation.

- Final credential scans passed for both the existing web production build and rebuilt extension bundle. No configured server credentials found.

### PostgreSQL verification and matrix audit

Docker was restored after the user's confirmation. Local `vctconnect-db-1` is healthy. Parent ran the complete suite against isolated `vct_recovery_20261001`: **366 passed, one opt-in Azure test skipped**, in 239.50 seconds. All database-dependent tests ran and passed. The prior Docker blocker is resolved.

Each matrix row has executed passing coverage:
- Saved page: `test_taobao_upload_original_bytes_owner_and_encoding` and `test_taobao_user_evidence_atomic_ownership_replay_quota_and_shared_metadata` (item/shop and upload/capture combinations).
- Capture: `test_taobao_capture_selected_evidence_owner_and_strict_schema`, item/shop DOM tests and `capture-result.test.ts` save/open/load and recovery tests.
- Missing evidence: `test_barriers_and_unbound_evidence_are_terminal`, `test_missing_fields_remain_unknown_and_reviews_are_scoped`, and shared sparse-capture admission tests.
- Wrong identity: model/page binding, imported canonical, prior-context, and capture source-ID/canonical admission tests.
- Invalid input: upload bounds/encodings, capture bounds/extra fields, JSONB-invalid text and deep nesting, plus URL admission tests.
- Unauthorized: missing identity/customer role, owner/foreign polling, persisted quota and immutable replay tests.

Next: final BMad review and any confirmed fixes, commit, approved dev deployment and real Chrome capture. No deployed success is claimed.

### Final review corrections and verification

All ten patch groups were corrected by the implementation agent and verified by the parent. No findings were deferred. The two low-priority improvements remain rejected with the reasons recorded above.

Parent also reproduced two identity regressions during correction: executable ICE writes inside template interpolation, and visually hidden canonical metadata. Both now fail closed with dedicated passing regressions; these extend the existing executable-context and canonical-identity patch groups without changing intent.

Final parent verification: **394 backend tests passed, one opt-in Azure test skipped**, against isolated PostgreSQL `vct_recovery_20261001`; **67 frontend tests passed**, with zero skips; TypeScript passed. Original sample audits remain product **6/12** and shop **4/12**, with 622-byte item and 3,356-byte shop DOM projections. Projection visibility is simulated, so real Chrome acceptance remains pending.

Implementation and review are complete. Production builds, credential scans, reviewed local commit and authorized dev deployment are recorded below as they complete. Live browser capture and signed-in acceptance require the user's session and remain explicit operational gates.

- Production web and extension builds passed, web credential scan passed, Bicep compilation passed, and whitespace checks passed. Extension rebuilt for the Azure development web origin; stable extension ID retained. Remote main remains an ancestor of the reviewed local revision, so the authorized push can proceed normally.

### Release gate correction

Release commit `5b3e565` was pushed under existing approval. CI on Python 3.12 rejected an existing 1688 test that assumed 2,000 JSON nesting levels always exhaust the decoder; the Windows Python 3.11 run had passed. Both runtimes safely reject the array, but Python 3.12 reports MALFORMED_PAGE when decoding succeeds. The test now verifies safe rejection independently of runtime depth and separately injects an actual decoder RecursionError to verify the exact PARSER_LIMIT contract. Production parser behavior is unchanged. Deployment was skipped by the CI gate; no release success is claimed until the corrected run passes.

The corrected CI passed backend, frontend, typecheck, production build and credential gates, then exposed an existing Docker workspace mismatch: the web image invoked the root build (including the extension) after installing without its workspace manifest. The web Dockerfile now installs the complete declared workspace graph and builds its web artifact explicitly. Docker context also excludes all nested node_modules and generated extension bundles, avoiding host dependencies in Linux images. CI continues to verify the extension separately through the root build.

Local verification of the Docker correction could not pull node:22-alpine because Docker Desktop cannot resolve registry-1.docker.io, even with elevated execution. The corrected image will be verified by the existing GitHub CI Docker gate, whose previous run successfully accessed Docker Hub. No local image-build pass is claimed.

### Deployed release verification

- Released revision: `ce914c3e99b23580d7b924c815372ea5fb319b1e` (implementation `5b3e565`, test portability `e7b7608`, Docker correction `ce914c3`).
- CI run **36846986620** passed: **395 backend tests, one opt-in Azure skip; 67 frontend tests**, typecheck, production build, credential scan, backend/web Docker images and Azure template compilation.
- Azure Deploy dev run **36847751380** succeeded, including target/Key Vault checks, digest image publishing, baseline convergence, successful private migration, processor activation, ingress/private API boundary and guest fixture completion.
- API ready revision `vct-connect-dev-api--0000003` contains the exact cloud web and stable extension Clerk authorized parties.
- Parent deployed checks passed: capture/import return 401 without authentication; exact extension CORS is preserved. Guest item **12AA8D20** and shop **7AFC5C82** completed with **BLOCKED / ACCESS_CHALLENGE**, no supplier snapshot, PUBLIC_HTTP/GUEST_PUBLIC provenance, and foreign guest access rejected.
- Extension built and credential-scanned for `https://vct-connect-dev-web.blackdesert-0144dda1.southeastasia.azurecontainerapps.io`; reload the unpacked `frontend/apps/extension/build` to use it.
- Remaining operational acceptance: user's current Chrome session must verify accessible Taobao item/shop capture, automatic result opening, and signed-in saved HTML import. Local automated ownership/import/persistence checks passed; real Chrome and signed-in cloud acceptance are not claimed. Pausing for that required user action under the standing instruction.

### User browser capture checkpoint

User reported completing the requested Chrome capture check, but could not locate the ID. A parent read-only query through the deployed private API container found the latest customer Taobao capture: **8509C888** (`8509c888-bff2-414f-827b-ab69e82e6909`), source item **1053813155889**, created/completed **2026-10-01 12:50:35 UTC**. It is COMPLETED / PARTIAL, EXTENSION_ENHANCED / EXTENSION_DOM, with USER_PROVIDED_BROWSER_EVIDENCE provenance, **4/12 fields**, **four reviews**, and **one product**. The query returned only metadata/counts, no account/session data or review bodies. This confirms a real signed-in cloud capture persisted successfully; automatic opening is supported by the user's completion report, without independent browser observation. Saved HTML import and live shop capture acceptance remain pending.
