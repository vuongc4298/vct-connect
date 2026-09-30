---
title: 'Add the Taobao source adapter'
type: 'feature'
ticket: '3'
created: '2026-09-30'
status: 'built'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['blind-hunter', 'edge-case-hunter', 'intent-alignment', 'verification-gap']
review_loop_iteration: 0
followup_review_recommended: true
warnings: [oversized]
deferred: []
baseline_revision: '499d255011ab0979b77e564feab0f5327d929251'
context:
  - 'C:/Users/eidel/Desktop/VCT Connect/_bmad-output/initiative-vct-connect-year-one/epic-extraction/epic-extraction.md'
  - 'C:/Users/eidel/Desktop/VCT Connect/_bmad-output/initiative-vct-connect-year-one/epic-extraction/taobao-sample-audit.md'
---

<intent-contract>

## Intent

**Problem:** The queued path accepts only 1688. Taobao has no adapter despite its presence in SupplierData v1.

**Approach:** Add Taobao product/shop HTTP extraction grounded in representative captures, reusing bounded fetching, durable snapshots and source-aware presentation.

## Boundaries & Constraints

**Always:** Preserve SupplierData v1, its 12-field denominator, seven statuses, explicit unknown fields, raw source values used in normalization, page hash, timestamp, method, mode and extractor version. Bind evidence to the requested item/shop identity. Keep HTTPS host/path allowlists, public-IP pinning, safe redirects, 2 MB response limit, 25-second budget and two transient retries. Validate stored platform against the canonical analysis URL; namespace supplier identities by platform. Preserve authorization, quota, lease checks and immutable replay.

**Never:** Implement Tmall, Alibaba, short-link expansion, Playwright, source login/cookie transfer, challenge bypass, risk scoring or extension merge. Guess selectors or fabricate absent evidence. Advertise Taobao extension capture or HTML import: those existing paths remain explicitly 1688-only. Do not broaden arbitrary Taobao subdomain access or silently follow a different item/shop.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
| --- | --- | --- | --- |
| Supported URL | Verified Taobao product/shop with tracking | Canonical identity-preserving URL and Taobao dispatch | Reject unsafe/ambiguous forms before queueing |
| Accessible page | Matching identity and observed evidence | Versioned SUCCESS/PARTIAL, raw evidence and coverage | Absent fields remain unknown |
| Changed page | Malformed, unbound or mismatched evidence | PARSE_FAILED | No snapshot |
| Access barrier | Login, CAPTCHA or block | AUTH_REQUIRED/BLOCKED with honest guidance | No retry or bypass |
| Fetch failure | Transient, unsafe, unavailable, slow or oversized | Shared bounded fetch/status policy | No unsafe connection or incomplete-body parsing |
| Durable result | Replay or cross-platform seller ID collision | Immutable snapshot; separate supplier identities | Preserve lease, ownership and replay conflicts |

**Decision (user samples supplied):** Verify item `1076425861755` and shop `159450000` using the saved browser pages. Product URLs retain the unique numeric `id`; shop hosts are numeric `shop<ID>.taobao.com` or `shop<ID>.world.taobao.com`, with `/`, `/index.htm` or `/category.htm`. Strip tracking; bind main-model identities; allow redirects only within the same verified item/shop. Captures verify parsing, not anonymous server access.

</intent-contract>

## Code Map

- `backend/app/extraction/urls.py` — canonical platform/identity detection; strict Taobao forms alongside existing 1688 validation.
- `backend/app/extraction/offer1688.py`, new shared fetch module — reusable checked-IP transport, retry/budget policy and explicit adapter callbacks; retain 1688 regression/injection points.
- New `backend/app/extraction/taobao.py` — observed ICE product and `window.g_config` shop models, scoped DOM reviews, UTF-8/GBK decoding and JSON-safe evidence. See the sample audit for mappings/privacy exclusions; never execute scripts.
- `backend/app/extraction/__init__.py`, `backend/app/main.py::Submission`, `backend/worker/main.py::_compute_claim` — platform admission/dispatch; preserve fixture and 1688 import/capture.
- `backend/app/storage.py::_complete_processing` — source-bound platform parameters in supplier checks/SQL. Schema already permits TAOBAO with platform-scoped identity; no migration expected.
- `frontend/apps/web/app/analysis-status.ts`, `extraction-evidence.tsx`, `page.tsx` — source-aware submission, links, evidence and guidance; contracts already permit TAOBAO.
- `backend/tests/`, frontend status/evidence tests — sanitized layouts, adapter/fetch matrix and queued persistence regressions.

