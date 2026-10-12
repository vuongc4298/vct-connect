---
title: 'Verify actual buyer workflows and remedy completion inconsistencies'
type: bugfix
ticket: ''
created: '2026-10-11'
status: built
route: full
route_source: auto
review: thorough
review_source: auto
lenses_ran: [blind-hunter, edge-case-hunter, verification-gap, intent-alignment]
review_loop_iteration: 0
baseline_revision: '4807d238a070af83897f76d2084397739c37f0c8'
context: []
---

<frozen-after-approval reason="user authorized auditing and remedying inconsistencies in the original request">

## Intent

**Problem:** Built BMAD records do not establish successful end-user usage. Saved HTML cannot reach assessment/reporting; enhanced paths ignore trial quotas; evidence anchors omit source values; reopening a supplier can leave the input pointing elsewhere; the extension does not load its restored result.

**Approach:** Correct these reachable integration gaps, verify the real database and browser where available, and produce an honest current-status record and an end-user acceptance guide. The original request authorizes reversible fixes; preserve unrelated existing edits.

## Boundaries & Constraints

**Always:** Preserve owner/guest authorization, privacy, source provenance, immutable reports, queue replay, trial expiry and no-charge semantics. Keep synthetic tracer evidence explicitly synthetic. Distinguish implemented, automated-tested, browser-verified and live deployed acceptance.

**Never:** Invent live supplier scores, weaken Clerk authentication, transmit secrets, invoke paid live models without configured credentials, alter cloud infrastructure, overwrite existing planning notes, claim pilot/evaluation completion beyond built stories, or push remotely.

## I/O & Edge-Case Matrix

| Scenario | Expected behavior |
| --- | --- |
| Successful/partial saved HTML | Persist snapshot and local queue/Azure outbox atomically; return ASSESSING; worker resumes stored evidence and persists report without recrawling. |
| Blocked/invalid saved evidence | Remain terminal extraction-only with explicit recovery; create no assessment work. |
| Active versus expired/future trial | All customer admissions use the same effective quota; rejected admissions leave no rows/work. |
| Source evidence | Raw review text and supported normalized supplier field values are inspectable; absent values remain unknown. |
| Reopen history/Watchlist | Source input matches the reopened analysis and clears any previous file selection. |
| Reopen extension popup | Automatically load current owner's last result; async responses cannot restore another owner's report. |
| Legacy tracer/blocked guest result | Explain that no scored report/preview exists; avoid a misleading report-ready state or raw 404 as the only outcome. |

</frozen-after-approval>

## Code Map

- `backend/app/storage.py`: URL admission uses `_customer_quota`; import/capture/renormalize currently ignore `trial_limit`. Capture already persists then queues assessment; reuse that pattern for import.
- `backend/app/main.py`: import returns COMPLETED and does not pass queue transport. Preserve upload validation; return actual handoff state.
- `backend/worker/main.py`, `backend/app/intelligence/worker_assessment.py`: stored assessment-phase replay is established. Legacy FIXTURE_URL is deliberately only a tracer and must retain its smoke contract.
- `backend/app/reporting/builder.py`, `backend/app/intelligence/assessment_policy.py`: supplier evidence carries field markers; resolve only allowlisted source fields from immutable normalized snapshot when building report.
- `frontend/apps/web/app/report-presentation.ts`, `full-report.tsx`: evidence cards discard review text/value; render source content without conflating interpretation.
- `frontend/apps/web/app/page.tsx`: history/status reopening fails to synchronize non-extension source URL; guest landing always submits tracer but asks for a report-backed preview.
- `frontend/apps/extension/src/popup.tsx`: restore effect sets link only; `loadResult` has unguarded async updates. Shared client/owner restoration contracts already exist.
- `frontend/apps/web/app/api/v1/analyses/[analysisId]/report/route.ts`: compare preflight handling to status route before deciding a minimal consistency fix.
- Existing tests: `backend/tests/test_postgres_tracer.py`, `test_auth.py`, `test_worker_assessment_postgres.py`, `test_reporting.py`; frontend component/helper/client suites.

