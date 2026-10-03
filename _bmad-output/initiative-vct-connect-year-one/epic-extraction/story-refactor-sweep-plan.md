---
title: 'Refactor sweep'
type: 'refactor'
ticket: '8'
created: '2026-10-03'
status: 'built'
baseline_revision: '90bead71cd8073f352fb6b6801099e3c784d120c'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['blind-hunter', 'edge-case-hunter', 'verification-gap', 'intent-alignment']
review_loop_iteration: 0
context:
  - '_bmad-output/initiative-vct-connect-year-one/epic-extraction/epic-extraction.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The three HTTP adapters, extension normalizers, replay, and extension merge repeat SupplierData coverage and status assembly. Taobao, Alibaba, browser handling, and replay also import generic parsing helpers from the 1688 or Taobao adapter, making shared behavior appear platform-specific. A future field or guard change could diverge between paths.

**Approach:** Move genuinely shared evidence validation, DOM handling, and coverage assembly into explicit shared modules; keep audited selectors and identity rules in their platform adapters. Retain the same outcomes and provenance for existing inputs.

## Boundaries & Constraints

**Always:** Preserve SupplierData v1, the 12-field denominator and existing presence rule, seven statuses, reason codes, platform identity binding, raw selection/replay versions, immutable snapshot semantics, browser limits, and extension secret rejection. Keep missing evidence unknown and retain review/product deduplication and provenance.

**Never:** Broaden accepted URLs or page models, execute source scripts in HTTP parsing, weaken access-wall or unsafe-destination handling, change database/API/frontend schemas, or collect new page state. Do not turn the sweep into a new extraction feature.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
| --- | --- | --- | --- |
| Audited public layouts | Saved 1688 offer, Taobao item/shop, Alibaba product/profile | Same status, SupplierData fields, coverage, bounded reviews, raw hash and selected fields | No new field claims |
| Sparse or invalid source | Missing fields, conflicting identity, login/CAPTCHA, unsafe redirect, timeout | Same explicit status/reason and no unsupported snapshot | No fallback past access or safety guards |
| Browser, extension, replay | Render gain, selected page capture, retained raw fields | Same method/version, provenance, merge deduplication and coverage | Reject secrets and incompatible raw revisions |

</frozen-after-approval>

## Code Map