## Tasks & Acceptance

**Execution:**
- [x] `backend/tests/fixtures/` — audit product/shop captures, sanitize fixtures and record observed fields, supported forms and provenance.
- [x] `backend/app/extraction/` — Taobao URLs/parser/adapter and shared bounded fetch; retain 1688 behavior.
- [x] `backend/app/main.py`, `backend/worker/main.py`, `backend/app/storage.py` — admission, dispatch and atomic platform-correct persistence.
- [x] `frontend/apps/web/app/` — Taobao submission, source labels, safe links and honest guidance.
- [x] `backend/tests/`, frontend tests — matrix coverage, guest/account modes, owner polling, replay and platform isolation.

**Acceptance Criteria:**
- Given representative Taobao pages, when submitted through the queue, then owners receive traceable snapshots or correct terminal outcomes.
- Given existing 1688 workflows, when regressions run, then fixture, public extraction, import and extension contracts remain valid.

## Implementation Notes

- Added strict identity-preserving Taobao admission, same-item/shop redirects, audited ICE/g_config parsing and platform dispatch. Shared checked-IP fetching retains the 1688 injection points and policy.
- Sanitized product/shop fixtures retain public normalization values and observed DOM scope only. Local full captures yield matching partial evidence (product 6/12; shop 4/12). Original capture timestamps remain unknown.
- Supplier persistence validates the canonical analysis platform and uses `(platform, platform_supplier_id)` for every supplier lookup/write. Taobao remains PUBLIC_HTTP only; import/capture validation remains 1688-only.
- Source links and recovery guidance distinguish Taobao, preserve approximate counts/price contexts, and describe displayed shop age without claiming legal incorporation age.
- Live probes on 2026-09-30 UTC returned HTTP 200 script challenges for both approved URLs; final adapter outcomes are `BLOCKED / ACCESS_CHALLENGE`. Observed TMD `login_jump` scripts set `window._config_`, write a challenge cookie and navigate via `location`; classification requires that structure on a page without visible public content. No challenge tokens or response cookies are retained.
- Focused extraction verification: 170 passed (107 existing 1688 + 63 Taobao). Frontend: 48 tests passed, typecheck passed, full web/extension production build passed with normal filesystem access. The sandbox extension build initially failed on esbuild parent-directory access; the approved build succeeded.
- Initial full backend run: 250 passed, 46 database/Azure tests skipped because no `VCT_TEST_DATABASE_URL` was set in the implementation shell. Added queued product/shop guest/account ownership, replay and platform-collision integration tests await the primary session's isolated PostgreSQL verification. Azure verification follows deployment.

## Plan Change Log

## Review Triage Log

### 2026-10-01 — Review pass

