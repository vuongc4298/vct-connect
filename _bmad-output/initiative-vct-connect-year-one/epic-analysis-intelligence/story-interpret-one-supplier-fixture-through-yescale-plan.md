---
title: 'Complete the interpretation foundation after the demo slice'
type: 'feature'
ticket: '1'
created: '2026-10-05'
status: 'built'
acceptance_status: 'live-fixture-accepted'
baseline_revision: 'f7210bd2944592325a5070b192cf42588b5b77a0'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['blind-hunter', 'edge-case-hunter', 'verification-gap', 'intent-alignment']
review_loop_iteration: 1
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The Oct 6 implementation supplies the provider, bounded dispatch,
persisted Vietnamese report and owned UI. Story 3.1 still lacks successful live
Chinese interpretation, actionable validation diagnostics and its confidence
output. The latest Chinese response failed INVALID_OUTPUT; its exact cause is
unknown because neither rejected content nor specific validation reason survived.

**Approach:** Extend the existing versioned interpretation contract with explicitly
uncalibrated model self-reported confidence, preserve safe validation diagnostics,
and verify authentic sanitized Chinese evidence through the same pipeline.
Reuse the adapter, immutable snapshot, dispatch ledger, persistence and report UI.

## Boundaries & Constraints

**Always:** Represent model self-reported confidence in one dedicated field with
score from 0 to 1 and a Vietnamese basis. Persist application-owned provenance
`model_self_reported` and calibration `uncalibrated`; clearly label this in the UI
and state it is not supplier safety, factual accuracy, or assessment confidence.
This follows the operator's explicit choice on 2026-10-05. Keep this field separate
from future deterministic Risk/Confidence/Coverage. Preserve old saved reports
without adding inferred confidence. New schema/prompt versions require the new
field; UI reads legacy reports when it is absent.

Keep exact model/version checks, secret isolation, field minimization, owner
boundaries, citation/language/score guards, reservations and one-dispatch fencing.
Retain only bounded enumerated failure reasons and allowlisted field locations;
do not serialize exception messages, raw response text, source values or keys
into diagnostic metadata. Valid report JSON remains available for evaluation.
Actual cost stays unknown when only an estimate or rounded dashboard charge is
available. Record report creation time and model/prompt/schema/pipeline versions.

**Never:** Relabel or replay either failed Chinese analysis; silently change models;
weaken validation to fit unknown historical output; add calibrated probabilities,
scoring, review clustering, factory/trader or media analysis; treat offline/fake
provider verification as live translation acceptance. No rejected-response storage
is added in this slice; an explicit bounded/redacted policy is required for that.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Behavior | Error Handling |
| --- | --- | --- | --- |
| New interpretation | Valid Chinese evidence and v2 provider JSON | Persist Vietnamese report, cited findings and labeled self-reported confidence | Bounds, language and citations validated |
| Bad confidence | Missing/out-of-range/bool/non-finite score or non-Vietnamese basis | No READY report | Safe schema/language diagnostic |
| Invalid report | Malformed schema, unknown citation, unsupported assessment score, non-Vietnamese prose | Preserve FAILED/INVALID_OUTPUT, reason and safe location | No payload/exception leakage |
| Credential echo | Literal or decoded provider key in content | Reject before persistence | Fixed credential diagnostic, no secret value |
| Legacy saved report | Existing v1 READY result | Same report remains usable, no invented confidence | No regeneration |
| Timeout/replay | Ambiguous dispatch or a second worker poll | Preserve UNCERTAIN and reservation; no extra spend | Existing fencing remains authoritative |

</frozen-after-approval>

## Code Map

Implementation checkout: `C:/Users/eidel/Desktop/VCT Connect/tmp/oct6-text-report-worktree`.
All relative paths below refer to that checkout. Existing untracked `tmp/`
operational evidence is retained and excluded from staging.

- `backend/app/interpretation/contracts.py`: strict report schema, version IDs,
  citation/prose/unsupported-score validation; introduce safe typed validation errors.
- `backend/app/interpretation/service.py`: prompt/schema construction, bounded
  generation, secret checks and settlement; retain allowlisted diagnostics in metadata.
