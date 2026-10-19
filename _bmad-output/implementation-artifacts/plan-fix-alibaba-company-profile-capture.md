---
title: Fix Alibaba company profile capture on capability-card layouts
type: bugfix
ticket: ''
created: 2026-10-19
status: built
route: full
route_source: auto
review: thorough
review_source: auto
lenses_ran: [blind-hunter, edge-case-hunter, verification-gap, intent-alignment]
review_loop_iteration: 0
baseline_revision: 329432480b05b86dafb4fd72038a95262d10589a
context: []
---

<frozen-after-approval reason="user directly requested implementation and live release">

## Intent

The Alibaba third capture step, Save company HTML & analyze, fails on the user's Guangzhou Lianxian television supplier profile. Fix that capture so the visible company evidence joins the existing product/storefront collection and reaches its report, then release the verified fix to the live app and downloadable extension.

## Boundaries & Constraints

Always preserve source identity, company-name matching, visible-public-region capture, bounded claims/HTML, one quota reservation, 30-minute guided capture, stored-upload retries and 1688/legacy Alibaba compatibility. Map displayed label aliases to the existing canonical company fields, retaining units and uncertainty. Keep DOM-selected claims and cleaned HTML identical.

Never read source scripts/globals/module-data, account state, contact widgets, hidden content, recommended products, or industry-average metrics as company facts. Do not solve CAPTCHA, weaken matching to accept another supplier, invent establishment years from membership tenure, change historical reports, or touch unrelated dirty initiative files. No external LLM replay is needed.

## I/O & Edge-Case Matrix

| Scenario | Input/state | Expected behavior |
| --- | --- | --- |
| New profile | Saved gzlianxian capability-card profile with visible company name, Custom Manufacturer, two production lines and floor space 5000 square metres | Nonempty canonical profile selection and matching cleaned HTML; profile step finishes same collection |
| Existing profile | Yiheng table-based profile | Existing 15 claims, source identities and captures remain compatible |
| Visibility/scope | Hidden duplicate claims, recommendations and supplier-vs-industry comparisons | Only visible company-owned supported fields captured; comparison averages excluded |
| Invalid source | Foreign supplier/canonical, conflicting visible company names or claims | Reject; preserve pending capture so user can retry |
| Missing data | No usable visible profile claims or loading/challenge-only page | Actionable retry; no finalization or claimed successful download/upload |
| Transport/recovery | Valid product/store/profile and a lost finish response | One reservation, all three HTML sources, same analysis ID and retry of exact saved evidence |

</frozen-after-approval>

## Code Map

- `frontend/apps/extension/src/alibaba-capture.ts`: current FACTORY mode and HTML capture require old `tr .field-title,tr.icbu-shop-table-col-item td.title` labels. New page still has `.cp-name` but no matching table rows, so FACTORY returns null before upload. Keep old table support; add narrowly scoped capability-card label/value capture and `.company-type .business-type` under the supplier header. Use the same alias/value rules in selected evidence and rebuilt HTML.
- Saved input: `sample webpages/alibaba/Company Profile.html`, actual source `https://gzlianxian.en.alibaba.com/company_profile.html`. This saved document contains private source state: do not print attributes or commit the raw document. A sanitized inspection copy exists at `tmp/gzlianxian-inert-inspection.html` with scripts/forms/globals/module-data removed. Public modern content is inside `#fresh-shop-content`; manufacturer cards contain adjacent span labels `Number of production line` -> `2` and `Floor space(㎡)` -> `5000`. Supplier header `.cp-name` is `Guangzhou Lianxian Electronic Technology Co., Ltd.` and visible `.business-type` is `Custom Manufacturer`. Header popup data is hidden. Compare panels and product recommendations must not become facts.
- `backend/app/extraction/alibaba_browser.py`: canonical allowlist already supports `Business type`, `Factory Size`, `No. of Production Lines` and other company labels. Exact selected/HTML equality and source/company checks remain. Prefer no backend public contract expansion; add regression evidence verifying normalized company fields and factory evidence.
- `frontend/apps/extension/src/background.ts` / `background.test.mjs`: existing CONTINUE_GUIDED captures matching FACTORY, downloads `company.html`, finishes once and retains retry payload. Do not rewrite reservation protocol.
- `frontend/apps/extension/src/*test*`, `backend/tests/test_alibaba_browser.py`: add real-structure fixtures and meaningful extraction/visibility/conflict tests, ensuring registration in `frontend/package.json` when adding a new test file. Existing Yiheng bundle fixture remains unchanged.
- `frontend/apps/extension/build.mjs`, `scripts/verify_web_extension_download.py`, README/current end-user guidance: publish extension 0.7.2 with stable ID, icon, live origin, permissions and authentication.