- verdicts: 22 findings — high 0, medium 12, low 3, false 7, maybe-false 0
- findings:
  - `[medium]` `[patch]` Blind 1: commented g_config supplies evidence — Reproduced PARTIAL from a commented assignment; constrain recognition to the actual audited assignment/wrapper and cover it. Fixed: Anchored audited assignments/wrappers; commented and quoted assignments fail.
  - `[false]` `[reject]` Blind 2: duplicate JSON keys imply conflicting effective identity — JSON and the source object use the final key value; the accepted effective item ID and SSR ID both match the requested source. The claimed different-item snapshot was not demonstrated. Strict duplicate-key rejection would add a new parsing rule.
  - `[medium]` `[patch]` Blind 3: challenge vocabulary hides bound public evidence — Reproduced BLOCKED from a navigation help phrase added to a valid capture; use verified useful identity-bound evidence to scope body vocabulary. Fixed: Verified useful bound evidence prevents incidental vocabulary becoming a wall.
  - `[medium]` `[patch]` Blind 4: incidental script keys suppress a real login wall — Reproduced PARSE_FAILED for a body login prompt plus seller:null metadata; replace substring evidence detection. Fixed: Incidental metadata is no longer public evidence; real login/challenge bodies are classified.
  - `[medium]` `[patch]` Blind 5: unrelated shop cards contaminate products — Global .shop-item-card scanning admits cards outside the actual shopProductShelfArea-- container; scope to the audited container. Fixed: Scoped cards to the observed shopProductShelfArea-- container.
  - `[medium]` `[patch]` Blind 6: empty evaluations inflate completeness — Reproduced transaction_signals with four null fields from evaluates:[{}]; filter entries lacking useful labeled metrics. Fixed: Require meaningful metric title and score.
  - `[low]` `[patch]` Blind 7: observed shop product titles are dropped — Full capture contains title-- nodes with matching public title attributes; preserve those values in evidence and sanitized fixtures. Fixed: Retain observed title-- attribute/text.
  - `[medium]` `[patch]` Blind 8: selected raw values are normalized — Reproduced raw priceText losing source whitespace; retain original selected values separately from normalized evidence. Fixed: Preserve original selected price/rate/duration/metric values separately.
  - `[low]` `[patch]` Blind 9: shop collection is hidden in the evidence view — The component only reads products[0].title; render bounded existing product data with validated links and ID fallback. Fixed: Render the bounded collection with title/ID fallback and identity-checked links.
  - `[low]` `[patch]` Blind 10: safety failures are described as login barriers — Taobao BLOCKED branch ignores unsafe/source-mismatch/loop reasons; select accurate safety guidance first. Fixed: Select safety/identity guidance before access guidance.
  - `[false]` `[reject]` Intent 1: captured HTML versus live source — The approved intent explicitly permits classified access failures; capture-only parser success is documented and the live probes return BLOCKED without claiming public snapshots.
  - `[false]` `[reject]` Intent 2: mocked transport versus live network — Deterministic fetch tests and documented real access probes establish different evidence honestly; the intent does not require an unattended live test.
  - `[false]` `[reject]` Intent 3: joined component verification versus continuous live roundtrip — Owner-scoped queued persistence and HTTP behavior are exercised separately; actual live access is blocked and Azure verification is explicitly pending deployment, so no continuous live success is claimed.
  - `[false]` `[reject]` Intent 4: Taobao barriers are not newly tested through queued polling — Shared completed-failure owner-polling tests run, Taobao dispatch is tested, and source failure persistence is platform-independent. The report identifies test granularity without demonstrating an unmet outcome.
  - `[false]` `[reject]` Intent 5: bounded URL forms versus general Taobao coverage — The user-approved decision names desktop item and numeric shop forms and rejects unverified families; the diff matches that decision.
  - `[false]` `[reject]` Intent 6: component tests versus browser journey — Submission/polling integration and rendered guidance are verified; the change does not claim a real signed-in browser/Azure smoke. This remains a documented manual/deployment limitation.
  - `[medium]` `[patch]` Gap 1: independently conflicting SSR ID regression is undetected — Reviewer mutation prefers itemId and all 63 tests still pass; add a mismatched SSR ID with matching item ID. Fixed: Added independent conflicting SSR ID regression.
  - `[medium]` `[patch]` Gap 2: privacy checks only receive sanitized inputs — Reviewer source-model retention mutation passes all 63 tests; inject private sentinel values and assert they are absent. Fixed: Injected private user/session/cart/reviewer sentinels and asserted absence.
  - `[medium]` `[patch]` Gap 3: shop metric/age rendering is unasserted — Current render test supplies no shop metric or age fields; add observable labels, values and legal-age qualification assertions. Fixed: Asserted rendered metric labels/values, product links and qualified age.
  - `[medium]` `[patch]` Edge 1: bound page vocabulary becomes a block — Same reproduced access-classification defect as Blind 3; patch verified-evidence handling and preserve actual barriers. Fixed: Same verified-evidence fix as Blind 3.
  - `[medium]` `[patch]` Edge 2: incidental script substrings suppress login — Same reproduced login-classification defect as Blind 4; patch verified-evidence handling. Fixed: Same incidental-metadata fix as Blind 4.
  - `[medium]` `[patch]` Edge 3: empty evaluations count as evidence — Same reproduced missing-field defect as Blind 6; filter meaningless entries. Fixed: Same meaningful-metrics filter as Blind 6.

