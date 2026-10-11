# VCT Connect functionality audit

Date: October 11, 2026 (Asia/Bangkok). Starting revision: `4807d238a070af83897f76d2084397739c37f0c8` (merged Story 6.2). Existing user edits and untracked planning artifacts were preserved. Fixes in this audit are local until explicitly deployed.

## Assessment

The repository contains substantial working implementation through platform, extraction, analysis, reporting and product workflows, plus blind text evaluation/annotation (6.1–6.2). It is not a completed, accepted full MVP or pilot. Built story records describe implementation/review; they do not prove the actual buyer journey, live supplier acquisition, current cloud deployment or production model quality.

The current initiative contains 40 story-plan records marked `built`/`done` (37 built, 3 done), plus one older in-progress statistical-review draft. By epic: platform 7, extraction 8, intelligence 9, reporting 6, product workflows 8, human evaluation 2, pilot 0. These are build-record counts, not 40 independently accepted end-user workflows.

The October 3 development table was stale: it described intelligence/reporting/product workflows as absent even though the current code contains them. An additive October 11 table now distinguishes implementation from acceptance and preserves the historical demo decision.

## Reproduced inconsistencies and remedies

| Finding | Evidence | Remedy |
| --- | --- | --- |
| Guest fixture completes without a report but claims report ready and shows `Preview not found`. | Actual browser → web/API → local PostgreSQL queue → worker; source is the synthetic tracer. `fixture_result` has no normalized supplier data or assessment. | Distinguish tracer completion, skip unavailable report/preview request, explain synthetic evidence. Guest form also accepts supported real source URLs so real guest-preview behavior is reachable. Preserve deployment tracer payload. |
| Saved HTML cannot produce a scored report. | `Store.import_customer_page` persisted synchronous COMPLETED extraction with no assessment work; API always returned COMPLETED. | Successful/partial imports persist snapshot and queue ASSESSING through local queue/Azure outbox in the same transaction; worker resumes saved evidence without recrawling. Invalid/blocked imports remain terminal. |
| Trial allowance differs by submission path. | Normal URL submission used `_customer_quota`, while import/capture/renormalization accepted but ignored `trial_limit`. | Apply the effective active-trial/free quota inside each existing admission transaction; regression checks include trial time boundaries and rejected-work atomics. |
| Source anchors omit actual source content. | Report presentation ignored raw review `text`; supplier evidence stored field markers without normalized values. | Resolve allowlisted supplier values from immutable normalized snapshot and show retained source text/values separately from interpretation; missing data remains unknown. Existing reports are immutable and may still contain old field markers. |
| Reopened report leaves source input pointing at the previous URL. | `openHistoryAnalysis` cleared report state but not URL/file selection; poll synchronized URL only for extension results. | Synchronize source input and clear previous saved-file selection when reopening history/Watchlist or loading status. |
| Reopened extension popup restores link but no progress/verdict. | Restore effect set `lastCapture`; polling required a loaded result; late async writes could survive owner changes. | Automatically load the restored owner-scoped result and guard late responses across owner/request changes. Manual reload remains available. |
| Report route preflight was inconsistent with capture/status routes. | Report GET proxy lacked explicit stable-extension OPTIONS handler. | Add the existing allowed-origin preflight pattern; this consistency fix alone does not establish real Chrome CORS/session compatibility. |

## Verification evidence

Before fixes, the suite without a configured PostgreSQL test database reported **855 passed, 127 skipped**. Frontend reported **107 passed**, and TypeScript checking passed. This exposed a verification gap: a green default local run was skipping persistent database behavior.

A dedicated local PostgreSQL database, `vct_progress_audit`, was created separately from the application database. The baseline full suite with that database reported **950 passed, 32 skipped**, in 364.46 seconds. Remaining baseline skips were live browser/Azure checks. Deterministic test providers are used for worker assessment; no live YEScale call was claimed.

Actual local runtime was initially stopped. The existing Docker PostgreSQL service was started, ordered migrations applied to the local app database, and web/API/worker started with a process-local `QUEUE_TRANSPORT=local` override. Root `.env` was not changed. API `/healthz` returned 200. The real browser loaded the signed-out landing page and reproduced the fixture inconsistency above.

