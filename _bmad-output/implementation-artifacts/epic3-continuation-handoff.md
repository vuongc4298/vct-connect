# Epic 3 continuation after the Oct 6 demo priority change

Prepared 2026-10-05. Verified pushed demo baseline:
`29344d20da6d861439dcdc1c79306f5b1e3d2630`, branch `codex/oct6-text-report`.
This is a reconciliation and starting intent, not a completed story or epic.

## What the demo already delivered

- Backend `LLMProvider` protocol and YEScale adapter, bounded structured output,
  selected public evidence projection, exact requested/returned model checks,
  thinking control, deadlines and conservative spending reservations.
- Immutable snapshot-linked report jobs, persistent dispatch ledger, one app
  dispatch per report job, lease fencing, uncertain-state recovery and owner-scoped
  saved report retrieval. Unknown actual costs remain unknown.
- Vietnamese summary, evidence-linked observations/inferences, limitations and
  pre-order actions, independent report progress, extraction fallback and reopen.
- Deployed signed-in 1688 saved-page interpretation and report acceptance. Citation
  E2 and exact persisted report reopening passed the final presentation rehearsal.
- UI source restoration for uploaded, public and extension saved analyses.

Reuse `backend/app/interpretation/{provider,contracts,service}.py`,
`backend/app/storage.py`, `backend/db/migrations/0010_text_reports.py`,
`backend/worker/main.py`, `frontend/apps/web/app/text-report.tsx` and existing
report/API contracts. Do not build a second gateway or duplicate dispatch ledger.

## Reconcile original stories without claiming full completion

| Story | Existing contribution | Remaining original acceptance |
| --- | --- | --- |
| 3.1 YEScale supplier interpretation | Adapter, Vietnamese reports, versions/settings/usage/latency/reservation and backend-only credentials exist. The v2 release adds safe categorized diagnostics and explicitly uncalibrated model self-reported confidence, with persisted labels and legacy-compatible UI. | Live Chinese interpretation still has not passed: the v2 rehearsal identifies NON_VIETNAMESE_PROSE in findings.text. Distinguishing untranslated text from a validator false positive requires an approved bounded/redacted diagnostic policy. Confidence remains separate from calibrated assessment confidence. Actual cost stays unknown without trustworthy billing data. |
| 3.2 Deterministic review signals | Selected review bodies can reach interpretation; extracted evidence IDs/provenance exist. | Complaint grouping, duplicate/timing/rating-text/volume signals and review reliability are not implemented. Missing dates/ratings must remain unknown. |
| 3.3 Semantic/structured review interpretation | Provider, evidence projection and run metadata can be reused. | Embeddings, near-duplicate clustering, complaint category/severity and manipulation/reliability outputs are pending; original dependencies on 3.1 and 3.2 remain. |
| 3.4 Factory/trader evidence | Existing extraction provenance and provider interfaces are reusable. | Direction/strength/reliability aggregation, contradictory/self-claim handling, likelihood/confidence and uncertainty are pending. Trader status alone must not add risk. |
| 3.5 Risk/Confidence/Coverage | Source extraction coverage exists; illustrative fixture scores are separate. | Full deterministic versioned assessment and seven dimensions, thresholds, manipulation adjustments and approved critical floors remain pending. Owner approval of critical evidence eligibility is required by the original ticket. |
| 3.7 Complete worker assessment | Snapshot-linked interpretation/report processing and replay protections exist. | Review/factory/risk integration, assessment/run/finding/score storage and the complete REPORTING handoff are pending. Current extraction can complete before the separate text-report job; preserve compatibility and explicitly reconcile this with the original locked-job assessment lifecycle. |
| 3.6, 3.9 Media | No demo contribution to media analysis. | Permitted image/video interpretation, retention/provenance and worker assessment enrichment remain pending. |
| 3.8 Refactor sweep | Focused demo corrections were reviewed and tested. | Epic-wide cleanup after all prerequisites is pending. |

Reporting Epic 4 likewise has a reusable text-report UI, authorized retrieval,
progress, limitations and citations. Full assessment-backed risk/confidence/
coverage, guest-safe assessment projection and complete reporting acceptance
are not done. Do not mark 3.1, 3.7, Epic 3 or Epic 4 done from demo evidence.

## Recommended next implementation: finish the interpretation foundation