- `backend/app/interpretation/provider.py`: existing provider/configuration, reuse.
- `backend/app/storage.py`, `backend/db/migrations/0010_text_reports.py`: JSONB
  report/metadata and generated_at already exist; avoid unnecessary migration.
- `frontend/packages/contracts/src/index.ts`, `frontend/apps/web/app/text-report.tsx`:
  optional legacy-compatible confidence type and conspicuous uncalibrated label.
- `backend/tests/test_text_reports.py`, existing PostgreSQL report tests,
  `frontend/apps/web/app/{text-report.test.tsx,page.test.mjs}`: extend meaningful
  validation, persistence/ownership and actual mounted report coverage.
- `backend/tests/fixtures/taobao_item_1076425861755.html` and
  `taobao-provenance.md`: authentic sanitized Chinese title, prices and two reviews.
- `implementation-artifacts/activation-oct6-text-report.md` and
  `epic3-continuation-handoff.md`: historical evidence and remaining scope.

## Tasks & Acceptance

**Execution:**
- [x] Contracts/service -- add v2 confidence and bounded safe validation reasons;
  preserve the public failure state and all existing dispatch protections.
- [x] Frontend contract/report -- display self-reported, uncalibrated confidence
  and its basis separately; preserve v1 report rendering and fixture/guest exclusion.
- [x] Backend/frontend tests -- cover matrix, diagnostic secret injection, Chinese
  evidence projection and score/prose boundaries with actual report persistence.
- [x] README and implementation evidence -- explain confidence meaning, safe
  diagnostics, legacy behavior, live limits and observed acceptance.

**Acceptance Criteria:**
- Given a new validated report, when stored and reopened, then its numeric
  confidence, Vietnamese basis and uncalibrated provenance remain identical.
- Given an invalid report, when settlement completes, then operators can identify
  a bounded validation category/location without seeing provider/source secrets.
- Given a legacy report, when the UI is upgraded, then the original content and
  citations remain usable without a confidence claim or new generation.
- Given a bounded live Chinese rehearsal, when the configured provider returns,
  then acceptance records the actual translation, evidence support, usage/latency,
  cost provenance and owner-scoped reopen; a failure is recorded honestly and
  does not satisfy this criterion. No automated paid retry follows failure.

## Implementation Notes

Planning only. Original ticket 3.1 is not marked built/done. No new provider request
has run during planning. The published demo baseline and untracked operational
artifacts remain intact; avoid rebuilding delivered modules.

Operator approved this complete plan on 2026-10-05. Full-route implementation
starts now; do not deploy, make paid requests, commit or push from the coding
handoff. Parent performs review and live acceptance after local checks. Python
runtime: `C:/Users/eidel/Desktop/VCT Connect/.venv/Scripts/python.exe`.
Existing local disposable PostgreSQL host port 55439/database `vct_oct6_report`
is available; keep retained rehearsal schemas intact. Use fresh test schemas.

Offline verification completed: 134 focused report/provider tests, 13 isolated
PostgreSQL report tests, 83 frontend tests, TypeScript typecheck and web production
build. Upload provenance test initially omitted required uploaded byte count;
corrected fixture invocation and reran the PostgreSQL suite successfully.

Matrix audit: new report/confidence persistence and Chinese projection are covered
by PostgreSQL owner reopen tests; bad confidence and all diagnostic categories
by focused parametrized tests; literal/escaped credential echo by diagnostic tests;
legacy v1 by PostgreSQL no-generation and mounted v1 UI tests; timeout/replay by
existing hung-provider and dispatch crash/fencing tests. All covering suites ran.
The authentic Chinese test uses hand-authored output and does not certify live
translation quality. No new paid call or deployment has run for v2 yet.

## Plan Change Log

2026-10-06 completion review loopback (bad_plan): the dedicated confidence
field introduced a prose surface not adequately protected against `Tôi chắc chắn
90% về cách diễn giải.` / `Tôi khá chắc chắn: 65%.`; the current label-to-any-number
guard also rejects `Độ tin cậy còn hạn chế vì chỉ có 2 đánh giá.`. Both outcomes
were reproduced by the parent. No source edits were made in this resumed run
before loopback, so no new implementation code needs reverting. KEEP the
previously committed confidence contract, legacy UI, field projection, dispatch
fences, source-quotation protections, secret guards and safe diagnostics intact.