Post-fix full PostgreSQL-backed backend verification passed **970 tests, 32 skipped**, in 359.52 seconds, before review patches. The skips remain live browser/Azure checks. Implementation checks passed **113 frontend tests**, TypeScript checking and targeted database/report tests. Post-review frontend verification passed **124 tests** and TypeScript checking. Both web and Chrome-extension production builds passed. The web and extension configured-server-secret scans passed, and `docker compose config --quiet` and `git diff --check` passed. The final post-review full PostgreSQL suite passed **974 tests, 32 skipped**, in 348.22 seconds. One existing Starlette test-client deprecation warning was non-blocking.

With the human signed into the app browser, actual Clerk authentication succeeded against the local API. Account shows CUSTOMER, Free, inactive/unallocated trial and persisted usage. An authenticated tracer completed with explicit no-risk/no-report wording. History loaded 18 persisted records including the new tracer; reopening an existing saved-source entry synchronized the input URL, and a browser refresh reopened its authorized analysis by query ID. Its older extraction-only result explained that no assessment report was stored.

The authenticated saved-HTML form accepted the repository 1688 sample and handed it to assessment. Without the configured provider key it retried and reached bounded FAILED_FINAL with sanitized PROCESSING_ERROR, rather than inventing a report. This verifies submission/handoff/failure handling, **not** a live report, Watchlist round trip or evidence browsing. Those remain gated on provider configuration. No credential was entered or copied by the agent.

The post-review production web build was inspected in the same real Clerk session. History retained 19 entries including the failed import; reopening the historical extraction-only entry showed the correct source and no longer marked assessment/report complete. An existing pending history analysis kept a newly typed Taobao URL through multiple real status polls; no new submission was made for this check. Watchlist correctly rendered its empty server state; account usage increased from 0/20 to 2/20 for the two authenticated submissions. Add/remove/deduplication still needs a completed report for browser acceptance. A saved browser screenshot is at `tmp/progress-audit-final-browser.jpg`. The mounted frontend tests execute actual Page/Popup wiring with mocked identity, HTTP and Chrome boundaries; they complement, rather than replace, real browser/Chrome acceptance.

Four independent review lenses (blind, edge cases, verification gaps, intent alignment) were triaged individually in the build plan. Findings were remedied, including single-attempt budgets for both import and capture, pending-report copy, polling URL edits, guest registration expectations and unknown saved-page capture age. Database regression covers local and mocked Azure assessment/report/replay without a recrawl or repeated model calls. No live provider/cloud/Chrome gate was converted to a pass.

## Remaining release gates

- The key was absent during the initial inspection. After operator configuration and explicit approval, the historical 1688 sample passed real YEScale assessment/report acceptance; see the follow-up below. Fresh public-source, Chrome and cloud acceptance remain pending.
- Historical Azure guest-tracer deployment smoke checks queue plumbing, not assessment, report evidence, history/Watchlist or signed-in acceptance. This audit does not redeploy cloud resources or claim current live parity.
- Live source challenges are explicit terminal extraction outcomes, not scored-report success. Repeat accessible-source checks across all three platforms; Alibaba has no import/capture recovery path.
- Browser fallback remains disabled in Azure pending the documented compatible runtime. The standard worker has optional tested media contracts but no production source-media acquisition/retention/deletion path.
- Real Chrome/Clerk sync, capture, popup reopening, account switching and report viewing must pass on the target build; automated helper tests do not replace that gate.
- New users are Free unless a trial entitlement is granted; allocation/dates are product/operator choices. Expiry and no automatic charging are implemented, but a universal automatic trial is not a claim.
- Human evaluation beyond 6.1/6.2 remains pending: private media review, double review/adjudication, supplier labels, metrics and model benchmark.
- Pilot recruitment, source/privacy/budget gates, representative latency/cost/load measurements, 100-user/500–1,000-URL/return-use targets and upgrade intent are unvalidated. No completed pilot plans exist in this checkout.
- An older untracked in-progress statistical-review plan coexists with later built review plans. It was preserved; resolve ticket/draft reconciliation separately without treating it as a code-completion signal.

Web/API remain running on ports 3000/8000. The audit worker was stopped after verification so the next worker can load the operator-selected model configuration; start it using the guide. PostgreSQL remains running. A dedicated test database is retained for repeatable regression checks.

## End-user test

Use [END_USER_TEST.md](../../END_USER_TEST.md). The shortest meaningful buyer acceptance is signed-in saved evidence → assessment/report → source inspection → persisted history → Watchlist deduplication/removal → second-account isolation. A synthetic tracer pass alone is not that acceptance.

## Live provider follow-up — October 11, 2026

