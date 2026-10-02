---
title: 'Add the Alibaba source adapter'
type: 'feature'
ticket: '4'
created: '2026-10-01'
status: 'built'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['blind-hunter', 'edge-case-hunter', 'verification-gap', 'intent-alignment']
review_loop_iteration: 0
baseline_revision: 'e452afdb0a1477ed1adb381bec7da973a1e303a9'
context:
  - 'C:/Users/eidel/Desktop/VCT Connect/_bmad-output/initiative-vct-connect-year-one/epic-extraction/epic-extraction.md'
  - 'C:/Users/eidel/Desktop/VCT Connect/_bmad-output/initiative-vct-connect-year-one/epic-extraction/alibaba-sample-audit.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The queued extraction pipeline supports 1688 and Taobao, but rejects Alibaba supplier/product links. Buyers cannot obtain Alibaba evidence or a source-specific access explanation.

**Approach:** Add an Alibaba adapter grounded in representative product and supplier pages, reusing bounded HTTP extraction, SupplierData v1, durable owner-scoped snapshots and source-aware presentation. Access challenges remain explicit terminal outcomes.

## Boundaries & Constraints

**Sample decision:** Use the supplied product `1600147809763` (supplier `beautiy`) and independent profile `dgxuandele`, audited in the context file. They ground separate layouts; do not associate their supplier evidence.

**Always:** Preserve fixture, 1688/Taobao, seven extraction statuses, the 12 optional evidence fields, explicit unknowns, authorization, quotas, queue settlement and immutable replay. Bind requested product/supplier identity and canonical hints; reject ambiguous/conflicting evidence. Reuse checked public-IP connections, hostname TLS, per-hop URL checks, 2 MB cap, 25-second shared deadline and conservative transient retries. Retain only selected public source values, accessible review bodies, original response-byte hash, method/mode/version and timestamp. Keep source company claims distinct from independently verified facts. Keep the accepted Taobao shop capture deferral.

**Never:** Execute page scripts, collect source credentials/cookies/session state, bypass challenges, fetch unrelated hosts/media, infer missing fields or scores, alter existing migrations, add Alibaba upload/capture, launch Playwright, merge evidence, or claim inaccessible public pages produced usable snapshots.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Outcome | Handling |
| --- | --- | --- | --- |
| Public product/profile | Audited URL and identity-bound accessible HTML | Versioned ALIBABA snapshot with selected evidence | Missing fields remain unknown |
| Sparse page | Bound page omits fields/review bodies | PARTIAL with honest coverage | No invented reviews or zero-risk signal |
| Unsafe input/hop | Unsupported URL, private IP, foreign or changed identity | Admission rejection or fixed terminal outcome | No request to rejected target |
| Access wall | HTTP/access HTML or approved login destination | AUTH_REQUIRED/BLOCKED, no snapshot | No bypass or retries of access walls |
| Changed content | Ambiguous identity, malformed structures, inactive/unrelated content | Fixed PARSE_FAILED or partial scoped evidence | No exception/private-state leakage |
| Transport failure | Timeout/transient error/oversize body | Existing bounded retry and failure contract | No incomplete stream parsed |
| Consumer boundary | Alibaba HTML import or extension capture request | Explicit unsupported-source rejection | Preserve 1688/Taobao recovery |
| Ownership/replay | Another owner or duplicate queue delivery | 404 or unchanged immutable snapshot | Atomic completion and platform isolation |

</frozen-after-approval>

## Code Map

- `backend/app/extraction/urls.py` — add audited Alibaba canonicalization/identity; extend platform dispatch without widening other platforms.
- New `backend/app/extraction/alibaba.py` — public parser and fetch adapter; reuse `fetch.py::bounded_extract` and safe utility functions from `offer1688.py`.
- `backend/app/extraction/contracts.py` — SupplierData/status/coverage already shared; ALIBABA is present, retain coverage semantics; extend narrowly typed display fields only where audited evidence requires it.
- `backend/app/extraction/__init__.py`, `backend/worker/main.py::_compute_claim` — export adapter; explicit three-platform dispatch after fixture branch.
- `backend/app/main.py` — shared submission admission; explicitly reject unsupported Alibaba import/capture before legacy dispatch.
- `backend/app/storage.py::_complete_processing` — existing source/platform/mode/method validation and transactional supplier/snapshot/review storage; no schema change expected.
- `frontend/apps/web/app/{source-url.ts,analysis-status.ts,extraction-evidence.tsx,page.tsx}` — Alibaba safe links, labels, terminal guidance and URL submission; retain supported import/capture wording.
- `backend/tests/`, web status/render tests — cover admission, worker, ownership, replay, source safety and presentation; align `frontend/packages/contracts/src/index.ts` where needed.

## Tasks & Acceptance

**Execution:**
- [x] `alibaba-sample-audit.md` — audit recorded supplied product/profile mappings and exclusions; derive sanitized fixtures and compare against originals.
- [x] `backend/app/extraction/{urls.py,alibaba.py,__init__.py}` — implement audited admission/parser/HTTP adapter with explicit partial and failure outcomes.
- [x] `backend/worker/main.py`, `backend/app/main.py` — connect queued dispatch; guard unsupported recovery endpoints.
- [x] `frontend/apps/web/app/` — expose supported Alibaba submission and traceable evidence without advertising unimplemented recovery.
- [x] `backend/tests/test_alibaba.py`, fixtures, auth/PostgreSQL tests and frontend tests — cover every matrix row and 1688/Taobao regressions.