Use `bmad-build` with original ticket 3.1 and this handoff as additional context.
Limit the first continuation to safe diagnostic observability and reproducible
Chinese-input acceptance; retain the already working provider/persistence path.

1. Distinguish schema, citation, unsupported-score and Vietnamese-prose validation
   failures internally with bounded enumerated reasons; maintain safe user-facing
   failure states and never log credentials or unbounded source/provider payloads.
2. Establish a bounded, redacted diagnostic/evaluation output policy before
   retaining rejected model text. Existing production failures cannot be diagnosed
   conclusively from INVALID_OUTPUT metadata alone; do not guess the cause or
   weaken validation to make an unobserved response pass.
3. Exercise authentic sanitized Chinese title/review input with offline regression
   fixtures first. A fake-provider test proves integration, not live translation
   quality. Require a separate reviewed live result for substantive acceptance.
4. Reconcile original 3.1 confidence/run-output requirements in its build plan.
   Keep interpretation uncertainty distinct from deterministic risk confidence.
5. After the foundation's chosen acceptance passes, build original 3.2, then 3.3
   and 3.4 subject to their dependencies, then owner-gated 3.5 and complete 3.7.
   Media and the epic refactor follow their original prerequisites.

## Live evidence and constraints to preserve

- READY 1688 report: `36677413-84b7-45b5-8255-828fbe4cd0c8`. The product title
  is English, so it is not proof of Chinese translation quality.
- Chinese attempt `c40adda8-aba1-42c2-8306-12f8604f1abc`: UNCERTAIN /
  PROVIDER_TIMEOUT, one dispatch, retained reservation $0.0021396.
- Fresh Chinese attempt `5d86a995-5687-4b60-9e18-b31c87216d7e`: FAILED /
  INVALID_OUTPUT, exact expected returned model, 1052 input / 1888 output,
  49377ms, one dispatch, retained reservation $0.0021396. Neither attempt is
  relabeled or replayed. Capture timestamp remains unknown.
- Candidate `deepseek-v4.1-flash`, expected return
  `deepseek-v4-1-flash-260910`, operator-observed version, thinking disabled.
  This is a demo candidate, not a human-benchmark-selected production model or
  established immutable gateway version guarantee.
- Existing approved ceilings: $2 total / $0.10 per call, no account top-ups;
  deployed ledger cap $0.09, deadline 120 seconds, output cap 2400 tokens.
  Preserve reservations for uncertain spend. Latest displayed balance $0.092
  is rounded and does not authorize resetting the ledger or additional retries.
- No new paid generation is part of this preparation. Any subsequent live
  diagnostic must be deliberate, account for retained spend and stay within
  approved limits. Do not silently change models or auto-replay failed jobs.

Original ticket requirements and dependency graph remain authoritative. The
original checkout's edited priority documents and untracked operational artifacts
are preserved. This handoff records contributions without rewriting ticket truth.
Detailed evidence: `activation-oct6-text-report.md`; presentation fallback:
`oct6-demo-walkthrough.md`.

Continuation implementation/release evidence: `story31-v2-release-acceptance.md`.
Implementation and regression review are complete; the live Chinese gate remains
open. Earlier preparation-only and demo freeze notes above are historical; the
latest approved v2 release preserves the saved v1 fallback and prior dispatches.

The subsequent approved one-call local language diagnostic failed
SCHEMA_INVALID/findings before language validation and retained no rejected
prose. See `story31-language-diagnostic-result.md`; a safe schema-subtype helper
is prepared offline, but its distinct paid followup remains unapproved.

That followup was subsequently approved and ran once: schema validation passed,
but summary failed the language screen. No sample was saved under the earlier
findings-only policy. See `story31-schema-followup-result.md`. Broader first-prose
capture and a three-request resolution batch are proposed in
`story31-bounded-resolution-proposal.md`; neither is approved or executed yet.


The broader policy and three-request resolution batch were subsequently approved and executed. Two retained first-field diagnostics supported Vietnamese source-rendering/prompt and tissue-vocabulary corrections, reviewed and tested with 147 focused tests locally and in the non-root offline image. Commit 115ba712ec38124042558119fc8a423243d1ff4f is released to dev, not pushed to Git. Final cloud acceptance failed OUTPUT_INCOMPLETE at 2400 output tokens; owner-scoped reopen preserves that failure. The batch is exhausted and Story 3.1 remains partial. See story31-bounded-resolution-result.md for final spending, revisions and the next truncation blocker. No additional paid call or replay is authorized by this batch.


