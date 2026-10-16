---
title: Temporarily pause Taobao extraction
type: feature
created: 2026-10-16
status: built
route: full
route_source: auto
review: thorough
review_source: auto
lenses_ran: [blind-hunter, edge-case-hunter, verification-gap, intent-alignment]
baseline_revision: f5fb5ea2e7f63c0fb35360c4c867d8dec14483b5
context: []
---

<frozen-after-approval reason="user-requested temporary disablement">

## Intent

User request: “next, could you get rid of the taobao path for now? the extraction doesn't work due to captcha preventing logins”.

Pause new Taobao extraction across the customer-facing application. Offer 1688 and Alibaba in the guide and extension; make Taobao pages clearly unavailable for new capture. Retain existing Taobao reports, historical evidence and parser code so the pause is reversible. Existing session authorizes release to the live app.

## Boundaries & Constraints

Always reject new Taobao customer/guest URL submissions, saved-HTML imports and selected browser captures before quota-consuming storage or queue work. Existing report/history/watchlist reads must remain compatible. Explain the temporary pause in Vietnamese/English where a user encounters a Taobao page or old failure report.

Never delete old data, remove the TAOBAO contract enum, dismantle retained parsers/normalizers, solve CAPTCHAs, or modify unrelated dirty files. Do not change 1688/Alibaba capture behavior. No model calls or new supplier analyses are required to validate this change.

## I/O & Edge-Case Matrix

| Input/state | Expected behavior |
| --- | --- |
| Signed-in or guest new Taobao URL | 422 with explicit temporary-unavailability detail; zero analysis/outbox/admission writes |
| Taobao saved HTML or browser JSON | 422 before parsing/storing evidence; old extension cannot bypass pause |
| Extension on Taobao product/shop/login page | Pause notice, no Analyze action, no capture/upload |
| Extension on 1688/Alibaba supported pages | Normal product/company guided capture remains available |
| Existing Taobao analysis/report/history/watchlist | Still readable for the owning user; ownership checks remain |
| Web landing/download guide | Lists 1688 and Alibaba only; no Taobao instructions or active tab |
| Old Taobao failure report | Explains pause rather than suggesting another Taobao capture/import |

</frozen-after-approval>

## Code Map

- `backend/app/main.py`: `Submission.supported_offer` validates both customer/guest POST URLs; `import_saved_page` and `capture_browser_evidence` are the other admission boundaries. Reject Taobao using a shared message without changing URL normalization used by historical reads/replay. Collection API bundles already support only 1688/Alibaba.
- `backend/tests/test_auth.py`: first Taobao upload/capture success cases must become pause-before-admission tests; unsafe-text/deep-nesting test should use supported 1688 data to keep testing its actual guard. FakeStore gives counters/rows for side effects. Add seeded legacy read/ownership regression evidence.
- `backend/tests/test_taobao.py`: canonicalization test currently also admits via Submission; retain canonicalization and parser checks, replace only Taobao admission assertion.
- `frontend/apps/extension/src/capture.ts`: `supportedOffer` is the live admission parser; stop returning Taobao product/shop there. Retain `captureSelectedDom` Taobao logic and types as inactive adapters for future restoration and offline tests.
- `frontend/apps/extension/src/extension-shell.ts`, `popup.tsx`, `ui-language.ts`: classify Taobao host pages as temporarily paused, gate capture actions, provide localized notice. Keep account/result viewing usable; do not remove last report access. `background.ts` already validates product kind and must stay unable to start Taobao collection.
- `frontend/apps/extension/src/capture.test.ts`, `extension-shell.test.ts`, `popup.interaction.test.mjs`: assert paused page admission and no action/upload while retaining offline adapter tests and active-source regressions.
- `frontend/apps/web/app/extension-guide.tsx`, `page.tsx`: remove Taobao guide tab/steps and supported-platform marketing copy; update guide tests. `analysis-status.ts`/tests: preserve success display but replace failed-Taobao recovery with pause notice. `extraction-evidence` and source link normalizers remain historical-display compatible.
- `frontend/apps/extension/build.mjs`: publish extension 0.7.1, description only 1688/Alibaba, same identity/icon/origin. `scripts/verify_web_extension_download.py` must check 0.7.1. `END_USER_TEST.md`, extension README and main README: current support is two platforms, with historical technical notes clearly superseded rather than a giant documentation rewrite.

## Tasks & Acceptance

