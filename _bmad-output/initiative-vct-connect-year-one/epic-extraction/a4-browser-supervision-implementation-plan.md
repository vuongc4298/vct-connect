---
title: A4 browser supervision implementation recommendation
ticket_ref: '2.12'
date: '2026-10-03'
disposition: proposed-controls-unqualified
after: [9, 10]
---

# A4 implementation plan

Parent executes after CSS ticket 2.9 and fetch ticket 2.10. This supporting plan preserves the approved F4–F6 intent; it does not change ticket status, authorize browser activation or establish deployed acceptance. Docker is currently stopped; parent owns restart. No new runtime probes accompanied this plan.

## Intent and boundaries

Qualify abrupt runner death, independent cleanup delay and actual allocation failure, and fix demonstrated failures while retaining useful HTTP evidence. Implement one attempt owner that remains identifiable after runner death and one outer deadline covering setup, execution and cleanup.

Keep supervisor/runner UID/GID nonzero, `chromium_sandbox=True`, the existing seccomp profile, secret-free runner environment, network denial, source CSP, identity/gain checks, access-wall handling and immutable HTTP provenance. Keep deployed `PUBLIC_BROWSER_FALLBACK=False`. No privileged container, added host capabilities, cgroup delegation, seccomp relaxation, supervisor mapping to UID 0, sandbox bypass or increased resource budget. Preserve Chromium's own sandbox internals. Reuse existing DOM/adapters; exclude CSS and fetch/decompression implementation.

## Existing evidence

Cached baseline: `vct-backend:story28`, image `sha256:cb6445e95d789de1f6236dbc95c7b03b4b27baea27bbb547737b48af38a00723`. Both production browser files matched workspace SHA-256 at assessment time; subsequent candidate changes require a new immutable image. Controls: UID 10001, `--init --network none --cpus 0.5 --memory 1g --memory-swap 1g --shm-size 256m`, existing seccomp, finite outer timeouts. Times exclude Docker startup.

| Probe | Observed outcome |
| --- | --- |
| Ordinary sandboxed Chromium | Browser gain, 7.904 s. |
| Abrupt runner death, separate-session synthetic descendant | 0.429 s; descendant survived cleanup with PPID 1. HTTP result unchanged. |
| Actual Chromium descendants frozen, runner killed | 4.993 s; four descendants remained alive. Gone runner's `pidfd_open` raised EINVAL, aborting cleanup. Narrow rerun located `browser.py:151`. HTTP result unchanged. |
| Three independent 4 s `/proc` enumeration stalls | 12.059 s against 10 s budget; HTTP unchanged. Controlled delay injection. |
| Independent 12 s profile-cleanup stall | 12.034 s against 10 s budget; HTTP unchanged. Controlled delay injection. |
| Instrumented runner: 384 MiB allocation under 256 MiB RLIMIT_AS | Observed MemoryError; native runner main returned RUNTIME_FAILED, caller survived, HTTP unchanged; 2.401 s. |
| Instrumented runner: 1,200 MiB allocation in shared 1 GiB cgroup | Peak 1,073,741,824 bytes; oom +1, oom_kill +1, runner exit -9; caller survived, HTTP unchanged; 9.162 s. |
| Actual Chromium touched-buffer pressure | DEADLINE, 9.885 s; no OOM event. Allocation failure unqualified. |
| Subsequent Chromium attempt in same caller | 9.902 s; no gain. Caller survival observed; browser recovery unqualified. |

Probe-owned survivors were killed through retained pidfds before disposable container exit. These allocation probes exercised an extraction caller, not database-backed worker completion or failure during normal DOM serialization. F4/F5 are demonstrated defects; F6 remains conditional qualification evidence. A shared-cgroup 1 GiB OOM is **not a worker-survival guarantee**.

## Minimum proposed implementation

1. **Trusted bootstrap in a separate process.** Never unshare/fork the threaded HTTP worker. A small single-threaded helper calls `unshare(CLONE_NEWUSER | CLONE_NEWPID)`, establishes single-ID mappings retaining the caller's nonzero UID/GID, writes `setgroups=deny` before an unprivileged GID map where required, and forks the first child as namespace PID 1. Drop bootstrap-only namespace capabilities before processing source input. Do not depend on an unverified `unshare` executable or `--map-root-user`.
2. **Parent owns the namespace init pidfd before any browser starts.** The trusted bootstrap reports the child's PID as visible in the worker's namespace. Init waits for a bounded READY/ACK handshake; parent opens its pidfd while init is alive and validates readiness/nonroot identity. Only after ACK may init create the profile and spawn the runner. A pidfd for the outer bootstrap alone is insufficient. Handle bootstrap/worker death through a tested parent-death chain and control-channel closure; no browser may escape the handshake. Bound bootstrap termination/reaping too.
3. **One absolute monotonic deadline.** Keep the 10 s budget, starting before attempt setup. Put profile creation/deletion, runner execution and any `/proc` inspection inside the namespace owner. Reserve cleanup time inside that budget. Parent uses bounded nonblocking IPC and deadline-aware waiting; cap result receipt at MAX_BYTES + 1 and cap control messages separately. Accept a candidate only after bounded protocol validation and successful attempt cleanup/exit. At expiry, signal namespace init SIGKILL through its retained pidfd, close IPC and return the original HTTP result. Namespace init death supplies kernel descendant termination, including other sessions and nested PID namespaces; no outer `/proc` tree walk is needed for ownership.
4. **Cleanup remains independent of individual errors.** Close every acquired descriptor even if signaling fails. Continue independent termination/reaping after one error; never reopen a gone runner PID as the sole owner or assume every EINVAL is harmless. Track finite cleanup outcomes without exception strings or source material. Successful calls leave no profile. Interrupted deletion uses a separate bounded helper for the known attempt directory; cap outstanding cleanup and decline further browser attempts when cleanup capacity is exhausted. Do not claim immediate deletion during a deliberately stalled filesystem operation.
5. **Fail closed on missing prerequisites.** Unsupported Linux/PID namespace support, denied unshare or ID mapping, failed pidfd signal/handshake, or incompatible sandbox launch returns RUNTIME_UNAVAILABLE with original HTTP evidence. Post-start failure returns the existing finite RUNTIME_FAILED/DEADLINE outcome with original HTTP evidence. Missing namespace support must never fall back to today's process-group-only implementation. No retries that bypass controls.