**Acceptance Criteria:**
- Given representative saved product/profile HTML, when parsed through an accessible mocked public response and queued completion, then owner polling shows bound ALIBABA evidence with correct provenance and coverage.
- Given a genuine live Alibaba URL, when the deployed pipeline completes, then it stores a traceable snapshot or the observed explicit access/failure status.
- Given existing fixture and 1688/Taobao workflows, when regressions run, then their authorization, recovery, persistence and presentation remain valid.

## Implementation Notes

Initial investigation checkpoint: tracked tree was clean on main at the recorded baseline; existing user samples, PDFs, skills, and temporary files remained untracked and preserved. Runtime implementation had not started at that checkpoint.

Implementation checkpoint: the audited Alibaba forms now enter queued public
HTTP extraction and immutable owner-scoped storage. The parser selects public
detailData/shopBizData paths and retains distinct supplier/product scopes.
Alibaba import/capture are explicitly rejected before legacy recovery dispatch.
No schema or status-contract change was needed. The bounded fetcher has an
optional cookie-decline policy used by Alibaba; existing adapters retain their
configured behavior. A valueless HTML style attribute in the original product
required the shared inactive-node helper to treat that attribute as empty.
The sanitized fixtures retain selected JSON/DOM structures; original samples stay untracked.

## Plan Change Log

## Review Triage Log

### Review pass 1

Verdicts: high 2; medium 15; low 0; false 5; maybe-false 0. All surviving groups are direct corrections to demonstrated states or missing regression assertions; no public surface changes.

| Finding | Verdict | Route | Evidence |
| --- | --- | --- | --- |
| B1 | medium | patch | A valid 400-digit JSON integer escapes _number as OverflowError in a reproduction; the parser only catches ValueError/TypeError. |
| B2 | high | patch | Nested csrf-shaped objects in selected localCompanyJoinYears or localized priceRangeLow survive into raw evidence. A scalar-shape guard on selected scalar paths is a direct correction. |
| B3 | high | patch | An otherwise valid locale offer URL with a query token is accepted and retained verbatim. Only public identity components are needed; queries must be removed from selected raw URL evidence. |
| B4 | medium | patch | Alias and Reflect.set writes to the source model reproduce PARTIAL. Add targeted guards for the demonstrated unresolved writes; the existing ambiguity policy already rejects direct mutations. |
| B5 | medium | patch | A throwing statement before the audited assignment still yields PARTIAL. Reject demonstrated terminating control flow in its prefix. |
| B6 | false | reject | The arbitrary regex-bearing prefix is not an audited wrapper. Its fixed PARSE_FAILED result is permitted for changed/unsupported layouts; no supported original sample is affected. |
| B7 | medium | patch | A matching list appended outside the original product-review component is collected. The original review body has an audited .product-review ancestor; scope selection to that component and preserve the ancestor in the sanitized fixture. |
| B8 | medium | patch | A simple inline stylesheet .secret {display:none} hides a matching review container but the parser retains it. Exclude statically identifiable hidden DOM using the existing CSS selector engine; no external CSS or script evaluation. |
| B9 | medium | patch | A canonical link inside a hidden div causes PARSE_FAILED. The identity-hint loop omits the existing active-node predicate. |
| B10 | medium | patch | Usable stale model data suppresses explicit access/login title signals as well as password checks. Honor explicit gate titles while keeping ordinary sign-in navigation and non-gating forms compatible with usable public evidence. |
| E1 | medium | patch | Duplicate numeric-overflow finding; reproduction escapes before the fixed parser failure handling. Group with B1. |
| E2 | medium | patch | MOQ integer 9007199254740993 normalizes to 9007199254740992 due to float conversion. Integer-valued source fields must preserve exact values. |
| E3 | medium | patch | The >>= reproduction remains PARTIAL; the mutation operator pattern omits several assignment operators. Group with the source-mutation guard correction. |
| E4 | medium | patch | Alias/Reflect writes reproduce the source ambiguity, and Object.assign(window,{detailData:...}) also bypasses the current target guard. Group with B4. |
| E5 | medium | patch | The provided-client path bypasses the newly added cookie policy, although the default production path declines cookies. The false flag must also govern the existing injectable client path. |
| E6 | medium | patch | With only homeUrl supplying a valid supplier host, platform_supplier_id lacks selected raw binding. Retain the validated public hostname/path components without its navigation query. |
| V1 | medium | patch | Pre-verified regression gap: fixture parsing and persistence tests do not assert exact profile revenue/reorder/dispatch metric values and scopes. Assert the audited source claims. |
| V2 | medium | patch | Pre-verified regression gap: the Alibaba rendering case has null quotation data. Add a populated product quotation case asserting range/currency/unit/MOQ. |
| I1 | false | reject | Deployed flow is a pending release gate, explicitly disclosed in the plan and provenance. The implementation does not claim it ran deployed smoke. |
| I2 | false | reject | Original-versus-fixture equivalence was directly executed and recorded. Original browser captures remain private/untracked by intent; an always-on raw-file test is not required. |
| I3 | false | reject | Local API/PostgreSQL ownership and static presentation checks are the current planned gates; the deployed buyer journey remains subsequent release verification. No claim of a completed browser journey was made. |
| I4 | false | reject | The approved frozen block and audit bind support to representative audited URL forms; neither promises every Alibaba link form or browser recovery. |