## Tasks & Acceptance

**Execution:**
- [x] Backend storage/API/tests: fix saved HTML handoff and effective quotas; preserve failure atomics/replay.
- [x] Backend builder/frontend report/tests: show retained source evidence values and review text.
- [x] Web page/extension/tests: correct reopening state, honest tracer/guest completion, and owner-safe restored result loading.
- [x] Root agent: record audit evidence, refresh status documentation additively, update setup/extension docs, and write `END_USER_TEST.md` with concrete buttons, URLs, files, expected outcomes and blocked acceptance gates.

**Acceptance Criteria:**
- Given saved supported HTML, when imported, then its stored snapshot reaches an authorized immutable report via the configured queue; a blocked import remains extraction-only.
- Given an active, expired or future trial, when any customer admission runs, then quota agrees with account state and failed admission creates no analysis/queue work.
- Given source evidence in a report, when a buyer inspects its source card, then source text/values remain visible separately from interpretation and absent source data is labeled unknown.
- Given reopened history/Watchlist/extension results, when displayed, then IDs, input URLs, evidence files and owner scope refer to the same analysis.
- Given the default synthetic tracer, when it completes, then the web clearly identifies a tracer completion without claiming a real report is ready.
- Given unfinished live/provider/cloud/pilot gates, when reading updated documentation, then their unverified state and repeatable acceptance steps are explicit.

## Implementation Notes

Root clarified during implementation that the guest landing form must accept a supported source URL so report-backed previews are reachable; its default tracer remains available and extraction-only completion must explain that no scored preview exists.

Baseline: 855 backend tests passed, 127 skipped without PostgreSQL/live flags; 107 frontend tests passed; typecheck passed. Local app and Docker database were stopped. Dedicated database `vct_progress_audit` created for database checks. Local YEScale configuration is absent. Root handles environment/browser verification and documentation; implementation subagent owns application code and regression tests only, and must not commit/stage or run database tests concurrently with root baseline checks.

## Plan Change Log

## Review Triage Log

Each independently filed finding is retained here, including duplicates. Review snapshot preceded final verification documentation.

