---
title: 'Qualify browser process cleanup and memory failure boundaries'
type: 'change'
ticket: '12'
created: '2026-10-03'
status: 'in-progress'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: []
review_loop_iteration: 0
baseline_revision: '50c9f37df40476c8be22f1a49af745e0a4e120e8'
context: ['_bmad-output/initiative-vct-connect-year-one/epic-extraction/epic-extraction.md', '_bmad-output/initiative-vct-connect-year-one/epic-extraction/a4-browser-supervision-implementation-plan.md']
---

<frozen-after-approval reason="approved retrospective A4; user authorized implementation and qualification">

## Intent

**Problem:** Abrupt runner death can leave reparented descendants alive; independently slow process/profile cleanup can exceed the declared browser budget. Actual allocation-failure survival and durable HTTP completion need qualification.

**Approach:** Establish per-attempt process ownership before browser launch, enforce one outer monotonic deadline including setup and cleanup, qualify allocation-failure preservation through the worker, and fix demonstrated defects. A compatible kernel attempt boundary is required; unavailable prerequisites decline rendering and retain HTTP evidence.

## Boundaries & Constraints

**Always:** Preserve nonroot supervisor/runner, Chromium sandbox, existing seccomp, secret-free environment, offline/CSP/network guards, source identities and strict gain/preservation, ten-second budget and original HTTP provenance. Keep deployed fallback false. Bound IPC while receiving. Record exact image and independent fault measurements.

**Never:** Add privileged containers, host capabilities, cgroup delegation, sandbox bypass or larger budgets. Do not map the supervisor to UID0. Do not describe shared-cgroup OOM survival as guaranteed worker isolation or count a DOM_LIMIT/timeout as observed allocation failure. Missing safe ownership never falls back to ancestry-only cleanup.

## I/O & Edge-Case Matrix

| Scenario | Expected behavior | Qualification |
| --- | --- | --- |
| Namespace/pidfd/handshake prerequisite denied | RUNTIME_UNAVAILABLE; HTTP unchanged; no browser/profile/helper leak | Inject failures plus actual Linux prerequisite check |
| Valid eligible three-platform cached HTML | Gain within total budget; strict original fields/provenance preserved | Existing actual browser union and queue gates |
| Runner death with different-session/frozen/reparented descendants | Owned descendants terminate; unrelated sentinel survives; finite failure preserves HTTP | Actual namespace/kernel termination probes |
| Slow process inspection or profile cleanup, stalled IPC | Outer deadline bounds caller; attempt terminated; bounded leftover cleanup policy | Independent delayed operations, finite watchdog, repeat/backlog check |
| Output exceeds cap or is malformed | Bounded receipt and finite existing failure code; HTTP unchanged | Observe receipt cap before full buffering |
| Observed allocation refusal/OOM | Caller survives and persists immutable original HTTP with current claim; subsequent work progresses | Instrumented actual allocations, memory event observation and database-backed persistence; targeted normal DOM serialization separately recorded |
| Incompatible memory/runtime environment | Explicit unqualified gate; fallback remains disabled | No claim of guaranteed worker survival or deployed qualification |

</frozen-after-approval>

## Code Map

- `backend/app/extraction/browser.py`: currently supervises only runner ancestry, buffers communicate before checking output, performs unbounded worker-side cleanup. Replace with bounded outer protocol and retained kernel namespace-owner pidfd.
- New small trusted bootstrap/supervisor under `backend/app/extraction/`: single-threaded user+PID namespace setup with nonzero ID maps, bounded READY/ACK before runner launch, own profile/cleanup and child lifetime. Use the detailed supporting recommendation for ownership/death races. Keep setup independent from threaded worker.
- `backend/app/extraction/browser_runner.py`: reuse selected-evidence/security work from A1; adjust only allocation-bound collection/runner failure behavior if measured probes justify it.
- `backend/tests/test_browser_supervision.py`: focused protocol/fault tests and actual Linux qualification; selected result and survivor assertions independent of production implementation.
- `backend/tests/test_browser_fallback.py`: existing actual browser security/function gates.
- `backend/tests/test_postgres_tracer.py`: actual retained HTTP failure completion/owner/provenance and next-job evidence.
- `.github/workflows/ci.yml`: include focused actual supervision gates in existing controlled browser gate if new module needs explicit registration. Keep resource/network/security controls.

