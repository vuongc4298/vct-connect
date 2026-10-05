---
title: 'Oct 6 saved-evidence Vietnamese report'
type: 'feature'
ticket: ''
created: '2026-10-05'
status: 'built'
baseline_revision: '1a98e428b2dcbe15feb2ec064c9ef136f9e01eac'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['blind-hunter', 'edge-case-hunter', 'verification-gap', 'intent-alignment']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Saved extraction works; Vietnamese assessment is illustrative. The October 6 journey needs real interpretation, progress, sources, limitations, and pre-order actions.

**Approach:** Queue bounded backend YEScale interpretation, persist Vietnamese reports, and show report readiness separately from extraction in the existing buyer screen.

## Boundaries & Constraints

**Always:** Preserve immutable extraction, provenance, ownership, quotas and insufficiency. Backend calls require credentials, model/version pin, input/output limits, deadline and spend ceiling. Minimize personal data; use anonymous identifiers. Persist model/prompt/schema/pipeline versions, returned model, usage, latency, request ID and cost provenance; unknown cost stays unknown. Validate citations and separate inference from observations. Treat source text as untrusted. Distinguish extraction/generation dates from unknown capture freshness. Label illustrative scores; exclude fixture findings from real reports.

**Never:** Add full scoring, clustering, media, history or evaluation. Rewrite extraction results; silently switch models; invent evidence/cost/freshness; expose keys; retry ambiguous paid calls. Deployment/live activation require separately configured model and budget.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| Saved evidence | Owned SUCCESS/PARTIAL snapshot; provider enabled | Queued report becomes persisted Vietnamese summary, cited findings, limitations, actions | Preserve extraction on report failure |
| Insufficient | No usable text, blocked extraction, or fixture without snapshot | Explicit unavailable/insufficient report; evidence remains readable | No model spend |
| Provider unavailable | Disabled, missing configuration, timeout, budget rejection | Visible report state and useful evidence fallback | Bounded error; no secret leakage |
| Invalid output | Malformed JSON, unknown references, unexpected model | Reject interpretation; persist failure reason | Never display unvalidated output |
| Duplicate/crash | Redelivery, stale lease, restart after dispatch | Reuse committed report; fence stale writes; mark unresolved dispatch uncertain | No blind paid-call replay |
| Unauthorized | Another owner or guest requests full report | Existing access policy applies; no report/evidence disclosure | Consistent denied/not-found response |

</frozen-after-approval>

## Code Map

Root: `C:/Users/eidel/Desktop/VCT Connect/tmp/oct6-text-report-worktree`; branch `codex/oct6-text-report`, baseline `1a98e42`. Paths below are relative. Original edits remain preserved.

- `backend/app/extraction/contracts.py`: SupplierData, coverage/provenance.
- `backend/app/storage.py`: immutable `_complete_processing`; owned `_SELECT`; extraction claims skip completed analyses.
- `backend/app/main.py`: synchronous import/capture; authorized polling.
- `backend/worker/main.py`, `backend/app/queue.py`: local/Azure leases and fencing.
- `backend/app/config.py`, `.env.example`: no existing AI configuration.
- `backend/db/migrations/0001`–`0009`: extraction persistence only.
- `frontend/apps/web/app/{page,extraction-evidence}.tsx`: real evidence; fixture-only DemoReport.
- `frontend/packages/{contracts,api-client}/src/index.ts`: contracts/polling, no report state.

## Tasks & Acceptance

**Execution:**
- [x] `backend/db/migrations/0010_text_reports.py`, `backend/app/storage.py` — snapshot-linked jobs, dispatch ledger, reports, atomic enqueue, deduplication and fenced settlement.
- [x] `backend/app/interpretation/{contracts,provider,service}.py`, config, `.env.example` — bounded schemas, Vietnamese prompt, LLMProvider/YEScale via httpx, validation and fail-closed spend controls.
- [x] Backend API/worker — enqueue eligible owned imports/captures/extraction; expose report status; drain jobs in local/Azure workers.
- [x] Frontend contracts/client, page, new `text-report.tsx`, status helpers — poll after extraction completes; render citations/actions/limitations, evidence fallback and fixture labels.
- [x] Backend provider/report/tracer/PostgreSQL/migration tests; frontend report/status/client tests and test script — verify matrix, ownership, persistence and fencing.
- [x] `README.md`, rehearsal artifact — configuration, activation requirements, prepared evidence and fallback; record observed checks.