The operator configured YEScale with `deepseek-v4.1-flash` and explicitly approved sending the saved repository 1688 sample to `https://api.yescale.io`. The initial model used all 1,800 output tokens for reasoning and returned no answer. DeepSeek V4 structured text/media requests now disable thinking, including provider-prefixed model names, with the chosen setting preserved in model provenance. Supplier prompt v2 asks for concise Vietnamese JSON and explicitly lists permissible evidence reference fields. The schema and token limit remain enforced.

Analysis `1591350c-8239-4945-ad1c-f85ecde61f9e` completed through the actual worker assessment/report functions. Earlier attempts included invalid/truncated model output and a transient provider connection failure. The successful model run returned `finish_reason=stop`, 1,074 prompt tokens, 875 completion tokens and 5,182ms provider latency. It persisted `thinking.type=disabled` and `supplier-interpretation.prompt.v2`. The report correctly has no overall risk score, `INSUFFICIENT_INFORMATION`, confidence 0.475 and coverage 0.5; the UI rounds confidence to 48%.

Browser acceptance verified the Vietnamese report, source rating reference and retained source values, unknown saved-page capture age, Watchlist save/reopen/deduplication and report persistence after refresh. History lists the completed report. Reopening the same analysis exposed a frontend polling dependency bug: the open handler cleared state without changing the ID, so a previously stopped poll did not restart. A reopen generation now triggers a fresh lookup for History/Watchlist, with two mounted component regressions.

Follow-up checks: 39 adapter/interpretation tests, 52 assessment/report/scoring tests and seven PostgreSQL worker tests passed; 126 frontend tests and TypeScript checking passed. Quick independent review found no code issues. Watchlist removal, second-account browser isolation, real Chrome extension, fresh live sources and cloud deployment remain separate gates. Only the approved sample was processed; the continuous worker remains stopped so unrelated queued historical analyses are not sent to the provider.

### Continuous worker and operator extension capture

After explicit operator approval of queued and newly submitted supplier evidence processing through YEScale, the continuous local worker was started. Extension analysis `37c466a0-037d-4c53-bd13-2b9e3d5fb464` had waited unclaimed with zero attempts since capture at 04:39 UTC; this was an absent worker, not a long-running model call. It completed on the first worker attempt with no failure code. The authenticated web report loaded with `INSUFFICIENT_INFORMATION`, no overall risk score, 44% displayed confidence and 50% coverage. The continuous worker remains running. This verifies the operator-submitted capture's server assessment/report path; full Chrome popup, account-switching and source coverage gates still require separate checks.

### Expanded 1688 capture follow-up

Operator analysis `75cb5a08-3ecf-4706-a495-6b062863692a` for offer `1027322610455` completed but retained only supplier name, product title and an unqualified coupon price. Its saved DOM contains considerably more selected visible evidence. The extension now captures bounded supplier tenure/business and metrics, up to 50 attributes, SKU price/stock, qualified price components, shipping, dropshipping metrics and product rating/reviews. Strict normalization advances to `1688-extension-dom.v2`; approximate counts and metric scopes remain literal, and tenure/shipping/stock do not become founding age/headquarters/capacity.

The sanitized saved-page browser regression retains 41 attributes (including the 400g title versus 300g–350g specification conflict), four supplier and nine dropshipping metrics, both qualified prices, SKU stock, shipping, product rating 4.6, 40+ review display and one review. Payload size is 3,851 bytes; normalized source completeness is 75%, with founding age, certifications and activity history still unknown. This is extraction completeness, not scored risk coverage.

The subsequent operator-supplied review drawer exposed ten loaded cards missing from complete-page saving. The extension now prefers the visible drawer, retains repeated cards and falls back to inline reviews when closed. Independent review also found repeated-card loss during recapture merging; 1688 merging now retains maximum observed multiplicity rather than summing recaptures or collapsing repeated text. Ten fixture reviews survive normalization, merge and assessment preparation, excluding buyer identities. Validation passed: 131 frontend tests, 170 backend tests, two PostgreSQL extension checks, TypeScript, extension build and 17 browser fixture checks. Pagination and review media capture/vision remain unconnected; fresh Chrome recapture is still an operator gate.

Validation: 164 backend and 129 frontend tests, TypeScript, extension build, two PostgreSQL extension tests and 14 real-browser fixture checks passed. Independent review found no actionable issues. API and continuous worker restarted; extension build ready for Chrome reload. Fresh Chrome recapture remains pending and old reports retain their original evidence. The end-user guide now includes the exact retest steps.