## Tasks & Acceptance

- [x] Reproduce FACTORY=null with the saved new layout and record the exact cause before patching.
- [x] Implement safe capability-card extraction with canonical labels/units, identical HTML and preserved table behavior.
- [x] Add regression coverage for every matrix row, including normalized profile facts reaching factory assessment and continued guided completion/retry.
- [x] Bump extension to 0.7.2 and adjust relevant package assertions/current documentation.
- [x] Run focused tests and actual offline Chromium against the sanitized saved page; parent runs full checks, reviews, commit, isolated PR, CI and deployment.

Acceptance: Given the new profile belonging to the captured product supplier, when the buyer saves company HTML, then cleaned company evidence downloads/uploads and assessment starts under the same analysis ID. Given an existing supported collection, when this patch is installed, then collection identity and result restoration remain unchanged. Given an invalid or empty profile, when capture is attempted, then the pending collection remains retryable.

## Implementation Notes

Baseline reproduction in offline Chromium: FACTORY returned null despite one visible `.cp-name` and production/floor-area cards; old table selector count was 0. The capture rejected the profile at its empty-claims guard before HTML upload.

User explicitly requested fixing and releasing this issue. No additional planning approval is needed. Preserve the two dirty initiative documents. Implementer must not commit, push, run remote operations or modify the saved raw sample. Parent handles release. Native signed-in source navigation may remain a user acceptance check; offline actual injected capture must reproduce the supplied layout and validate its server-side output.

## Plan Change Log

- Implemented capture rules in both independently serialized functions using the public `factoryCapability` semantic root and adjacent values in the Production card. The supplier header supplies Business type; duplicate values coalesce and conflicting values reject capture. Floor-space values retain their displayed square-metre unit.
- Added an Alibaba company-name check before profile download/finalization. Server-only rejection previously left a mismatched name in a saved FINISHING payload; early rejection preserves the retryable pending collection. Reservation/replay protocol is unchanged.

## Review Triage Log

The first reviewer attempts hit a temporary usage limit; the resumed reviewers completed all four lenses. Blind/edge/verification ran together; intent followed as a slot became available.

| Finding | Verdict and route | Evidence / action |
| --- | --- | --- |
| Blind 1: unavailable area gains manufacturing evidence | Medium, patch | Modern N/A becomes a nonempty area claim; reject placeholder/nonpositive area values. |
| Blind 2: equivalent measurements conflict | Medium, patch | Thousands separators and equivalent square-metre units should not reject the same supplier fact; compare normalized bounded values and retain display text. |
| Blind 3: multiple declared manufacturer/trader badges conflict | Medium, patch | Both roles are compatible; combine explicit header badges before checking table equality. |
| Blind 4: header-only loading profile succeeds | Medium, patch | Header claim must supplement a usable loaded profile body, not turn an empty body into a complete profile. |
| Blind 5: unrelated legacy table contaminates claims | Medium, patch | Bind legacy selectors to saved CompanyOverview/ProductionCapacity/TradeCapability roots. |
| Blind 6: hydration changes between selection and HTML poison finish retry | Medium, patch | HTML injection validates the selected company/claims before download or finalization; mismatch stays retryable. |
| Blind 7: no persistent real-browser source-layout test | Medium, patch | Added sanitized public source-layout HTML and CI case executing serialized capture functions in the existing network-denied Chromium container. |
| Blind 8: numeric truncation alters area evidence | Medium, patch | Drop oversized measurements instead of clipping them into a different quantity. |
| Edge 1: missing/zero area becomes evidence | Medium, patch | Same root cause as Blind 1; exclude rather than add units. |
| Edge 2: explicit square feet receive metre suffix | Medium, patch | Add label units only to complete bare numeric values; keep explicit units unchanged. |
| Edge 3: equivalent m²/table measurement conflicts | Medium, patch | Same root cause as Blind 2. |
| Verification 1: product-name guard untested without a shop capture | Medium, patch | Add direct-profile matching/mismatch/correction cases, retaining one reservation and pending state. |
| Verification 2: comma-spacing compatibility untested | Medium, patch | Retain visible legacy header plus table declaration in compatibility regression. |
| Intent 1: actual page vs DOM double | Verification boundary, patch | Persisted source-layout fixture and mandatory actual Chromium case complement the saved full-page replay. |
| Intent 2: mocked collection vs native installed extension | Verification boundary | Native signed-in Alibaba navigation remains an explicit end-user acceptance check; source capture, same-ID retry and server contracts are separately exercised. |
| Intent 3: normalized facts vs delivered report | Verification boundary, patch | Parameterized the existing collection/report PostgreSQL integration for both table and capability fixtures; it checks one reservation/report, owned persistence and sourced production-line evidence. CI executes it against PostgreSQL. |
| Intent 4: prepared release vs delivered release | Pending release verification | Parent completes PR, CI, rollout and packaged-version verification before reporting live. |
| Intent 5: acceptance instructions vs demonstrated browser journey | Verification boundary | Final report distinguishes saved-layout/fixture checks from native account navigation. |