Completion implementation tasks, in order (this checkout only):
The parent already initialized BMad successfully for this workflow run and is
executing the rendered step-03 implementation handoff. This is a coding subtask,
not a new BMad invocation: implement this plan directly; do not invoke or render
any skill again. Existing operational files under tmp remain outside the code
handoff and must not be staged or executed by the implementer.
- [x] In `backend/app/interpretation/contracts.py`, replace the label-to-any-number
  check with a narrowly defined numerical-confidence assertion check. Detect
  numerical confidence assertions outside the dedicated score, including explicit
  percentages after `chắc chắn`/`tự tin`, recognized score labels with numerical
  values, fractions and Vietnamese number-word forms covered by existing tests.
  Preserve unsupported supplier-risk scoring rejection. Permit a qualitative
  confidence statement whose following number is explicitly an evidence count
  (e.g. `2 đánh giá`), not an interpretation confidence value. Do not classify
  arbitrary source percentages/prices/units as interpretation confidence.
- [x] In that file, correct the demonstrated Vietnamese fabric homograph `vải the`
  without accepting standalone English `the` narrative; exempt bounded technical
  unit symbols µm and Ω only when attached to a numeric quantity, preserving
  foreign-script prose rejection. Add the demonstrated ordinary short Vietnamese
  product adjectives `mỏng`, `rẻ` to the vocabulary without changing thresholds.
  Increment `VALIDATION_VERSION` to `vi-prose.v5`; leave prompt/schema versions
  unchanged. Do not alter source quotations or language ratios speculatively.
- [x] In `backend/tests/test_text_reports.py`, add regression tests for the exact
  reproduced cases, all five prose locations for numeric-confidence rejection,
  evidence-count/source-value allowances, foreign counterexamples for fabric/unit
  exceptions, and both directions of `evaluate()` report-language mismatch IDs.
  Retain every current confidence, quote, secret, persistence and replay test.
- [x] Update `README.md` to identify current vi-text.v8/text-report.v2 and
  vi-prose.v5, with uncalibrated confidence unchanged. Run focused report tests
  and the offline language corpus; report any failures honestly. No paid calls,
  deployment, remote operation, commit or push in the coding handoff.

Task verification: Given a numerical interpretation-confidence claim in any
prose field, when validated, then it is UNSUPPORTED_SCORE at that field. Given
a qualitative basis with an explicit review count, when validated, then it is
accepted without inferring a confidence value. Given Vietnamese fabric language
or a numeric technical unit, when screened, then it is accepted; standalone
foreign narrative and unquoted foreign scripts still fail. Given either evaluator
label mismatch direction, when evaluated, then its exact ID is reported.

Live completion remains the original frozen acceptance criterion. User authorized
up to five deliberate diagnostic requests at the existing per-run $0.01 and
combined $0.09 reservation bounds; run 1 rejected at summary and captured no
prose under findings-only policy. Any extension of capture to other prose fields
requires its pending explicit answer. Keep local demo generation disabled;
isolated operator diagnostics cannot drain its queue or rewrite old results.

Completion coding handoff verification (2026-10-06): all 427 focused tests in
`backend/tests/test_text_reports.py` passed using the specified Python runtime.
The offline evaluator ran all three retained language corpora (57 + 24 + 25 =
106 cases): no screen false rejections, screen false acceptances, or report
language mismatches. The `empty` case remains SCHEMA_INVALID/findings.text,
an expected structural rejection rather than a language mismatch. New tests
verify both evaluator mismatch directions with exact IDs, all five prose
locations, safe settlement and no replay, explicit evidence counts/source values,
and bounded fabric/unit exceptions with foreign counterexamples. Initial local
failures exposed colon placement and casefolded unit handling in the patch;
both were corrected before the final passing run. Frontend and PostgreSQL
suites were not rerun for this contracts/tests/documentation-only completion
patch. Live Chinese acceptance remains unmet. No operational tmp files were
executed, and no paid request, deployment, remote operation, commit or push ran.