## Tasks & Acceptance

- [ ] Correct demonstrated F4/F5 ownership/deadline defects with a safe kernel attempt boundary and bounded worker-side receipt.
- [ ] Add regressions for abrupt death, independent cleanup delays and denied prerequisites/output cap; prove original failures against baseline where applicable.
- [ ] Qualify actual allocation refusal/kernel OOM separately from normal DOM serialization and durable worker completion; record any remaining runtime-dependent gap.
- [ ] Run actual browser preservation/security/gain and affected local tests; parent runs shared candidate image/database gates.
- [ ] Reconcile findings in the parent unified thorough review.

**Acceptance Criteria:** Given the approved fault scenarios, when a browser attempt fails, then its ownership survives runner reparenting, the outer budget bounds the caller and unchanged HTTP evidence can complete under its owner/claim. Given unavailable safe prerequisites, no unsafe runner is launched. Given an unobserved allocation-failure path, its gate remains explicitly open and deployed activation stays disabled.

## Implementation Notes

The parent initialized bmad-build and owns ticket coordination/review/completion. This is its explicit step-03 handoff, not a new skill invocation; do not render/restart the workflow. Edit scoped source/tests directly, report every changed path, no commit and no cloud operations. Preserve A1/A2 and unrelated user/demo changes. Parent owns local Docker recovery, image creation and shared PostgreSQL container `vct-retro-postgres` (port55439); never remove/reconfigure it. Local finite controlled Docker probes may run once engine is available, but no skipped test is a pass.

The supporting A4 recommendation records proposed controls and verified baseline faults; implementation may choose the simplest equivalent kernel design meeting the frozen constraints. Unsupported unshare/mapping must fail closed. PID namespace ownership does not solve shared-cgroup OOM victim selection; keep that limit explicit and do not manufacture a pass. Do not touch fetch/decompression or CSS resolution.

Parent baseline-image prerequisite probe passed combined user+PID unshare, single-ID maps, namespace PID1 at UID/GID10001 and outer retained pidfd termination under existing controls. Nested Chromium launch remains to qualify. Docker has recovered after runtime socket repair; the disposable test database is running. The parent has a CSS checkpoint image `vct-backend:retro-css` (sha256:635354824a2dae125b105f4779bcfe46adf523ae89f1797c371a06fc2b4d4f7e); it deliberately uses baseline fetch and is not the final candidate. Actual child source/test images must reflect your code before qualification.

Integration ownership update: the A1 implementer is diagnosing a repeated 1688 restored-visibility DEADLINE in `browser_runner.py` / `test_browser_fallback.py` (44/45 new actual cases passed). Preserve that concurrent work; A4 owns `browser.py`, the new supervisor/protocol/fault tests, database fault tests and CI registration. Do not edit runner or existing browser-fallback tests without handing the necessary change to the parent. Target allocation-failure probes through the focused qualification harness; any required runner allocation correction is coordinated separately.

## Plan Change Log

## Review Triage Log

Parent unified V2 and integration P1 confirmed automatic cleanup recovery was untested and could starve indefinitely: a 0.7-second healthy deletion is repeatedly killed by 0.5-second drain windows. Re-derivation uses the existing total deadline and adds actual subsequent gain without private test intervention. The prior source handoff and image are historical development evidence; A4 remains incomplete for required open gates. See `../../implementation-artifacts/plan-extraction-retrospective-actions.md` for every verdict and route.

## Verification

Run focused unit/protocol tests, actual Linux nonroot namespace/runner death and independent cleanup probes under existing seccomp/network none/0.5CPU1GiB/no-swap/256MiB shared-memory controls. Require immutable candidate image, no skips for covering cases, elapsed time, owned/unrelated liveness and profile result. Parent runs database-backed fault-preservation and current browser union separately. Preserve explicit G1–G6 unrun/failure rows from the supporting plan until observed.