## Verification

Run focused new/old Alibaba DOM, background and backend bundle tests; all frontend tests, typecheck, production build, client/archive secret scan and full backend checks. Use offline Chromium with blocked external requests for the saved profile plus legacy Yiheng. Verify emitted HTML equals selected facts, contains no source/private state, normalizes production lines=2 and area with units, and supplies factory evidence. CI must pass actual browser/PostgreSQL/image/infrastructure checks. After deployment confirm new ready images, public app/guide and protected version 0.7.2 package; retain honest distinction between fixture verification and native signed-in acceptance.


### Implementer focused verification (2026-10-19)

- Frontend: `node --import tsx --test apps/extension/src/alibaba-capture.test.ts apps/extension/src/capture.test.ts apps/extension/src/background.test.mjs` from frontend: **46 passed**, no skips. New file is registered in `frontend/package.json`.
- Backend: `.venv/Scripts/python.exe -m pytest backend/tests/test_alibaba_browser.py backend/tests/test_supplier_bundle.py -q -p no:cacheprovider`: **69 passed**. Actual browser profile output is the new public-only regression fixture; product/store envelope in its normalization test is explicitly synthetic.
- `npm run typecheck`: passed. `git diff --check`: passed.
- Offline actual Chromium with all external requests blocked: saved capability profile produces exactly Business type=Custom Manufacturer, No. of Production Lines=2, Factory Size=5000 square metres; cleaned HTML=591 bytes and its three rows equal selected claims. Legacy saved Yiheng product/store/profile captures still succeed, retain 15 selected profile claims identical to the unchanged existing fixture, and emit matching HTML claims. Local evidence: `tmp/gzlianxian-profile-capture.json`, `tmp/alibaba-guided-captures.json`; parent independently confirmed in `tmp/gzlianxian-current-capture.json`.
- Matrix audit: new profile + legacy profile are covered by DOM and backend tests; visibility/scope by hidden duplicate/header/contact/recommendation/comparison DOM cases; invalid identities/names/claims by DOM, backend and retryable background cases; missing/loading/challenge data by DOM plus failed profile/HTML background cases; transport/recovery by the new Alibaba three-source response-loss replay test (same ID, one reservation, same saved bytes, company.html download, 30-minute session).
- Parent remains responsible for full tests/build, secret scans, review, isolated PR/CI and release. Native signed-in source acceptance remains an end-user check. No commit, push or remote operations performed; raw saved source and the two dirty initiative documents were not modified.

### Parent verification

Full frontend suite: 189 passed. Full backend suite: 1059 passed, 166 environment-gated skips. Workspace typecheck passed. Independent offline replay of the saved full page and backend normalization retained the three profile facts, all three PARSED source records and four manufacturing evidence records. Production build, package checks and independent review continue before release.

### Reviewed final result

All actionable review findings were patched; none deferred. Selected claims and HTML now reject incomplete/invalid measurements, preserve explicit units, coalesce equivalent quantities and explicit manufacturer/trader roles, require loaded profile content, and remain retryable when page hydration changes facts between injections. Legacy tables are bound to their company-profile modules. Added direct-profile name checks, visible header/table compatibility and a persistent public source-layout fixture. The CI Chromium container executes exported current extension functions against that fixture; its changed-HTML assertion is mandatory. The existing PostgreSQL owned-report test now runs both Alibaba layouts.

Final local checks: 198 frontend tests passed; 1059 backend tests passed with 168 environment-gated skips; the new actual Chromium test passed separately with installed Chrome. Typecheck and final production build passed. Replayed original saved Yiheng product/store/profile with the final code: 15 claims retained. Independent follow-up review found no issues in the browser fixture/export/CI mount or parameterized report test. Raw source/private state and unrelated initiative documents were excluded. CI, deployment and live package checks remain the release gate.