| Finding | Verdict | Evidence and route |
| --- | --- | --- |
| Blind 1: worker environment instructions omit model key | medium | README step 3 explicitly excluded worker loading and claimed queue/database sufficient. Correct setup wording; patch by root. |
| Blind 2: pending real guest labeled tracer | low | Landing passes null requestedMethod and ProgressCard defaults to tracer before first response. Record submitted method; patch. |
| Blind 3: guest registration implies report transfer | medium | CTA promises full report while ownership has no guest-to-user transfer. Explain authenticated resubmission; patch copy. |
| Blind 4: saved evidence appears freshly captured | medium | Imported normalized extracted_at records processing time; FullReport freshness treats it as source capture. Known USER_UPLOAD must label capture age unknown; patch presentation using existing provenance. |
| Blind 5: popup says absent report during lookup | low | loadScopedResult publishes completed/null before awaiting report, with a 45-second timeout. Add loading presentation; patch. |
| Blind 6: popup poll error persists after recovery | low | Successful loadResult publishes state but does not reset error. Clear scoped lookup error on success; patch. |
| Blind 7: review source link omitted | low | Retained source_url exists in raw review payload; EvidenceCard only renders content/interpretation. Render through existing URL allowlist; patch. |
| Blind 8: page workflow interaction coverage missing | medium | Helper/static-render tests never invoke actual Page/Landing effects/callbacks. Add mounted interactions; patch; same causes as verification findings below. |
| Blind 9: Azure imported snapshot completion unverified | medium | Import outbox assertion and local worker completion do not execute the new imported Azure handoff. Add mocked dispatcher/worker replay integration on PostgreSQL; patch. This does not claim live Azure acceptance. |
| Blind 10: audit lacks final results | low | Review snapshot contained pending placeholder. Replace with final verification and actual browser observations before delivery; patch by root. |
| Edge 1: single-attempt import skips assessment | medium | Synchronous import sets attempt_count=1; acquire_processing rejects count >= max_attempts. Reset only queued import handoff count, verify single-attempt report; patch. |
| Edge 2: polling overwrites edited URL | medium | Every active poll executes setUrl(current.source_url), including after buyer changes input. Synchronize initial reopened status and preserve edits thereafter; patch. |
| Verification 1: history/Watchlist file clearing untested | medium | Static child callbacks are no-ops; removing clearSavedPage leaves tests green and stale upload selected. Add actual mounted Page regression for both paths; patch. |
| Verification 2: popup restore wiring untested | medium | Helper test bypasses storage restoration effect; deleting loadResult(last.analysisId) is undetected. Mount popup with stored owner-scoped capture; patch. |
| Verification 3: tracer preview omission untested | medium | Presentation helper alone cannot catch Landing requesting nonexistent preview. Mount Landing and fail if preview requested for tracer; patch. |
| Root follow-through: capture single-attempt budget | medium | capture_customer_page has the same verified synchronous count=1 before a queued assessment; valid max_attempts=1 immediately rejects it. Apply the same reset and real-database regression under the user's explicit instruction to remedy inconsistencies; patch. |
| Root browser: extraction-only progress checks report completed | medium | Refreshed legacy completed extraction showed both assessment/report checks while the same screen says no report stored. Make progress reflect available report/preview; patch with interaction assertion. |
| Intent 1: final verification absent in snapshot | low | True at review snapshot; full suite and signed-in observations now available. Update audit with final evidence; patch by root. |
| Intent 2: real acceptance narrower than broad goal | false | A descriptive limit, not evidence of a broken implemented path. Actual Clerk tested; missing provider key and Chrome/cloud access remain explicitly unverified, never passed. |
| Intent 3: frontend tests mainly helpers | medium | Corroborates the three filed interaction gaps, each retained separately above. Mounted interactions patch. |
| Intent 4: immutable evidence enrichment prospective | false | Existing reports intentionally remain immutable; no historical report rewrite authorized or required. Audit states old markers may remain. |
| Intent 5: status inventory broader than direct checks | false | Implementation inventory explicitly distinguishes built from accepted. No claim that unchanged pilot/evaluation features were live verified. |


## Verification

- Backend pytest using dedicated PostgreSQL database; report live/provider skips explicitly.
- Frontend tests, TypeScript checking, production build and secret scan.
- Browser inspect real Clerk-protected UI and run guest tracer with local queue; authenticated usage may require human sign-in.
- Confirm stored-snapshot assessment/report pipeline with deterministic test provider; do not represent that as live YEScale acceptance.

### Executed verification

- Final PostgreSQL-backed full backend suite: 974 passed, 32 live browser/Azure skips, 348.22 seconds; existing test-client deprecation warning only.
- Full frontend suite: 124 passed, including actual mounted Page/Landing/Popup interactions with mocked external boundaries; TypeScript checking passed.
- Web and extension production builds passed. Web/extension configured-server-secret scans passed. Compose configuration and diff whitespace checks passed.
- Actual human-signed-in Clerk session verified account, 0-to-2 usage, tracer completion, history persistence/reopening/refresh, empty Watchlist, saved-HTML submission/assessment handoff and bounded no-key failure. Production browser confirmed no-report progress and source edits surviving real polls.
- Four review lenses completed; all patch findings resolved, no unresolved code-review finding. Live model, real Chrome, second-account browser journey, deployed Azure, unfinished evaluation and pilot acceptance remain explicit external/pre-existing gates, not passes.
- Local model key remained absent. No live provider call or cloud deployment occurred. Historical immutable reports remain unchanged. Existing initiative/demo planning edits excluded from the commit; only additive current audit content is staged for the pipeline.
- Web/API/database remain available; audit worker stopped for a clean operator-configured start using END_USER_TEST.md.