## Review Triage Log

Completion review 2026-10-06 (every reviewer finding, before deduplication):

| Lens / finding | Verdict | Evidence and route |
| --- | --- | --- |
| Blind numeric confidence | medium | Parent probe confirms `Tôi chắc chắn 90% về cách diễn giải.` accepts in new basis. New field lacks complete assertion detection; bad_plan, completion loopback. |
| Blind qualitative source count | medium | Parent probe rejects `Độ tin cậy còn hạn chế vì chỉ có 2 đánh giá.` as score. New confidence explanation surface exposes false score classification; same bad_plan loopback. |
| Blind mixed English/French padding | medium | Parent probes both accept; ratio heuristic already accepted these before this change. Pre-existing language-identification limitation; defer, not a factual/language QA guarantee. |
| Blind fabric homograph | medium | `Vải the mềm mại.` rejects from newly strengthened any-blacklisted-word rule. Direct correction with counterexamples; patch. |
| Blind technical units | medium | Parent probes numeric µm and Ω reject under new script guard. Bounded unit exception and negative examples; patch. |
| Blind compact product descriptions | medium | `Giấy mỏng.` and `Giấy rẻ.` reject; concrete vocabulary omissions exposed by newly added tissue words. Direct vocabulary correction with unchanged thresholds; patch. |
| Blind citation-scoped quotes | medium | Parent confirms quote from E2 with E1 citation accepts. Global supplied-source exemption was present in baseline, including single quotes; pre-existing entailment limitation, defer. |
| Blind structural metadata quote | medium | Parent confirms path string is treated as supplied source. Recursive collection of complete evidence existed in baseline; pre-existing exemption-input defect, defer. |
| Blind compact guidance/schema maxima | false | Prompt asks for compact output under token cap while schema retains backward-compatible structural maxima. A larger valid basis is not a claim that compact guidance is strictly schema-enforced; no contract requires those advisory limits. |
| Blind README versions | low | README says v2 prompt while constants say v8. Direct documentation correction, patch. |
| Blind substantive live acceptance | medium | Latest v8 acceptance failed; current run 1 summary also failed. Live gate remains unmet and is the active completion objective; retain honest partial status until observed. |
| Edge numeric confidence colon | medium | Parent reproduces `Tôi khá chắc chắn: 65%.` accepted in new basis. Same new-field assertion defect as Blind numeric confidence, bad_plan loopback. |
| Verification evaluator mismatch mutation | medium | Filed evidence trusted: forced empty mismatch list survives existing assertions. Add both mismatch-direction exact-ID tests; patch. |
| Intent live outcome vs pipeline tests | false | Auditor correctly separates offline/earlier READY evidence from current substantive live gate. No completion claim exists; perform the pending gate and retain failure honestly if unmet. |

Completion review round 2 (all lenses collected before triage):

