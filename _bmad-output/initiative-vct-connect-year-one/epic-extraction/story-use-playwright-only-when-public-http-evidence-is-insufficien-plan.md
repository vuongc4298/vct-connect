---
title: 'Use Playwright only when public HTTP evidence is insufficient'
type: 'feature'
ticket: '5'
created: '2026-10-02'
status: 'built'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['blind-hunter', 'edge-case-hunter', 'verification-gap', 'intent-alignment']
review_loop_iteration: 0
baseline_revision: '374dfc8de12af6af8b35ee59b61cef797445d869'
context:
  - 'C:/Users/eidel/Desktop/VCT Connect/_bmad-output/initiative-vct-connect-year-one/epic-extraction/epic-extraction.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** HTTP extraction misses inline-rendered evidence. Public links need bounded rendering that preserves source safety and access failures.

**Approach:** Render cached public HTML when justified, reuse normalization, select strictly improved evidence, and measure coverage gain for pilot tuning.

## Boundaries & Constraints

**Always:** HTTP first; all three platforms, seven statuses, SupplierData v1's 12 fields, public modes, quotas, ownership, current leases and immutable replay remain valid. Require identity-bound PARTIAL evidence, insufficient coverage and a relevant inline DOM-rendering signal. Only render cached, bounded HTTP 200 HTML. Stop on login/CAPTCHA/block before or during rendering, returning the explicit access status without evidence. Keep selected public fields only, original response hash, rendered hash, method/version/time and honest missing fields. Chromium must use its sandbox, a minimal environment without backend secrets, fresh ephemeral context, one attempt and an outer process deadline. Deny secondary requests, navigation, frames/popups, downloads, service workers and WebSockets; use offline/dead-proxy controls and deny non-proxied WebRTC. Fail closed if sandbox/runtime is unavailable.

**Never:** Follow challenges, click/authenticate, send or retain source cookies/storage/tokens, collect arbitrary globals, screenshots, traces, console/errors or whole HTML, fetch external resources, broaden URL admission, merge snapshots, score evidence, rewrite migrations, alter broker settlement or add Alibaba upload/capture. No fallback for SUCCESS, access/transport failures, malformed/conflicting identity, oversize/non-HTML or unverified shells. No-gain/runtime-failed attempts preserve useful HTTP evidence. A browser snapshot must preserve established identities and previously available evidence.

**User decision:** Defer manual upload/extension/browser acceptance. Keep automated tests/review; Story 2.5 deployment needs release approval.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Outcome | Handling |
| --- | --- | --- | --- |
| Render gain | Bound sparse public page, relevant inline script | Increased coverage, PUBLIC_BROWSER snapshot | Preserve prior evidence and identity |
| Enough/irrelevant | Complete/enough evidence or no rendering signal | Original HTTP result, zero launches | Record skip reason |
| Access wall | HTTP or rendered login/CAPTCHA/block | AUTH_REQUIRED/BLOCKED, no snapshot | Stop; no bypass/retry |
| Unsafe/invalid | Unsafe hop, identity conflict, malformed data or non-HTML | Existing terminal outcome | No browser launch |
| Resource attempt | Script requests network/state/popups/downloads | Denied; no source state retained | Count denials without sensitive labels |
| No gain/conflict | Missing bundles or lost/changed prior evidence | Original HTTP snapshot | No merge or fabricated enrichment |
| Runtime limit | Missing browser/sandbox, hang, oversized DOM/output | Bounded cleanup, original HTTP evidence | Fixed diagnostic code; no browser retry |
| Ownership/replay | Guest/account result or duplicate delivery | Atomic method transition and exact replay | Other owner gets 404 |

</frozen-after-approval>

## Code Map