The operator subsequently approved compact report guidance and one fresh paid acceptance request. Reviewed/tested prompt vi-text.v5 was committed locally as d303ec498bbecd5dbca02cac2537c13297d8b6e3 and deployed to healthy dev revisions. The provider completed at 991 output tokens, avoiding truncation, but findings.text failed NON_VIETNAMESE_PROSE. Rejected prose was not retained, so the specific cause is unknown. The owned failure reopens unchanged; no retry ran. The single-request authorization is consumed; Story 3.1 remains partial. See story31-compact-report-result.md for final evidence and spending.


A subsequent approved bounded local diagnostic retained a redacted Vietnamese shipping/service finding and demonstrated an actual screen false positive (13 recognized words of28, threshold14). An evidenced vocabulary correction plus validation_version vi-prose.v2 was reviewed/tested (149 focused tests locally and in the non-root offline image), committed locally as2124b19537a96a1447be153cc45371136200ba63, and released to healthy dev API14/dispatcher23. Compact prompt remains vi-text.v5. The retained finding passes offline; old cloud rejections cannot be assigned this cause without their missing prose. Additional owned cloud acceptance is requested and pending; no extra paid call has run. See story31-shipping-screen-result.md. Story3.1 remains partial.


That additional owned cloud acceptance was explicitly approved and ran once: analysis7de59f78-c93a-4764-ae51-410dbe1df587 completed at889 output tokens but failed NON_VIETNAMESE_PROSE/findings.text under vi-prose.v2. The owned failure reopens correctly. No rejected cloud prose retained, so its cause remains unknown. Both authorized calls are consumed and no retry ran. A small offline synthetic coverage probe found2 further valid Vietnamese packaging descriptions rejected among12 positive examples; all6 foreign negatives rejected. This supports broader offline coverage work before additional paid attempts, without assigning this cause to the cloud response. Full evidence: story31-shipping-screen-result.md. Story3.1 remains partial.


The subsequent approved offline coverage work added57 synthetic regression examples (33 Vietnamese,24 foreign/mixed/ambiguous) across product/review, packaging, price, service, freshness, actions and confidence wording. Baseline vi-prose.v2 had3 false rejections, all packaging/NFD-related; a six-word vocabulary correction gives0 mismatches on this curated corpus without lowering thresholds. Validation version vi-prose.v3, compact prompt vi-text.v5 and schema text-report.v2. Independent review found no actionable issues;206 focused tests pass locally and in the non-root offline image;13 isolated PostgreSQL settlement tests pass. Code commit a5450c00c4348c177813afb85df9040deb4b38b2 was released to healthy dev API15/dispatcher24 without Git push. Cloud ledger remains8 dispatches/$0.01802520, pending0; no paid generation occurred. This is development coverage, not general language calibration or live Story3.1 acceptance. See story31-offline-prose-coverage-result.md. A fresh complete accepted owned live report and identical reopen remain the gate.


The subsequent separately approved single live acceptance ran once under vi-prose.v3: analysis d44fb0b5-b30b-4830-8723-e40b8e77ff49 completed at937 output tokens but failed UNSUPPORTED_SCORE/self_reported_confidence.basis. No rejected cloud prose retained, so exact wording/true violation versus false positive remains unknown; no retry ran. Owned reopening preserves the failure and source. Displayed charge $0.0006, invoice actual unknown; cloud9/$0.02054175, pending0; combined retained reserves $0.04439385. Authorization consumed, Story3.1 still partial. Next: offline confidence-basis prompt/guard contract coverage before any separately approved bounded live diagnostic. See story31-screen3-live-acceptance-result.md. No code changes or Git push in this acceptance.


Approved offline confidence review confirmed synthetic qualitative confidence-label + evidence-number overmatching. Prompt vi-text.v6 clarifies dedicated numeric score versus qualitative evidence basis and uses a conditional example; guard vi-prose.v3 and schema text-report.v2 unchanged. All236 focused report tests pass and independent quick review found no issues. Known conservative guard limitation deferred; exact prior rejected cloud wording/cause remains unknown. No paid request, deployment or Git push; dev still v5/API15/dispatcher24. Story3.1 live gate remains open. See story31-confidence-basis-guidance-result.md. Next: release the reviewed prompt then separately approved bounded live acceptance/diagnostic as needed.