| Lens / finding | Verdict | Evidence and route |
| --- | --- | --- |
| Blind qualified confidence | medium | Parent reproduces `Độ tin cậy của diễn giải này là 90%.` and `Tôi chắc chắn đến 90% về cách diễn giải.` accepted. Narrow connector omissions in the assertion guard; trivial patch with exact all-field regressions. |
| Blind qualitative partial confidence | medium | Parent reproduces `Tôi chắc chắn một phần về cách diễn giải.` falsely rejected. The new value matcher consumes this qualitative phrase; direct patch with quantified-fraction counterexamples. |
| Blind risk-unknown evidence count | medium | Parent reproduces rejection, but the unchanged baseline risk-label-to-number branch also rejected it. Pre-existing conservative risk guard; defer rather than weaken its risk protections in this confidence correction. |
| Blind score-bearing source quote | medium | Existing score check deliberately precedes language quotation exemptions and baseline also rejects source confidence-score quotes. Pre-existing source-score policy ambiguity; defer; do not silently exempt numerical score claims. |
| Blind additional engineering units | medium | Existing vi-prose.v4 script guard rejects µg/µF/kΩ; the new bounded exceptions correct only demonstrated µm/Ω. Other unit handling remains a pre-existing coverage limitation, defer. |
| Blind mixed-language padding | medium | carried: same inputs and unchanged cue-ratio defect as prior Blind mixed English/French. Keep previous defer; no second patch or deferred entry. |
| Blind citation-scoped quotation | medium | carried: same global exemption inputs and cited-evidence mismatch as prior Blind citation-scoped quotes. Keep previous defer without duplicate entry. |
| Blind metadata quotation | medium | carried: same complete-entry source-string traversal as prior Blind structural metadata quote. Keep previous defer without duplicate entry. |
| Blind live acceptance absent | false | New actual run 2 is READY, independent bilingual audit passes its specific fixture, owned reopen is identical and another owner is denied. This happened after the review diff snapshot; record the new evidence without rewriting historical failed cloud acceptance. |
| Blind evaluator CLI exit mode | false | This is an intentionally diagnostic offline CLI, not a CI gate; targeted known-mismatch datasets are expected inputs. No automated consumer relying on its zero exit as acceptance was identified. Adding an optional public check mode is not a demonstrated defect. |
| Edge assessment qualifiers | medium | Parent reproduces assessment-qualified 90% accepted. Same narrow connector omission as Blind qualified confidence; patch, keep assessment confidence forbidden. |
| Edge signed confidence | medium | Parent reproduces +0.65 accepted outside the dedicated field; optional sign omitted from numeric literal. Direct patch with positive/negative/fraction regressions and source-count counterexamples. |
| Edge metadata quotation | medium | carried: prior identical location and complete-entry exemption claim; same defer, no duplicate action. |
| Edge citation-scoped quotation | medium | carried: prior identical location and global exemption claim; same defer, no duplicate action. |
| Edge mixed-language fragments | medium | carried: prior identical sentence-ratio claim; same defer, no duplicate action. |
| Verification assessment-qualified scores | medium | Verified independently by parent after filed service reproduction. Same connector defect as Edge assessment qualifiers; patch exact forms across all fields. |
| Intent contract versus actual model surface | false | Correct reading of the snapshot at launch. Actual live run 2 now supplies the missing independent semantic/persistence evidence. Preserve its bounded fixture scope; no human benchmark, calibration or historic causal explanation is claimed. |

| Lens / finding | Verdict | Evidence and route |
| --- | --- | --- |
| Blind 1: score repeated in prose | medium | Existing regex missed `Điểm tự báo cáo ... 0.65`; patch extends the existing score guard, with tests in all five prose locations. |
| Blind 2: supplier assurances in basis | medium | Structurally valid Vietnamese can contain unsupported assurances. Factual support is a pre-existing model evaluation limitation; defer semantic quality work and inspect the basis during the already planned live acceptance. Numeric confidence remains explicitly uncalibrated and separate from safety. |
| Blind 3: quoted foreign basis bypass | medium | The shared screen removes foreign quotations. Patch disables quotation exemptions for the new Vietnamese basis only, with Chinese and English counterexamples; legacy source-title handling remains intact. |
| Blind 4: natural confidence explanation rejected | medium | Small lexicon rejected the supplied natural Vietnamese example. Patch adds concrete interpretation terms and a passing regression; it does not adjust the guard to unknown historical output. |
| Blind 5: nested JSON RecursionError | medium | Complete nested JSON reached generic uncertain settlement. Patch catches RecursionError at parsing and retains SCHEMA_INVALID/report; test verifies no replay. |
| Blind 6: schema subtypes | low | The approved contract intentionally records category/location, sufficient to identify the affected field. Reject optional subtype enhancement: it adds a diagnostic surface beyond a direct correction. |
| Blind 7: live acceptance incomplete | false | No story acceptance or live success is claimed. The approved sequence requires review before the live rehearsal; that gate remains pending and will be recorded honestly. |
| Edge 1: escaped credential in duplicate member | medium | JSON decoding discards earlier duplicate members, bypassing decoded credential detection. Patch checks every decoded member before rejecting duplicate keys; escaped credential regression retains CREDENTIAL_ECHO/report. |
| Edge 2: nested arrays settle uncertain | medium | Same demonstrated parsing defect as Blind 5; same patch and regression. |
| Edge 3: summary repeats confidence score | medium | Same demonstrated dedicated-field defect as Blind 1; score guard patch. |
| Edge 4: diagnostics claim fails on nesting | medium | Same demonstrated parsing defect as Blind 5; fixed category/location tested. |
| Verification 1: confidence diagnostic mutation survives tests | medium | Filed mutation evidence accepted. Patch changes each invalid-confidence case to assert the exact reason/location, including score, basis and extra-field cases. |
| Intent 1: live semantic acceptance versus offline contract | false | Accurate phase distinction, not a completed-story claim. Offline results certify transport/persistence; live translation remains the next gate. |
| Intent 2: operator presentation and schema detail | false | Approved boundary is safe category/location metadata in the dispatch ledger, not a new operator UI or schema subtype. PostgreSQL verifies persisted diagnostics. |
| Intent 3: retrospective cause unknown | false | Intent explicitly records the old cause as unknown and prohibits rejected-response storage/replay; diagnostics are prospective. No recovery of absent historical content is claimed. |
| Intent 4: fake-provider confidence versus live confidence | false | Tests verify schema/persistence/display; no claim that a live model produced the test value. Live confidence output remains pending. |