**Acceptance Criteria:**
- Given saved Chinese evidence and configured provider, when processing finishes, then reopening shows the persisted Vietnamese report and inspectable citations.
- Given completed extraction and pending interpretation, when polling continues, then report progress remains visible without changing extraction status.
- Given partial evidence, when interpretation succeeds, then unknowns remain explicit and reliability scores are not claimed as computed.
- Given restart/redelivery, when processing resumes, then committed reports remain stable and uncertain attempts require reconciliation.

## Implementation Notes

- Implemented snapshot-linked report jobs with a one-dispatch ledger, atomic extraction completion/enqueue, immutable committed reports, lease fencing, and uncertain crash recovery. Ledger reservations survive analysis deletion.
- Configurable backend-only YEScale chat endpoint requires exact model ID/version, conservative configured rates, budget, byte/token limits and deadline. Usage estimates are labeled; actual cost remains unknown. Selected text is minimized, citations are checked, and scores/fixture findings are excluded.
- Existing authorized analysis polling exposes independent report state; local/Azure workers drain report jobs. Buyer polling continues after extraction and renders Vietnamese findings, inspectable citations, limitations, actions and fallback evidence.
- Observed verification: 1,260 backend regressions passed (357 configuration-dependent skips); 97 PostgreSQL/migration regressions passed (5 skips); 77 frontend tests, typecheck, web and extension build passed. Final focused provider/report run: 30 passed. Extension build used a test-only public key; no live activation or deployment occurred.
- Full rehearsal and remaining live quality/cost/model-version/Azure acceptance limits are recorded in `rehearsal-oct6-text-report.md`. The frozen intent and constraints are unchanged.

## Plan Change Log

## Review Triage Log

### Review 1 — 2026-10-05

Every matrix row has executed coverage: saved/report reopening and unauthorized reads in PostgreSQL; insufficiency/configuration/budget/timeout and invalid output in provider/service tests; committed redelivery, expired dispatch and stale leases in PostgreSQL. Parent reran the 30 provider/service cases successfully. Integration coverage gaps below require additional tests.

