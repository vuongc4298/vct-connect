# Story 3.1 completion acceptance — 2026-10-06

The interpretation foundation's live Chinese-fixture gate passed in local
isolated diagnostic run 2. This is actual YEScale output from authentic sanitized
Chinese product/review evidence, not a hand-authored FakeProvider answer. An
independent bilingual agent compared the accepted report against its exact source
projection and found no material unsupported claim or omission for this fixture.
It is not a human benchmark, calibrated confidence, or general model-quality
guarantee. The cloud's previous failed report remains failed; no deployment,
relabeling, replay, or historical causal explanation is claimed.

## Live result and provenance

- Analysis `071250f1-c4ca-49b9-8291-12ef9dababf7`, immutable snapshot
  `52191124-2c1d-4d3b-bd11-90becd745567`, dispatch
  `bc6e56f8-52ce-46b4-b582-3501f121707d`.
- State READY; exactly one dispatch, zero retries; extraction preserved.
- Candidate `deepseek-v4.1-flash`, exact expected/returned
  `deepseek-v4-1-flash-260910`, version `operator-observed-20261005`, thinking
  disabled. The gateway's immutable-version guarantee is not independently proven.
- Prompt `vi-text.v8`, schema `text-report.v2`, pipeline `saved-evidence.v1`,
  validator `vi-prose.v5`; 120-second deadline and 2,400-output-token cap.
- Input 9,491 serialized bytes; usage 2,298 input / 914 output tokens;
  application latency 13,797 ms. Provider request
  `20261006112443809364888Ae00We9s`.
- Creation time persisted as `generated_at=2026-10-06T04:24:55.725119+00:00`.
  Self-reported confidence 0.65, Vietnamese qualitative basis, provenance
  `model_self_reported`, calibration `uncalibrated`.
- Owner-scoped reopening is identical. A different owner receives no record.
  Canonical saved-report SHA256
  `492dcc986917e0a0142d100b314056c4540ead5ad1c283248dfd82dadff97b1d`.
- Evidence projection omits raw HTML, seller/shop/account/reviewer identifiers,
  shop name, contacts, URLs, session/cookie/navigation state. The backend obtains
  its provider key from the existing Key Vault secret; no client key is added.

## Substantive fixture rubric

| Source distinction | Observed accepted interpretation |
| --- | --- |
| 100 pulls and three layers | Correctly says 100 lượt rút / 3 lớp, without converting pulls to sheets or inventing pack counts. |
| Starting prices and discounts | From RMB 3.35 before discounts, from RMB 2.01 after shop discounts; not the final payable price. |
| Title's RMB 2/free-shipping wording | Explicitly attributed as an unverified title claim, distinct from displayed starting prices and actual charges. |
| Product versus shop rates | Last-three-month product positive rate 100.0%; separate shop 4.9 and 88VIP 97%, without inventing a score scale or broadening the population. |
| Shipment timing | Average seller sending in 23 hours, not promised buyer arrival; response average 14 seconds remains a source metric. |
| Aggregate versus accessible reviews | Approximate 30,000+ sales / 20,000+ reviews are source aggregates; the two accessible opinions remain individual reports. |
| Continued use | Continued use is retained and explicitly not treated as proof of repeat purchase. |
| Mixed review | Smooth outer packaging, slightly loose/porous paper texture, ordinary thickness, everyday usability and value remain distinct. |
| Confidence and missing evidence | Qualitative basis matches missing company, fees and freshness; no supplier-safety or calibrated accuracy claim. |

Minor presentation limitations remain: “khoảng 3 vạn+” is awkward Vietnamese,
“hơi xốp” is less precise than loose texture, and brand/Face wording and the title's
toughness adjective are omitted. The independent comparison assessed these as
nonmaterial for this fixture, not evidence of perfect translation.

## Authorization and spending

User authorized up to five deliberate diagnostics under the proposed $0.01
per-run ceiling, existing $0.09 combined retained-reservation limit, pinned model,
timeout/token cap, no retry, and bounded findings-only rejected-prose capture.
Two ran; the other three were not used. No rejected response or broader field
capture was saved. Broader capture was asked about but never assumed approved.

Run 1 FAILED / INVALID_OUTPUT / NON_VIETNAMESE_PROSE at summary. Its rejected
wording remains unknown because the approved policy covered findings only.
Run 2 READY does not explain that discarded response or earlier cloud failures.

Both reserved $0.00301725, totaling $0.00603450 for this batch. Their configured
usage estimates are $0.0009183 and $0.0008931 respectively; these are not invoices.
Actual invoice costs remain null/unknown. Local retained reservations are now
$0.03272385; with the last verified cloud $0.03186975, combined retained is
$0.06459360, below $0.09. No reservation was released, account topped up, or
failed/uncertain ledger reset.

Initial automatic approval review rejected the first external request for
unestablished payload sensitivity/destination authorization. An offline audit
proved the exact minimized public fixture fields and exclusions, and the next
approval review permitted the request. The rejected attempt made no dispatch.

## Implementation, review and verification

Corrected numerical-confidence assertion handling across all five prose fields,
including assessment/interpretation qualifiers and signed values. Source counts
and unquantified qualitative uncertainty remain permitted. Added bounded fabric
homograph/numeric technical-unit exceptions and demonstrated short Vietnamese
product vocabulary without lowering sentence or language-ratio thresholds.
The README now identifies the actual prompt/schema/validator versions.

Four independent review lenses completed, each finding was triaged, and direct
corrections were applied with regressions. Existing broad language-identification,
quotation/citation entailment, source-score policy and engineering-unit coverage
limitations are recorded in deferred-work.md; this is not a full semantic guard.

Final focused checks: 522 report/provider tests, 83 frontend tests, TypeScript
typecheck, and clean diff checks. The initial corrected contract passed all 13
PostgreSQL report tests; the final guard patch's persistence rerun also passed
all 13. The 106-case offline corpus matched its language labels, including a final
rerun after the score-only patch. The empty-text case is an expected separate
schema rejection; no language mismatch is silently relabeled as success.
The real accepted provider fields were reconstructed by removing only the
service's known fixed limitation suffix and labels, and passed the final validator
offline. The persisted report, provenance and hash remain unchanged; no fresh
provider request was necessary for those score-guard corrections.

Operational artifacts remain under Git-excluded tmp: diagnostic result/fence
files, payload audit, owned inspection and revalidation helper. The report is in
the retained diagnostic schema `story31_grounding_v8_diag_20261006_call2` in the
local diagnostic database, not the localhost demo database or Azure application.
Local demo paid generation remains disabled. The subsequently approved Azure dev
release is complete; health, runtime and saved-report preservation checks passed
without new paid requests. See `story31-completion-release.md`. A fresh cloud
semantic acceptance remains separate from this release and the accepted local fixture.