All four reviewers completed. No intent or plan loopback was required. The
implementation agent could not continue after its usage-limit interruption;
the parent applied the small patches. Focused tests now pass: 145, including
the review regressions. PostgreSQL persistence is rerun after the service fixes.

Post-review verification passed: all 13 PostgreSQL report tests, all 83 frontend
tests and typecheck. The web production build passed for the unchanged frontend.
The implementation plan is built; Story 3.1 remains unaccepted until the separate
live Chinese gate below is observed. No calibration or factual-support guarantee
is claimed. Semantic supplier assurances remain a deferred evaluation limitation.

Released reviewed implementation `21fed98` by immutable image digest. The one
approved live Chinese rehearsal failed NON_VIETNAMESE_PROSE/findings.text after
29321ms (1304 input/2109 output). One dispatch, no replay; rejected text remains
unretained. The saved v1 demo reopened unchanged. Detailed evidence is recorded
in ../../implementation-artifacts/story31-v2-release-acceptance.md. Story 3.1's
live criterion remains unmet; an explicit bounded/redacted diagnostic policy
is proposed separately and awaits approval before any further paid experiment.

## Design Notes

The new confidence field expresses the model's own uncertainty about its
interpretation, not a calibrated prediction. It must never feed deterministic
risk/assessment confidence automatically. Application-owned labels prevent the
provider from asserting calibration. Versioned generated schemas and optional
legacy UI typing avoid rewriting immutable old reports.

## Verification

Latest completion evidence: `../../implementation-artifacts/story31-completion-acceptance.md`.
Actual live Chinese fixture run 2 is READY and independently compared to the
source, with identical owned reopening and denied other-owner retrieval. The
final reviewed assertion-guard patch revalidates that saved provider output
without modifying its report or requesting generation. Parent final focused
suite passes 522 tests; frontend 83 tests and TypeScript checks pass. Earlier
implementation/release/failure notes above are historical and do not describe
the new fixture acceptance. Final PostgreSQL rerun passed all 13 tests after the
review corrections. All six frozen matrix rows are covered by the executed
report/provider and PostgreSQL suites: confidence persistence/ownership, invalid
confidence fields, diagnostic/secret boundaries, legacy no-generation reopen,
credential echo and timeout/replay fencing. The live criterion is covered by
actual run 2 plus independent source comparison and saved-owner inspection.
No additional provider call, rejected-prose capture, deployment or push was needed.

- Focused report/provider tests, including adversarial diagnostics and sanitized
  Chinese evidence; no external network or payment for offline verification.
- Existing isolated PostgreSQL report persistence/replay/ownership tests against
  retained disposable DB with a fresh test schema/temp path.
- Frontend tests, typecheck and relevant build; preserve legacy mounted Page checks.
- Context-free implementation review before release. No remote push unless requested.
- After local checks and concrete release review, one deliberate live Chinese
  rehearsal using the current approved model and spending bounds; preserve earlier
  failed/uncertain analyses and reconcile returned metadata/billing before any retry.