Namespace ownership fixes process lifetime, not memory isolation. Keep attempt concurrency bounded and all worker-side IPC allocations bounded. Do not apply the test's 256 MiB RLIMIT_AS blindly to Chromium: virtual-address reservations require separate compatibility qualification. If F6 fails, keep fallback disabled and route the remaining runtime limitation to A3; do not claim that namespace supervision prevents the shared cgroup from selecting the worker as an OOM victim.

## Prerequisite assessment

**Observed:** nonroot Chromium gain with its sandbox enabled; pidfd open/signaling of live probe descendants; seccomp allows `clone`, `unshare`, `setns`, pidfd operations and `prctl`; cgroup memory.max=1 GiB, memory.oom.group=0, cgroup mount not writable.

**Unrun:** combined user+PID unshare; nonzero UID/GID mapping; namespace-init ownership handshake and ancestor pidfd kill; parent-death races; Chromium inside the additional namespace; namespace/profile cleanup under faults.

`mount` is permitted by this seccomp JSON only when the container has CAP_SYS_ADMIN. Use inherited `/proc`; namespace-local process enumeration is not an ownership prerequisite. Prove Chromium compatibility with that proc view. If a private proc mount or extra capability is required, decline the attempt under the existing controls and report the limitation to A3. Static syscall allowlists and prior Chromium success do not prove these prerequisites. References: [user mappings](https://man7.org/linux/man-pages/man7/user_namespaces.7.html), [unshare](https://man7.org/linux/man-pages/man2/unshare.2.html), [namespace-init death](https://man7.org/linux/man-pages/man7/pid_namespaces.7.html), [shared-cgroup OOM](https://docs.kernel.org/admin-guide/cgroup-v2.html).

## Remaining acceptance gates — all unrun on proposed implementation

- **G1 prerequisites:** exact candidate image passes combined unshare, nonzero maps, PID 1 verification, parent pidfd ownership/signaling and nested sandbox launch with inherited `/proc`. Inject each denied prerequisite: no runner launch, no leaked helper/profile, HTTP unchanged, RUNTIME_UNAVAILABLE. No skipped prerequisite test counts as passed.
- **G2 F4:** kill runner during launch, execution and cleanup, with frozen and unfrozen descendants and another-session/double-fork cases. Kill namespace init directly; exercise bootstrap and outer-parent death/handshake races. Record PID/start time, PPID/PGID, pidfd and exit/reap status. Every owned descendant must terminate; an unrelated sentinel outside the attempt must survive. Verify descriptor closure and bounded reaping.
- **G3 F5:** independently stall `/proc` iteration/stat, profile creation and deletion, including early runner completion and near-deadline execution; exercise stalled READY/ACK and oversized/stalled stdout. Record setup/execution/termination/profile/total times with an external watchdog. Production cutoff stays 10 s; test assertion may retain the existing <11 s scheduling tolerance, which must not become extra production waiting time. Assert scope termination and bounded leftover-profile handling; repeat attempts cannot create an unlimited cleanup backlog.
- **G4 F6:** observe actual MemoryError and actual kernel OOM; additionally target normal isolated-world DOM serialization and runner UTF-8 encoding/reparsing. Record failing process, peak/current memory, memory.events deltas, selected result and cleanup. DOM_LIMIT or DEADLINE without observed allocation failure is not covering evidence. Same worker must preserve HTTP fields/hashes, remain alive and process a subsequent job; browser recovery requires an actual subsequent gain. Any worker loss or unobserved targeted failure leaves this gate open.
- **G5 durable evidence:** parent runs the existing local claim/persistence boundary with fault outcomes and checks completion under the current claim, owner isolation, immutable HTTP raw/normalized provenance and replay; no inappropriate browser provenance. Database checks are separately recorded from network-none browser probes. `vct-retro-postgres` at 127.0.0.1:55439 belongs to parent: never stop/remove/reconfigure it. If the integration harness is unavailable, report this gate unrun.
- **G6 preserved security/function:** actual three-platform gain, strict no-gain/conflict HTTP preservation, source CSP, access walls without snapshots, secret-free child environment and reachable-loopback HTTP/WebSocket denial. Run affected adapter/replay tests after CSS/fetch integration. Preserve all existing resource/sandbox controls and capture image identity; no network or sandbox bypass to obtain a pass.

Parent owns candidate image creation, scoped finite probes, unified review and evidence recording. Keep cloud/deployed qualification and activation under A3, independently gated even after local acceptance. Source changes are future work in `browser.py`, a small trusted namespace supervisor, and focused fault tests; reuse the runner's evidence/security implementation.

Source of approved intent: [story 2.12](story-qualify-browser-process-cleanup-and-memory-failure-boundarie.md), [retrospective F4–F6/A4](epic-extraction-retrospective.md), [approved action plan](../../implementation-artifacts/plan-extraction-retrospective-actions.md), [runtime decision](browser-runtime-decision.md). Fault locations: `backend/app/extraction/browser.py:129–210`; original allocation boundary in `browser_runner.py`'s isolated-world collection and `main`; existing gates in `backend/tests/test_browser_fallback.py` and `.github/workflows/ci.yml`.