- Add the backend admission pause and tests at each HTTP boundary. Given a Taobao source, when submitted with valid identity, then it fails before quota/evidence storage. Given stored Taobao evidence, when opened by its owner, then it remains readable; foreign access stays denied.
- Remove live extension admission and guidance. Given a Taobao page, when opening the popup, then it explains the pause with no Analyze button. Given 1688/Alibaba, when classified and captured, then existing guided behavior remains.
- Update web guide, landing, recovery and version metadata. Given the signed-in guide, when choosing a platform, then only 1688/Alibaba are offered. Given a legacy failed Taobao report, then guidance offers no new Taobao extraction. Given a downloadable ZIP, then its version is 0.7.1 with stable identity and live origin.
- Run focused tests, then full frontend/backend checks and typecheck/build/secret scan. Review the exact task diff. Parent handles explicit-file commit, isolated live-main PR, CI/merge/deploy and live verification. Implementation agent must not commit, push or run remote operations.

## Implementation Notes

Task is authorized directly by the user; proceed without another planning approval. Preserve the two dirty initiative documents and untracked local samples. Implement in the main workspace; the parent transfers only the task commit into an isolated release worktree.

The implementation delegate completed the initial gates but then failed on a transient gateway/DNS error. The parent finished tests, compatibility repairs and verification. Historical result restoration now has its own narrow Taobao URL allowance, separate from new-source admission. A pending 1688/Alibaba collection may still finish its stored upload on a paused tab; no new Taobao capture is exposed. Backend parsers, shared platform contracts and persisted data remain intact.

## Verification

Run `npm test --prefix frontend`, `npm run typecheck --prefix frontend`, production web build and `scripts/scan_frontend_secrets.py`. Run backend authentication and Taobao tests, then full backend suite as appropriate; CI supplies PostgreSQL/container checks. Verify actual production standalone/image download with `scripts/verify_web_extension_download.py`. Inspect signed-in guide and Taobao popup in mounted/browser tests. Verify live bundle omits Taobao capture instructions and old API clients receive rejection. No new real analysis is submitted.

## Review Triage Log

| Finding | Verdict and evidence | Action |
| --- | --- | --- |
| Blind 1: pending active collection hidden on paused tab | Medium, patch: finish/retry uses already stored 1688/Alibaba evidence and requires no capture of current tab. Hiding it regressed recovery. | Restore controls with explanatory copy; mounted cases cover all three pending stages and only FINISH_GUIDED. |
| Blind 2: null legacy extraction status offered new analysis | Medium, patch: blocked presentation fell back to generic recapture guidance. | Apply pause to fallback; full presentation regression added. |
| Blind 3: unsafe historical failure loses explanation | Low, patch: raw reason remains, but useful readable distinction was removed. | Retain unsafe destination/source explanation before pause notice. |
| Blind 4: guide assertion forbids pause explanation | False: user requested removal of this offered path; the guide deliberately offers two platforms. Popup and historical reports explicitly explain pause. No requirement for a third platform mention in the primary guide. | Keep two-platform guide assertion. |
| Blind 5: historical URL regex accepts trailing newline | Low, patch: JavaScript dollar anchor permits a terminal newline. | Require trim equality, test four line terminators for product/shop. |
| Blind 6: no mounted saved Taobao popup restoration | Medium verification gap, patch: unit restore alone does not establish UI access. | Add paused-tab restore/reload/open/owner-switch test. |
| Blind 7: legacy guest preview missing regression | Medium verification gap, patch: new submissions pause must not affect old guest reads. | Parameterize browser-scoped preview test with seeded legacy Taobao and foreign-key denial. |
| Blind 8: old version and current documentation conflict | Low, patch: Alibaba walkthrough still requested 0.7.0. | Current walkthrough/extension README say 0.7.1; remove active Taobao assertions and obsolete web import instructions from extension README. Historic acceptance sections remain under explicit top-level supersession notice. |
| Edge lens | No findings. | No patch. |
| Verification: missing restored collection case, proposed hiding controls | Medium test gap, patch; absence expectation rejected as false: uploading a valid stored 1688/Alibaba collection never admits Taobao and must preserve active-source behavior. | Added combined paused-tab/pending-stage tests asserting no new capture and retained finish/retry. |
| Intent lens | No implementation defect: temporary admission/UI pause matches request. It does not delete adapters or cancel already running work. | Preserve legacy data and in-flight behavior; no new marketplace request. |

No product changes deferred. Review fixes were applied by the parent because the implementation agent could not continue.

## Verified local result

181 frontend tests passed. Full backend suite: 1052 passed, 166 skipped for environment-gated PostgreSQL/container checks; targeted auth/Taobao suite: 192 passed. Workspace typecheck and production build passed. Actual standalone protected-download verification confirmed extension 0.7.1, six-file CRC integrity, stable ID, live origin and private-only access. Local desktop/mobile guide and actual browser ZIP saving passed against fixture authentication. Source bundle/ZIP secret scan passed. The ignored local build-live folder is also refreshed to 0.7.1. CI will execute the environment-gated checks before release.