Patch outcome: all surviving findings were corrected by the original implementation agent. Targeted verification passed 134 backend cases and 16 frontend rendering cases. Root inspected the complete patch diff and reran the full verification gates below; no review finding remains unresolved. Static visibility handling covers identifiable active inline stylesheet rules and deliberately does not evaluate conditional CSS, external stylesheets or scripts.

## Design Notes

Use audited `detailData`/Product JSON-LD and `shopBizData` module selections, never whole models. Require agreeing product identities and profile subdomain binding; saved-from comments are audit metadata only. Exclude inactive DOM, unrelated recommendations and account/chat state. Navigation/login widgets and ordinary security scripts alone are not access walls. Field mappings and fixtures are specified in the audit.

## Verification

- `.venv/Scripts/python.exe -m pytest backend/tests` against isolated PostgreSQL; parser/fetch/admission and owner/replay cases.
- `npm test --prefix frontend`, `npm run typecheck --prefix frontend`, `npm run build --prefix frontend`, `scripts/scan_frontend_secrets.py`, and `git diff --check`; all pass.
- Direct audit of original approved samples versus sanitized fixtures; record real anonymous access outcomes separately.
- After review and release approval, existing CI/Azure deployment and bounded deployed smoke; pause for missing credentials or required user action.

Implementation results (2026-10-01): the full backend suite against a fresh
isolated PostgreSQL database passed 490 tests, with the sole skipped test being
the explicitly gated live Azure Service Bus check. Detailed evidence is retained
in `tmp/alibaba-backend-junit.xml` and `tmp/alibaba-backend-tests.log`.
The final top-level assignment-wrapper guard was additionally verified by all
93 Alibaba parser/fetch tests and another original-versus-fixture comparison;
that targeted JUnit report is `tmp/alibaba-parser-final-junit.xml`.
All 69 frontend tests, type checking, web/extension production build, configured
credential scan and `git diff --check` passed. Frontend test/build logs are in
`tmp/alibaba-frontend-tests.log` and `tmp/alibaba-frontend-build.log`.
Original-versus-fixture normalization matches; the anonymous live adapter reports
`BLOCKED / ACCESS_CHALLENGE` for both approved URLs with no snapshots (outcomes
only in `tmp/alibaba-live-outcomes.json`). Review, release approval, deployment and
deployed smoke remain subsequent workflow steps.

Post-review results (2026-10-01): 536 backend tests passed against a fresh isolated local PostgreSQL database; the single opt-in live Azure Service Bus test was skipped. Every frozen matrix row has executed passing evidence, recorded in `tmp/alibaba-matrix-audit.md` against `tmp/alibaba-backend-junit.xml`. All 70 frontend tests, type checking, web/extension production build, configured credential scan and staged/unstaged whitespace checks passed. Build initially hit a sandbox filesystem denial in esbuild; the same command succeeded with approved elevated execution. Logs: `tmp/alibaba-review-backend-tests.log`, `tmp/alibaba-review-frontend-tests.log`, `tmp/alibaba-review-frontend-typecheck.log`, `tmp/alibaba-review-frontend-build.log`. Root independently compared the two original samples with sanitized fixtures: normalized supplier evidence and reviews match, at 10/12 product and 9/12 profile coverage. Local implementation and review are verified; release approval, deployment and deployed smoke remain pending.

### Approved release closeout (2026-10-02)

The user approved pushing and deploying Story 2.4, and deferred manual browser acceptance in favor of Story 2.5 development. Commit `b9d93d90a63b6ffad582352520deb6a963c94963` was pushed to main. [CI](https://github.com/vuongc4298/vct-connect/actions/runs/36895896016) and [Deploy dev](https://github.com/vuongc4298/vct-connect/actions/runs/36896852899) succeeded, including ingress, credential-response and deployed guest-fixture queue checks.

Two additional guest Alibaba analyses completed through the deployed queue, each with attempt_count 1, BLOCKED / ACCESS_CHALLENGE, and no supplier snapshot: product `aefa6d41-5899-4a52-b121-a80e7a32c55b` and profile `a1745a35-b430-46bd-8f75-197446c2bc9b`. Outcome metadata is retained locally in `tmp/alibaba-deployed-outcomes.json`. This establishes deployed admission, dispatch, access classification and owner polling; it does not claim successful public extraction or a signed-in browser journey. Manual regression checks for supported 1688/Taobao HTML import and extension extraction, plus signed-in Alibaba URL presentation, remain explicitly deferred. Alibaba HTML import/capture remains unsupported by this story. The prior Taobao shop capture deferral is preserved.