All four lenses completed before triage. Runtime capacity required staggered launches; snapshot ACL restrictions initially blocked two readers. Elevated reads succeeded after automatic approval review rejected an ACL-changing operation. No ACL change was made. Grouped outcomes retain all 22 individual rows; 15 patched findings resolve into 12 root-cause entries (9 medium, 3 low); 7 were rejected and none deferred.

## Verification

Final verification after review corrections on 2026-10-01: **319 backend tests passed, 1 opt-in Azure test skipped**, with one existing Starlette deprecation warning; **54 frontend tests passed**; TypeScript, web/extension production builds, and frontend credential scan passed. Full captures still produce PARTIAL product 6/12 and shop 4/12; the shop includes 20 observed titled products. Commands used the isolated local PostgreSQL database and a fresh workspace-local pytest temp directory.

Primary verification: 297 backend tests passed on isolated `vct_story23_20261001`; one opt-in Azure check skipped, one existing Starlette warning. Fresh workspace-local pytest temp directory avoids pre-existing Windows temp/cache ACL errors. Corrected the platform-isolation test to use guest-mode evidence matching guest analyses; stripped tracking from sanitized shop links. Frontend rerun: 48 passed; TypeScript and credential scan passed.

Matrix audit: URL admission/dispatch, bound and sparse captures, malformed identities, access barriers and fetch failures ran in the extraction suites; PostgreSQL queue/owner/replay/platform-isolation cases ran and passed. Existing deadline/DNS/transport cases cover the reused fetcher.

- `.venv/Scripts/python.exe -m pytest backend/tests -q` with an isolated database — matrix/persistence/authorization/1688 regressions pass.
- `npm test --prefix frontend`, `npm run typecheck --prefix frontend`, `npm run build --prefix frontend` — UI/contracts/builds pass; register any new test files.
- `.venv/Scripts/python.exe scripts/scan_frontend_secrets.py`, `git diff --check` — clean.
- Audit full captures locally; commit sanitized fixtures only. Probe real URLs and record actual outcomes; Azure verification follows deployment.

## Points of Contention

- Public Taobao access currently yields challenge pages; parser acceptance uses the supplied authenticated captures and cannot establish live public success.
- Taobao capture/import remains outside this approved story, so a blocked user currently has no Taobao extension recovery path.
- Displayed shop age, approximate counts and contextual shop metrics are evidence labels, not legal incorporation age, exact transaction totals or product ratings.
- Duplicate JSON keys use the effective final value, matching the source JavaScript object. Both effective item and SSR identities must still match the request; this pass did not introduce a separate duplicate-key rejection policy.
- Supported layouts and URLs are deliberately bounded to the audited desktop item and numeric-shop forms. Other Taobao layouts, Tmall and shortened links remain unverified and unsupported.
- Azure deployment and a signed-in browser journey through the deployed queue were not performed in this local implementation round. Deterministic transport, database ownership/replay, component rendering and real access probes provide separate evidence.
- A follow-up review is recommended for the corrected access classification and shop shelf/model scope against unseen layouts; the corrections pass regressions but have not received a second independent review.

## Auto Run Result

**Status:** built — first implementation/review round complete, local commit only.