The operator subsequently approved the v6 dev release. All236 focused tests pass in the actual non-root offline release image; code202c2db6b9dab9d3afdfaf11830c6c2878cea745 deployed as sha256:142c550e33032a1c8237052dc0db80ff4cf9bd73e5a09307d1d3ca3229186581. API16/dispatcher25 healthy, analysis/migrate templates match, effective settings/secret refs and web image preserved. Read-only ledger still9/$0.02054175 pending0, combined retained $0.04439385. No paid request or Git push. Separate one-request owned live acceptance capped at $0.01 is proposed, not yet approved. See story31-confidence-basis-guidance-result.md.


The separately approved v6 live acceptance ran once and produced first READY Chinese-fixture v2 report: analysis95fdb0a2-5c69-475a-87a8-77ac29bbedc5,1773in/835out,15431ms. All citations resolve; self-report confidence0.55 is explicitly uncalibrated; owned reopening identical. Substantive acceptance still failed:23-hour dispatch mistranslated as delivery, unsupported fees-excluded assertion and starting-price/scope/product-fact omissions. Preserve this READY report as immutable evidence, not a passed Story3.1 or a relabeled FAILED job. Displayed charge $0.0008; actual unknown; cloud10/$0.02317800 pending0; combined retained $0.04703010. No retry, additional paid diagnostic or Git push. Authorization consumed. Next: offline grounding correction using retained accepted prose. Full evidence: story31-confidence-v6-live-acceptance-result.md.


Approved grounding correction implemented/released on2026-10-06: code d181ab06e5830f7b966765ad363bf290005de16b, prompt vi-text.v7 with dispatch/starting-price/unknown-fee/product-scope/specification/review-attribute guidance and audited Taobao item field-specific metric scope. Score/language/schema guards unchanged.245 focused tests pass locally/final non-root offline image;13 isolated PostgreSQL tests pass. Quick review found one test-upload-bytes mistake; corrected both fixture tests and asserted original upload provenance. Digest8c2a34aa4efd5e111c90fa67dd3f613ab002a4ef494dbbc4cdf2f92d0dcc44aa released to healthy API17/dispatcher26, analysis/migrate templates matching; settings/secret refs/web preserved. Read-only ledger10/$0.02317800 pending0, combined$0.04703010. Prior READY v6 report95fdb0a2-5c69-475a-87a8-77ac29bbedc5 hash identical, still one dispatch. No paid request or Git push. Story3.1 remains partial; separate capped single live acceptance proposed, not approved. See story31-grounding-guidance-result.md.

The operator subsequently approved that single v7 acceptance, which ran once on2026-10-06: analysis0c4823ba-c3ce-4828-aef4-dadc97d2af6e failed NON_VIETNAMESE_PROSE/findings.text after2,050in/1,043out and14,798ms. Rejected prose not retained; exact violation versus screen false positive unknown. Owned saved failure reopens identically, exactly one dispatch, no retry. Displayed charge$0.0009; invoice actual unknown/null. Cloud11/$0.02601525 pending0, combined retained$0.04986735. Single-request authorization consumed; Story3.1 substantive gate remains open. Automatic review blocked broad inspection; safe FAILED/null assertions and whitelisted metadata resolved that inspection block. No code change or Git push. Next: offline language-screen contract investigation; any further paid/capturing diagnostic needs separate explicit scope/authorization. See story31-grounding-v7-live-acceptance-result.md.

Approved offline language-contract investigation completed on2026-10-06. Added reproducible diagnostic evaluator and25 synthetic boundary cases:6/22 ordinary Vietnamese clauses falsely rejected and2/3 targeted foreign/mixed cases falsely accepted, reproduced through full report validation; existing57-case corpus still matches all labels. These deliberately selected examples are not calibrated accuracy data. All247 focused tests pass after quick review fixed one evaluator classification bug with schema/score regressions. Production guard/prompt/deployment unchanged; exact missing v7 wording/root cause remains unknown. No paid request, rejected capture, cloud action or Git push. Existing contract and quotation faults recorded for subsequent correction; Story3.1 acceptance remains open. See story31-language-contract-investigation-result.md and plan-story31-language-contract-investigation.md for review evidence.