- `backend/app/extraction/fetch.py::bounded_extract` — hook validated 200 HTML beside parsing; preserve transport.
- `backend/app/extraction/{offer1688,taobao,alibaba}.py` — existing parse/access/identity policies and audited DOM selectors; wire hooks without collecting arbitrary page state.
- New `backend/app/extraction/browser.py`, `browser_runner.py` — eligibility, supervised Chromium, comparison/provenance and sanitized metrics.
- `backend/app/config.py`, `backend/worker/main.py::_compute_claim` — settings/orchestration; preserve fixture/compute.
- `backend/app/storage.py::_complete_processing` — explicit leased PUBLIC_HTTP→PUBLIC_BROWSER transition for public modes; same-method exact replay; existing SQL accepts nonblank methods.
- `frontend/apps/web/app/{page,analysis-status,extraction-evidence}.tsx/ts` — recognize server browser provenance separately from extension evidence.
- `backend/{requirements.txt,Dockerfile}`, `.github/workflows/ci.yml`, `infra/azure/main.bicep` — browser/runtime; retain 0.5 CPU/1 GiB.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/extraction/browser*.py` — implement bounded offline rendering, eligibility, strict improvement and metrics.
- [x] `backend/app/extraction/{fetch,offer1688,taobao,alibaba}.py`, `backend/{worker/main,app/config,app/storage}.py` — integrate optional fallback, settings and atomic provenance.
- [x] `frontend/apps/web/app/` — present PUBLIC_BROWSER accurately, preserving terminal recovery.
- [x] `backend/requirements.txt`, `backend/Dockerfile`, `.github/workflows/ci.yml`, `infra/browser-seccomp.json`, `infra/azure/main.bicep` — bake pinned browser; CI runs the image with sandbox and network denied; production never disables sandbox on failure.
- [x] `backend/tests/test_browser_fallback.py`, `test_postgres_tracer.py`, frontend tests — matrix, actual Chromium gains, leakage, cleanup and coverage/time measurements.

**Acceptance Criteria:**
- Given a supported public fixture requiring inline rendering, when the queued pipeline runs, then owner polling returns greater traceable coverage with browser provenance and immutable replay.

## Implementation Notes

- Implemented opt-in cached HTML rendering, strict evidence selection, sanitized diagnostics, sandboxed runtime, queue provenance, frontend labels and CI/container gates. `PUBLIC_BROWSER_FALLBACK` defaults to false. No remote Story 2.5 release performed.
- Initial implementation verification: backend isolated PostgreSQL: 586 passed, 13 skipped (12 actual Chromium cases executed separately; one opt-in Azure check). Frontend: 72 passed; typecheck, build, secret scan, Azure compile and whitespace checks passed.
- Actual baked image `vct-backend:browser-story25`, digest `sha256:c2628d95fb7934050621216f883f165fcbf450ec550c5799e8d011fb651f2020`: 55 passed with sandbox, nonroot, network none, 0.5 CPU/1 GiB; seven actual browser queue checks passed against isolated PostgreSQL. Coverage 1688 1→2, Taobao 1→2, Alibaba 3→4 in approximately six seconds each.
- Matrix audit: render gain → actual three-platform and six guest/account queue cases; enough/irrelevant → eligibility/terminal/inert tests; access → static and actual rendered wall cases; unsafe/invalid → transport and existing adapter guards; resource → actual network/state/popups/global-canary case; no gain/conflict → strict preservation and actual CSP/hidden/conflict cases; limits → actual missing runtime, infinite script and oversized DOM with cleanup; ownership/replay → seven queue tests. All covering tests executed and passed in their applicable gates.
- Manual HTML, extension and signed-in browser acceptance remains deferred. ACA sandbox availability is unverified; unavailable runtime retains HTTP evidence with a finite diagnostic code.

## Plan Change Log

- Review patches: DOM collection moved to an isolated execution world; protected the global alias, namespace-aware frame checks, fixed 750 ms settling, stylesheet visibility pruning and HTTP restoration on malformed provenance. No approved intent changed. Existing Alibaba redirect assertions retained alongside added cookie, CSP, storage and reachable network regressions.

## Review Triage Log

- All four lenses completed. B1/B2/B4/B8/B10, E1/E2/E3 and G1/G2/G3 corrected with targeted regressions. B5/B6/B7 remain explicitly unverified and are recorded in deferred work; rejected refinements and descriptive intent observations remain individually documented below.

| Finding | Verdict | Route | Evidence / disposition |
| --- | --- | --- | --- |
| B1 | medium | patch | Synthetic container probe replaced getComputedStyle and collected a hidden review as PUBLIC_BROWSER. Protect existing DOM/visibility/byte collection from main-world replacements; add regression. |
| B2 | medium | patch | createElementNS and unsafeNode inspect qualified tagName; x:iframe has localName iframe and escapes this element check. CSP/context init remain layered protection, but deny the demonstrated namespace variant explicitly. |
| B3 | low | reject | Body phrase matching can conservatively classify ordinary text as a wall. Product descriptions about CAPTCHA are uncommon; distinguishing arbitrary prose needs new classification branches. Reject the low-frequency refinement; retain fail-closed markers. |
| B4 | medium | patch | A 500 ms inline timer is valid relevant rendering yet the 150 ms fixed wait excludes it. Correct the settling constant within the existing outer deadline and test that timer; no new readiness API. |
| B5 | maybe-false | defer | An abruptly exited runner can reparent children before discovery. Whether Playwright pipe closure or Chromium parent-death cleanup prevents surviving children is unverified; settle with forced runner termination and descendant observation (medium if confirmed). |
| B6 | maybe-false | defer | Cleanup reserves 0.5 seconds but proc enumeration/profile deletion has no independent wall timer. Actual tested cleanup remains bounded; a reachable slow-profile/proc state exceeding the total budget needs measurement (medium if confirmed). |
| B7 | maybe-false | defer | DOM allocation precedes size rejection. Container memory is capped at 1 GiB; it is unverified whether adversarial allocation kills only Chromium or the worker and loses HTTP evidence. Settle with bounded allocation/OOM observation (high if worker loss confirmed). |
| B8 | medium | patch | Synthetic GAIN without raw_payload passes comparison and leaves selected != HTTP after the exception. Restore HTTP on candidate/provenance failure and test malformed output. |
| B9 | low | reject | Lexical heuristic masks template expressions and may miss valid inline writes. Conservative no-signal admission is intentional; general JavaScript parsing adds complexity for uncommon syntactic cases, so reject this low-impact eligibility refinement. |
| B10 | medium | patch | Current denial test uses unreachable example.test and aggregate counts. Add a reachable local canary and assert zero HTTP/WebSocket arrivals while retaining denied-operation evidence; loopback remains reachable even in network-none containers. |
| E1 | high | patch | Proxy replacement of globalThis returned GAIN/PARTIAL for actual Taobao and Alibaba rendered CAPTCHA probes. Lock this existing global alias before source execution and assert access status/no evidence. |
| E2 | medium | patch | Static CSS .hidden-wall {display:none} with CAPTCHA produced BLOCKED in the container probe. Apply existing static stylesheet visibility pruning before scanning body text. |
| E3 | medium | patch | Same malformed GAIN defect as B8; raw_payload/extracted_at failures must restore HTTP. |
| G1 | medium | patch | Preverified regression gap: only Alibaba observes anonymous cookie rejection; add default/injected 1688 and Taobao cookie assertions. |
| G2 | medium | patch | Preverified regression gap: source CSP is tested directly but not forwarded through mocked HTTP. Add actual Chromium adapter response-header test preserving HTTP. |
| G3 | medium | patch | Preverified broken-verification gap: aggregate denials stay green when individual cookie/storage guards disappear. Add observable parameterized denial checks. |
| I1 | false | reject | Representative live coverage is not claimed by fixtures. The diff supplies rendering mechanics and pilot instrumentation; real source acceptance remains explicitly deferred. |
| I2 | false | reject | Opt-in default and no deployed behavior are explicitly approved. Story 2.5 release requires later authorization; no unsupported active-deployment claim. |
| I3 | false | reject | Sparse-field and inline-signal eligibility are approved initial defaults. The concrete timer issue is separately logged B4; broader policies remain tuning choices. |
| I4 | false | reject | Intent specifies coverage gain; increased populated fields preserving old evidence is a defensible coverage interpretation explicitly recorded in approved design. |
| I5 | false | reject | Instrumentation and measured fixture gains support later pilot tuning; no representative/validated threshold claim is made. |
| I6 | false | reject | Tests demonstrate defined access markers and safety controls, not exhaustive restrictions across all actual pages; no universal access-detection claim is made. |

## Design Notes

Initial engineering defaults: opt-in flag; fewer than six present fields plus a missing audited DOM field and a relevant executable inline DOM-write signal; one 10-second browser budget including launch/cleanup, 2 MB input/DOM/output. These are conservative starting limits, not pilot-validated thresholds. Capture only cached HTML and needed CSP metadata in memory; preserve source CSP. All browser traffic is blocked, including repeated canonical navigation. Rendering external bundles is intentionally unsupported. Reparse DOM with original scripts and existing identity guards; never serialize globals. Accept only increased field coverage with existing field values preserved (review/product lists may extend while retaining all old entries). PUBLIC_BROWSER failures retain HTTP provenance; structured logs expose finite codes, platform, elapsed time, byte/denial counts and before/after field counts only. Pin Playwright 1.63.0 and install its matching headless shell at build time. ACA sandbox availability is unverified: runtime unavailability must retain HTTP and be observable. Official references: https://playwright.dev/python/docs/docker and https://playwright.dev/python/docs/api/class-browsercontext.

## Verification

Final root verification after patches: 596 backend tests passed against disposable local PostgreSQL; 32 skipped here (31 actual Chromium cases separately executed, one live Azure check not enabled). Seven actual browser guest/account queue/provenance/replay checks passed in the rebuilt image. All 72 frontend tests, typecheck, web/extension builds, fresh build secret scan and Azure template compile passed.

Final baked image: `sha256:1f2834f112e23dd4eaa496480d1b197a693baa0388aee8cac6c97f155a9b809f`. The first concurrent browser gate passed 77/78: the oversized-DOM case retained HTTP and cleaned up within 9.524 seconds, but returned DEADLINE rather than the expected DOM_LIMIT. Its isolated rerun passed. Final serial container gate passed all 78 tests, including all 31 actual Chromium cases, in 207.19 seconds. No deadline or expectation relaxed. Whitespace check passed. No Story 2.5 push/deployment performed; opt-in remains disabled by default pending release approval and ACA sandbox validation.

- Full `backend/tests` against isolated local PostgreSQL; targeted actual Chromium tests must execute, not count as skipped coverage.
- `npm test --prefix frontend`, `npm run typecheck --prefix frontend`, `npm run build --prefix frontend`, `scripts/scan_frontend_secrets.py`, `git diff --check`.
- Build/run image: nonroot sandbox, network denied, measured time/coverage; infinite script and descendant cleanup tests.
- After release approval: CI/Azure and automated smoke.