Added the Taobao product/shop HTTP adapter, source-bound durable storage and source-aware UI. Public extraction stays bounded and reports access barriers honestly. Existing 1688 import/capture and fixture behavior remain covered by regressions.

### Files changed

- `backend/app/extraction/fetch.py` — shared checked-IP HTTP transport, redirect, retry, deadline and body policy.
- `backend/app/extraction/offer1688.py` — reuse transport while preserving existing adapter/injection contracts.
- `backend/app/extraction/taobao.py` — identity-bound audited models, scoped public evidence, original selected values and access classification.
- `backend/app/extraction/urls.py` — strict Taobao forms, canonical identities and platform detection.
- `backend/app/extraction/__init__.py` — export the Taobao adapter.
- `backend/app/main.py` — admit Taobao queued URLs while keeping capture/import restricted to 1688.
- `backend/worker/main.py` — dispatch Taobao with the claimed analysis mode.
- `backend/app/storage.py` — validate source platform/mode and namespace supplier identities throughout atomic completion.
- `backend/tests/test_taobao.py` — URL, parser, fetch, barrier, privacy, identity and dispatch regressions.
- `backend/tests/test_postgres_tracer.py` — product/shop modes, owner polling, replay and cross-platform identity isolation.
- `backend/tests/fixtures/taobao_item_1076425861755.html` — sanitized audited product structure.
- `backend/tests/fixtures/taobao_shop_159450000.html` — sanitized public shop, scoped shelf and 20 observed titles/links.
- `backend/tests/fixtures/taobao-provenance.md` — fixture provenance and exclusions.
- `frontend/apps/web/app/source-url.ts` — canonical safe links and source labels.
- `frontend/apps/web/app/page.tsx` — Taobao submission and source-aware UI text.
- `frontend/apps/web/app/analysis-status.ts` — terminal source/access/safety guidance.
- `frontend/apps/web/app/analysis-status.test.ts` — source and safety guidance assertions.
- `frontend/apps/web/app/extraction-evidence.tsx` — contextual metrics, approximate counts, qualified shop age and safe product collection.
- `frontend/apps/web/app/extraction-evidence.test.tsx` — observable Taobao evidence and link safety assertions.
- `frontend/packages/contracts/src/index.ts` — optional evidence context fields, preserving SupplierData v1.
- `taobao-sample-audit.md` — captured source mappings, identity/URL boundaries and public access observation.
- This plan — approved intent, execution evidence, individual triage rows and contention log.

### Review outcome

All 22 findings are individually recorded above: 15 patched findings grouped into 12 entries (**9 medium, 3 low, 0 high**), 0 deferred and 7 rejected. Rejections: the duplicate-key claim does not establish a mismatched effective identity; six intent observations describe documented capture/live, mock/network, component/journey or supported-layout boundaries without establishing an unmet approved outcome. Each rejection's specific evidence is retained in its triage row.

**Follow-up review recommended: true.** Multiple medium entries were patched. The specific unverified risk is how the corrected verified-evidence access classifier and audited script/shelf selectors behave on unseen Taobao layouts; automated regressions and the two full captures pass, but the corrected code has not had a second independent review. The user requested review of contention after this first round.

### Verification and residual risks

- Full backend: 319 passed / 1 opt-in Azure skipped; isolated PostgreSQL exercises durable queued ownership, replay and platform isolation.
- Full frontend: 54 passed; typecheck, production web/extension build and credential scan passed.
- Manual capture audit: product PARTIAL 6/12; shop PARTIAL 4/12 with 20 titles and safe canonical product URLs.
- Live probe: both supplied public URLs return BLOCKED / ACCESS_CHALLENGE; no anonymous live success is claimed.
- Azure deployment and a browser-to-deployed-worker roundtrip remain unverified. Taobao extension capture/import is outside the approved intent.
- Shared fetching retains the documented OS DNS cancellation limitation; this adapter does not add source cookies or challenge bypass.
- Finalization preserves the user's pre-existing untracked skills/runtime, full samples, PDFs, image and temporary directories. Only the reviewed story files are committed; no remote push.