| Finding | Verdict | Route | Evidence |
|---|---|---|---|
| Blind 1: disabled jobs drained | false | reject | UNAVAILABLE is the approved visible configuration failure; README documents ledger-checked operator requeue. It is not permanent loss of evidence or a promised automatic activation path. |
| Blind 2: missing attribute/shipping labels | medium | patch | Alibaba stores name/value attributes and Taobao stores shop_shipping_display_text; the whitelist demonstrably drops them. Preserve these business keys. |
| Blind 3: oversized input rejected | false | reject | INPUT_LIMIT is an intentional bounded failure with evidence fallback, covered by no-spend tests. Unlimited snapshot coverage is not promised; selected-text limitations are displayed. |
| Blind 4: quantities redacted | medium | patch | Parent reproduced MOQ 1000 2000 3000 becoming redacted contact text. Correct phone matching without stripping business quantity groups. |
| Blind 5: synchronous report work | false | reject | Sequential bounded job execution is the existing worker contract, not a demonstrated starvation or lock-renewal failure. Separate execution capacity is a throughput optimization; finite workers and dispatcher replicas remain available. No concurrent-extraction latency invariant was established. |
| Blind 6: wrong language accepted | medium | patch | Parent confirmed non-Vietnamese finding text passes validation. Add conservative local language screening; retain live quality acceptance limits. |
| Blind 7: score paraphrases accepted | high | patch | Parent reproduced risk/reliability claims with intervening words. Broaden existing score assertion rejection. |
| Blind 8: summary has no references | false | reject | Findings have mandatory validated citations; summary is an overview of the report. The API does not claim semantic entailment or cite every prose field. Actual factual quality is explicitly unverified pending model evaluation, and an invented summary-reference schema is not established by this finding. |
| Blind 9: malformed choice shape | medium | patch | Parent reproduced AttributeError for choices:[null]. Correct nested shape validation and retain safe trace metadata. |
| Blind 10: timeout trace missing | low | reject | Outer deadline can discard partial response metadata, but dispatch ID, model, timestamps and reservation are durable; no paid retry occurs. A cross-thread metadata interface adds complexity beyond a direct correction for a reconciliation convenience. |
| Edge 1: escaped credential bypass | high | patch | Parent used a synthetic key encoded with Unicode escapes and reproduced READY. Scan decoded validated output before persistence. |
| Edge 2: score assertion bypass | high | patch | Same demonstrated score-validator defect as Blind 7. |
| Edge 3: English report accepted | medium | patch | Same language-validator defect as Blind 6; schema alone does not screen language. |
| Edge 4: reopening language claim | medium | patch | Persisted READY can contain non-Vietnamese prose; same cause as Edge 3. |
| Edge 5: computed reliability claim | high | patch | Same score-validator defect; unsupported prose can contradict the standard limitations. |
| Gap 1: continuous worker coverage | medium | patch | Verified gap evidence: direct service tests and finite-job test do not exercise continuous draining of report-only imports. Add a bounded loop integration test. |
| Gap 2: buyer page mounting coverage | medium | patch | Verified gap evidence: static TextReport tests bypass the actual buyer page. Add rendering through Page with an owned READY response. |
| Gap 3: migration backfill coverage | medium | patch | Verified gap evidence: new saved imports happen after migration; seed eligible/ineligible rows under 0009 and verify upgrade job membership. |
| Intent: live operational journey | false | reject | Descriptive divergence matches explicit separate activation/deployment gate; implementation does not claim live acceptance. |
| Intent: substantive prose quality | false | reject | Fake-provider tests establish integration; live factual/language quality remains explicitly pending. Deterministic language screening above addresses the reproducible mechanical defect. |
| Intent: citation entailment | false | reject | Reference validity is verified; source claims are labeled unverified and semantic entailment is not claimed as a passing check. |
| Intent: authenticated browser journey | false | reject | Manual browser acceptance is explicitly unverified. Buyer page mounting gap is accepted separately above. |
| Intent: useful actions/limitations | false | reject | Report represents advisory text as intended; semantic usefulness requires live model acceptance and is not claimed from nonempty arrays. |

Survivors grouped by cause: evidence projection, phone redaction, language screening, score rejection, nested provider shape, decoded credential rejection, and three integration coverage gaps. All are local corrections to demonstrated states or tests; no new public API or intent decision is needed. No deferred code findings.

Resolution: all nine correction groups were applied. Business labels/shipping and quantity groups survive projection; conservative Vietnamese screening, numeric/written score rejection and decoded credential screening reject reproduced bad outputs; malformed provider shapes retain safe trace. New tests exercise continuous local/Azure/dispatcher draining, actual mounted Page and 0009→0010 backfill. jsdom is a locked development-only test dependency.

Parent verification after patches: full PostgreSQL-enabled backend run had 1,383 passes, 261 gated skips and 22 setup errors solely from denied existing pytest temporary directories. All 22 affected cases passed unchanged with a new checked workspace temporary path (23 cases in that rerun, one overlapping). Independent migration run: 23 passed. Final validator correction includes written-number assertions: 79 focused cases passed. Across these runs, 1,409 distinct backend cases have passing evidence. Frontend: 78 tests, typecheck, web/extension builds and credential scan passed; the build used synthetic keys. Initial sandbox frontend test failure was esbuild directory access and passed unchanged outside that sandbox. No code defects or required checks remain unresolved; live quality/authentication/Azure acceptance stay unverified.

## Design Notes

Separate report state preserves extraction. Persist dispatch before external calls; crashes become uncertain. Reserve configured spend before dispatch; label estimates and reconcile usage. Do not claim exactly-once billing.

## Verification

- Backend pytest: provider/report/tracer suites and relevant regressions using existing environment against this checkout.
- Disposable PostgreSQL: migrations, ownership, atomic enqueue, redelivery, stale claims.
- Frontend: `npm test`, `npm run typecheck`, `npm run build`; include new tests.
- Rehearse saved evidence → progress → report → citation and fallback using fake provider; label as integration verification.
- Live quality/latency/cost and Azure acceptance await credentials, model pin, budget and authorized release.