- `backend/app/extraction/contracts.py` — `EVIDENCE_FIELDS` and SupplierData shape; add a small shared presence/coverage/assembly helper based on the current 1688 `_present` rule, without hard-coded `12`.
- `backend/app/extraction/offer1688.py` — generic `MalformedPage`, `_field`, `_object`, `_string`, `_text`, `_present`, `_validate_json_evidence` currently live beside 1688 selectors. Move only generic parts to a shared evidence module; preserve adapter/public imports used by tests.
- `backend/app/extraction/taobao.py` — `_tree`, `_active`, `_scripts`, `_prune_dom` are consumed by Alibaba and browser code. Move shared DOM mechanics to a neutral module while keeping Taobao model and URL binding in place; retain `_tree` compatibility for `test_alibaba.py`.
- `backend/app/extraction/{alibaba,extension1688,extensiontaobao,renormalize,extension_merge,browser,browser_runner}.py` — switch shared imports and repeated coverage assembly, preserving parser-specific validation, replay revision checks, browser isolation, and merge provenance.
- `backend/app/extraction/fetch.py` — already centralizes bounded HTTP transport; leave retry, DNS, redirect and cookie policy unchanged.
- `backend/tests/{test_extraction,test_taobao,test_alibaba,test_browser_fallback,test_renormalize,test_extension_merge,test_postgres_tracer}.py` — existing representative fixtures and queued owner/replay checks; add contract parity assertions where current matrix misses a path.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/extraction/contracts.py` and new shared helper modules — centralize evidence presence, coverage/status assembly and generic parsing/DOM utilities without changing output keys or validation.
- [x] `backend/app/extraction/{offer1688,taobao,alibaba,extension1688,extensiontaobao,renormalize,extension_merge,browser,browser_runner}.py` — rewire callers, remove repeated coverage formulas and cross-adapter utility imports; preserve stable entry points.
- [x] `backend/tests/` — compare representative outputs and failure classifications before/after the refactor, including sparse fields, browser gain, raw replay, extension merge and selected-text rejection.

**Acceptance Criteria:**
- Given each saved platform layout, when parsed through public HTTP, then the resulting status, SupplierData evidence/coverage, raw selections and provenance match the baseline.
- Given sparse, blocked, invalid, or timed-out input, when extraction runs, then the same status and reason are returned with no new accepted evidence.
- Given extension capture or raw replay, when merged or re-normalized, then coverage, source labels, bounded deduplication and revision guards match the baseline.
- Given the reviewed change in CI and the approved development release, when the deployed three-platform queue matrix and extension merge checks run, then they pass without contract or failure-behavior drift.

## Implementation Notes

- Implemented on `codex/story-2-8-refactor-sweep` against the specified baseline `90bead71cd8073f352fb6b6801099e3c784d120c`. Read this plan and its complete frontmatter context before changes.
- `contracts.py` now owns `evidence_present`, `evidence_coverage`, `assemble_supplier_data`, and `evidence_status`; all seven normalization/merge paths use the canonical coverage calculation. Numeric zero remains evidence, and denominator/order derive from `EVIDENCE_FIELDS`.
- New `evidence.py` contains the existing generic readers, JSON persistence validation, and shared `MalformedPage`. New `dom.py` contains existing inert-source tokenization, visibility/script/pruning mechanics, static stylesheet hiding, and the already-shared login predicate. Adapter utility names remain aliases for compatibility.
- Rewired all nine listed callers. Platform model parsing, selectors, identity binding, revision guards, secret rejection, deduplication, and merge provenance remain local. Replay retains its platform-specific validation imports. Browser eligibility/gain retains its additional empty-object exclusion; SupplierData v1 coverage preserves the original 1688 presence rule.
- Captured 41 full baseline outcome JSON records before moving utilities, stored in `backend/tests/fixtures/refactor_baseline.json`. Added `test_refactor_parity.py` to compare HTTP for all five saved layouts, uploads, HTTP/browser replay, sparse evidence, simulated browser gains, access failures, malformed pages, timeouts, unsafe redirects, extension captures and merges, including raw hashes and provenance. Additional assertions cover selected-text rejection, zero values, the browser empty-object guard, SUCCESS coverage, and compatibility aliases.
- The optional bmad-build launcher failed fetching Jinja2 from PyPI under sandbox network restrictions. Implementation followed this user-designated plan directly.

## Plan Change Log

## Review Triage Log

### Review pass 1 — 2026-10-03

All four lenses completed before triage. Individual verdicts: 8 medium, 4 low, 9 false; no high or unverified finding. Four patch groups and five pre-existing CSS groups survive; the two duplicate coverage findings share one patch. Verification-gap reported no gaps.

| Finding | Verdict | Route | Evidence / action |
| --- | --- | --- | --- |
| B1: extra evidence keys override contract/provenance/coverage | false | reject | Every production assembly caller constructs only the canonical evidence fields; user source keys are selected before assembly. No accepted input reaches the proposed reserved-key state. |
| B2: sparse mappings raise KeyError | false | reject | Production callers initialize every canonical field, as the previous inline comprehensions required. Loud failure for a malformed internal mapping does not change accepted input behavior. |
| B3: extension merge coverage changes for empty inherited values | medium | patch | Replayed the old merge module from the canonical baseline against the same valid normalized mappings: inherited `categories=[]` yields 0.25 before and 0.1667 after. Preserve extension's existing None-only rule in the shared calculation and add regressions. |
| B4: important stylesheet priority is discarded | medium | defer | Reproduced a visible login wall disappearing with `display:block!important;display:none`. The relocated function's AST is identical to the baseline; pre-existing static CSS limitation. |
| B5: simulated Taobao gain injects reviews instead of rendered shelf products | false | reject | The injected callback intentionally tests result selection, not rendering. Actual three-platform gain tests and queue checks ran successfully with the real renderer; no claim that this mock represents a DOM capture. |
| B6: browser replay examples do not replay newly rendered evidence | low | patch | The new golden cases cover compatible retained shapes separately from simulated gain; the exact real gain-to-replay chain is not asserted. Add assertions to the existing real Chromium gain test using its actual selected raw fields. |
| B7: baseline key deletion silently removes coverage | low | patch | Parametrization reads only fixture keys. Assert equality of generated and recorded case sets before comparisons. |
| B8: baseline capture cannot be reproduced with the current module at the old revision | low | patch | Shared helper imports at module load are absent in the recorded revision. Localize those imports and document an isolated baseline capture procedure using the existing outcome generator. |
| B9: planned full-suite command is presented as completed | false | reject | The command list describes expected checks; the result section explicitly distinguished pending gates. Parent results now establish 839 backend, 78 browser and 12 real queue passes. |
| B10: in-review status differs from the historical in-progress note | low | reject | This is an earlier handoff note superseded by current frontmatter and parent verification. Its proposed fix edits the plan; rejected per workflow. |
| E1: missing canonical field raises KeyError | false | reject | Same complete-mapping invariant and caller trace as B2; malformed internal mappings are not accepted source evidence. |
| E2: reserved keys overwrite generated metadata | false | reject | Same selected-field caller trace as B1; no source or request mapping is spread directly into assembly. |
| E3: inline display cascade is not resolved | medium | defer | Reproduced `display:none;display:block` hiding a visible login wall. The `active` function is AST-identical to the baseline. |
| E4: visible child inside hidden ancestor is pruned | medium | defer | Reproduced explicit `visibility:visible` child text disappearing under a hidden ancestor. Existing token-based ancestor visibility rule is unchanged. |
| E5: print stylesheet hides screen content | medium | defer | Reproduced a print-only hiding rule removing a screen login wall. Existing stylesheet helper does not evaluate media applicability. |
| E6: later stylesheet display rule cannot undo hidden marker | medium | defer | Reproduced `display:none` followed by `display:block` leaving the node hidden. Group with B4: existing static stylesheet cascade/priority handling. |
| E7: percentage zero opacity retains invisible text | medium | defer | Reproduced `opacity:0%` text surviving pruning. Existing stylesheet regex does not recognize percentage zero; the moved function is unchanged. |
| I1: canonical policy differs from extension's old presence rule | medium | patch | Duplicate of B3, confirmed against the original merge implementation. Preserve the existing extension rule rather than redefining v1 evidence. |
| I2: new browser examples use callbacks and synthetic provenance | false | reject | Actual Chromium and queue gates ran with zero skipped covering cases. B6 separately adds the exact real render-to-replay assertion; simulated cases do not replace the actual runtime gate. |
| I3: finite fixture tests do not prove future rule propagation | false | reject | Future behavior is not a currently failing input. Shared call sites are now central; browser's deliberate extra empty-object exclusion is preserved and tested. |
| I4: finite new cases omit some identity/revision/persistence scenarios | false | reject | Existing regressions for these behaviors ran in the full 839-test database suite, alongside actual Chromium gates. The baseline matrix supplements those tests. |

Grouped patches: extension coverage parity (B3/I1), real browser gain-to-replay coverage (B6), baseline case-set coverage (B7), reproducible baseline capture (B8). The five CSS groups were confirmed as baseline behavior, not introduced by relocation.

### Post-patch verification — baseline portability

- P1 — medium / patch: Independent reproduction from the archived original modules exposed a platform-specific fixture-byte mismatch: the Windows working-tree 1688 HTML has CRLF while its Git blob/Linux checkout has LF. Four golden raw hash assertions differ although all selected and normalized fields agree. Canonicalize only the parity test's input bytes to LF and regenerate its recorded outcomes from archived original production code; preserve response-byte hashing in production.
- Measured-byte clarification: the archived baseline fixture actually contains eight CRLF sequences (hash `4102ff69e361897470b45ba190ece099e42e77d086e10da82a140cccc7a43404`), while the current fixture contains LF (hash `d929776c58087c17c70132423829ab26ec74cc3b5ea10b72c3099a57c892bf70`). The initial direction labels were reversed; canonical LF is now supplied consistently by the test. Parent independently reproduced all 41 records using isolated archived original modules after the correction.

## Design Notes

Keep one canonical coverage function returning ordered `missing_fields`, `completeness_denominator`, and `completeness`; use the existing presence rule rather than truthiness so numeric zero remains evidence. Restrict shared modules to mechanisms already used across adapters; platform-specific field selectors and URL checks stay local. Baseline fixtures and prior Story 2.7 deployed/CI records define parity, not a license to accept new source shapes.

## Verification

**Commands:**
- `.venv/Scripts/python.exe -m pytest backend/tests/test_extraction.py backend/tests/test_taobao.py backend/tests/test_alibaba.py backend/tests/test_browser_fallback.py backend/tests/test_renormalize.py backend/tests/test_extension_merge.py -q` — all platform/merge/replay regressions pass.
- `.venv/Scripts/python.exe -m pytest backend/tests -q` — queued persistence and API regressions pass against a dedicated test database.
- `git diff --check` — no whitespace errors; compare fixture outcome JSON/provenance before and after.
- Hosted CI and approved dev deployment — three-platform queued extraction/status matrix and extension merge smoke pass; record run links and any unavailable live-source paths.

**Local verification (2026-10-03):**
- Before refactoring, the six listed focused regression modules passed: **604 passed, 31 skipped**. The added baseline and rejection checks also passed against the original adapter implementation before relocation.
- After the final patch, the six listed modules plus `backend/tests/test_refactor_parity.py` passed: **661 passed, 31 skipped**. All 41 baseline outcomes matched, including normalized evidence, raw selections, hashes, statuses/reasons, versions and provenance. The 31 skips are opt-in actual Chromium checks.
- Against the user-provided disposable local PostgreSQL database, `backend/tests/test_postgres_tracer.py -k 'public_browser or extension or renormaliz or three_platform or queued' -q` passed: **27 passed, 42 deselected**. One existing Starlette/httpx deprecation warning. These checks cover queue ownership and immutable browser/replay/extension persistence.
- `git diff --check` passed. No fetch transport, URL normalization, database/API/frontend schema, browser isolation limit, or version change.
- Per the user's verification environment update, the parent will run the full backend/database suite and actual Chromium verification after handoff. Hosted CI, approved development release and deployed three-platform/extension smoke remain pending; no run links or live-source result claims are available for this patch. Story status stays in progress until those gates are recorded.

**Parent verification (2026-10-03):**
- Full backend suite on a disposable PostgreSQL 16 database: **839 passed, 32 skipped**, 221.36 seconds. The skips are 31 actual Chromium cases covered by the separate container gate and one opt-in live Azure Service Bus test. JUnit evidence: `../../../tmp/story28-backend-junit.xml`.
- Built `vct-backend:story28` using the existing Dockerfile: image `sha256:7b297ced1b4f16a1a8280984224f7196bbba935e05776077afa990b377f5daf2`.
- Nonroot, network-denied Chromium container with the configured seccomp policy, 0.5 CPU and 1 GiB: **78 passed, zero skipped**, 233.07 seconds. JUnit: `../../../tmp/story28-browser-junit.xml`.
- Actual Chromium queue/owner/provenance/replay checks on the isolated test database network: **12 passed, 57 deselected, zero skipped**, 56.48 seconds. JUnit: `../../../tmp/story28-browser-queue-junit.xml`.
- Audited all three approved matrix rows against passing JUnit cases, including all five saved layouts and all 41 full baseline comparisons. No missing, skipped or failing covering case.
- Hosted CI and deployed acceptance await release authorization; local results do not claim live source or hosted deployment success.

**Final post-review verification (2026-10-03):**
- Applied all four review patch groups. Extension captures/merge now pass the named legacy non-None presence predicate into the common coverage formula; public HTTP and replay retain the original v1 predicate. Eight inherited-empty-value cases pass for 1688 and Taobao. Case-set completeness and isolated capture documentation are present; all 41 canonical-LF baseline records were independently reproduced from archived original modules.
- Full final backend suite on the disposable PostgreSQL database: **850 passed, 32 skipped**, 228.83 seconds; one existing Starlette/httpx deprecation warning. The skipped browser cases are covered by the actual runtime gate; live Azure Service Bus remains opt-in. JUnit: `../../../tmp/story28-final-backend-junit.xml`.
- Final tested local image: `sha256:cb6445e95d789de1f6236dbc95c7b03b4b27baea27bbb547737b48af38a00723`.
- Actual network-denied browser suite: **76 passed, 2 deadline failures**, 261.29 seconds during concurrent backend/browser/queue verification. Both failures preserved original HTTP evidence. All three real gain-to-replay cases then passed in isolation; serial recheck of the affected gain/DOM-limit cases passed **4/4**, with unchanged 10-second budget, 0.5 CPU, 1 GiB and seccomp policy. Audited the report union: **all 78 distinct browser cases passed**, including all 31 actual Chromium cases, with no skipped coverage. Reports: `../../../tmp/story28-final-browser-junit.xml` and `../../../tmp/story28-final-browser-retry-junit.xml`.
- Final actual Chromium queue gate: **12 passed, 57 deselected**, 62.58 seconds, zero skipped; JUnit: `../../../tmp/story28-final-browser-queue-junit.xml`.
- Four review lenses completed; coverage parity and test reproducibility gaps corrected. Five confirmed pre-existing static CSS visibility groups are recorded in `../../implementation-artifacts/deferred-work.md`. Shared DOM helper ASTs match the original revision, so these limitations were preserved by the refactor.
- All approved matrix rows have passing covering cases; final whitespace checks pass. Local build is complete. Hosted CI, development deployment and deployed three-platform/extension acceptance remain release gates; no remote operations or live-source success are claimed.
