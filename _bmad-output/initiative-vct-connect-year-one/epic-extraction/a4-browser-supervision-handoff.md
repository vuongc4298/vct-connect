---
title: A4 namespace supervision implementation handoff
date: '2026-10-04'
ticket_ref: '2.12'
disposition: implemented-partially-qualified
---

Production source and all scoped test files are ready for the parent's final
immutable candidate build. This handoff does not complete A4 or waive the user's
deployed browser requirement. PUBLIC_BROWSER_FALLBACK remains false by default.
No commits, cloud operations, database reconfiguration or runner/fallback-file
edits were performed by A4.

Historical handoff before parent unified review loop 1. The source hashes and
development measurements below identify that checkpoint. Later cleanup recovery
corrections and qualification are recorded in `retrospective-action-execution.md`
and `../../implementation-artifacts/plan-extraction-retrospective-actions.md`.

## Changed paths

- `backend/app/extraction/browser.py`: replaces ancestry enumeration and
  communicate buffering with a retained namespace-init pidfd, bounded
  OWNER/READY/ACK protocol, nonblocking request/output receipt, one outer
  monotonic ten-second deadline and a half-second cleanup reserve. Candidate
  acceptance requires successful bootstrap exit after namespace exit/profile
  deletion. Missing prerequisites decline without launching a runner. One
  attempt lock and one retained cleanup slot prevent accumulating helpers and
  profiles when cleanup stalls; later attempts decline until cleanup succeeds.
- `backend/app/extraction/browser_supervisor.py`: stdlib-only, single-threaded
  bootstrap establishes combined user/PID namespaces and single nonzero ID
  maps, denies setgroups, drops capabilities, arms parent-death chains and keeps
  namespace PID 1 behind ACK. Runner lifetime belongs to that namespace. Profile
  creation runs inside init; deletion runs in bootstrap after namespace exit.
- `backend/tests/test_browser_supervision.py`: explicit controlled Linux fault
  gates, synthetic different-session/double-fork/frozen descendants, independently
  killed init/bootstrap/outer worker, unrelated sentinel, denied prerequisites,
  stalled setup/deletion/READY/stdout, forbidden worker ancestry inspection,
  streaming receipt cap, malformed output, bounded cleanup backlog, observed
  native-main MemoryError and separate kernel OOM probe.
- `backend/tests/test_postgres_tracer.py`: four opt-in actual namespace-fault
  cases (allocation refusal, abrupt death, oversized output, stalled deletion)
  through process_local_once, checking current claim, immutable original HTTP
  raw/normalized data, ownership, replay and a subsequent job in the same worker.
  These new database tests are written but were not run by A4; parent owns this
  shared gate.
- `.github/workflows/ci.yml`: registers focused supervision alongside the actual
  browser suite, adds a separate finite disposable OOM container, and applies
  memory-swap=memory to browser and PostgreSQL browser gates.
- This handoff document.

## Final source hashes (SHA-256)

| Path | Hash |
| --- | --- |
| browser.py | `69b9d419278bfdacf69040f30f1723fc8afa25ecf9995ac2ea08c0c8ec05878b` |
| browser_supervisor.py | `253691a257a55f88b864f56fa43f3146cdbbbdec5722afcad5190fc1547aa5d7` |
| test_browser_supervision.py | `3641491141e6824234f609a71dfe6ad9af0bf6e93688611b7328299a62be9722` |
| test_postgres_tracer.py | `eb17ef0d7ec0e465330306547cd72435306bc598bb00680a1840a850ff38eee2` |
| ci.yml | `9950cb0b1cd253e21451be26ea1513642c3e6976ea6fe1e056e6bc7a5320741b` |

## Observed development probes

All Docker probes used parent's existing base image
`sha256:635354824a2dae125b105f4779bcfe46adf523ae89f1797c371a06fc2b4d4f7e`
with the current backend source mounted read-only over `/app/backend`. They are
source-overlay development evidence, **not final immutable candidate image or
deployed acceptance**. Controls: default nonroot UID/GID 10001, --init, network
none, 0.5 CPUs, memory 1 GiB, memory-swap 1 GiB, shm 256 MiB, existing
infra/browser-seccomp.json, finite external timeout. No added privileges,
capabilities, cgroup delegation, sandbox bypass or budget increase.

| Probe/run | Observed result |
| --- | --- |
| Focused suite excluding separately selected kernel OOM | 20 passed, 1 deselected; 74.27 s. Later additions are separately covered below; these counts overlap and must not be summed. |
| Direct init/bootstrap/outer-worker death | 3 passed, 21 deselected; 10.32 s. Init kill caller elapsed 2.679 s; bootstrap kill 2.221 s. Runner, frozen different-session descendant and owner terminate; unrelated sentinel survives. |
| Final malformed-output/prerequisite plus existing non-actual browser selection tests | 59 passed, 90 deselected; 12.80 s. Includes output code arrays/objects returning INVALID_OUTPUT and receipt bounded to MAX_BYTES+1. |
| Final denied prerequisites including owner pidfd/signaling, ACK and control-message cap | 10 passed, 20 deselected; 16.48 s. No runner marker or attempt profile remains. |
| Different-session/double-fork descendant with abrupt runner death | Frozen and unfrozen cases pass; elapsed 1.657 / 1.725 s in corrected suite, owned process gone, sentinel alive. |
| Independent 12 s profile creation/deletion, READY and stdout stalls | Caller 10.001 / 10.002 / 10.001 / 10.002 s respectively; test tolerance <11 s reflects scheduling only. Deferred cleanup explicitly recorded and completed by bounded subsequent helper drain. Production waiting budget remains ten seconds. |
| Worker /proc iteration regression | No worker ancestry walk; abrupt failure preserved HTTP, elapsed 1.684 s. Independent helper-side delayed inspection does not become worker cleanup. |
| Repeated stuck cleanup | One known outstanding directory; three further attempts decline; no additional profile backlog; bounded later cleanup succeeds. |
| Instrumented actual 384 MiB bytearray under 256 MiB RLIMIT_AS through browser_runner.main | Observed MemoryError marker, RUNTIME_FAILED, original HTTP object unchanged, caller survives; elapsed 2.843 s in corrected suite. This limit is test-only, not applied to production Chromium. |
| Separate instrumented actual 1,200 MiB touched bytearray in shared 1 GiB cgroup | 1 passed, 20 deselected; 12.25 s suite, caller attempt 10.004 s. memory.peak=1073741824; memory.events oom 0→1, oom_kill 0→1; caller survives and original HTTP unchanged. This is an observed OOM, not a worker-survival guarantee. |
| Existing actual three-platform sandboxed gain inside additional namespace | 3 passed, 120 deselected; 27.29 s. This was a development overlay run; parent reruns current A1/A2 union against final image. |
| git diff --check on scoped tracked edits | Passed. |
| Windows host Python test collection | Could not collect: selectolax absent in host Python. Not a pass; controlled container runs above supplied the dependencies. |

No existing supervision tests were skipped to accommodate the replacement.
Search found no old _kill_tree/communicate mocks. The replay test's Popen-fails
guard is still valid because replay must never launch any browser helper.
Baseline F4/F5 failures remain the independent observations recorded in the
supporting plan; these were not claimed as newly reproduced in this handoff.

## Qualification still required

| Gate | Current state |
| --- | --- |
| G1 prerequisites | Development overlay cases observed; exact final candidate image run remains open. |
| G2 ownership/death | Runner, init, bootstrap and outer-parent cases observed with independent sentinel/liveness checks. Full launch/execution/cleanup race matrix and exact candidate qualification remain open. |
| G3 deadline/cleanup | Independent stalls, bounded output and capped backlog observed. Final-image regression and the full near-deadline matrix remain open. |
| G4 allocation failure | Native-main instrumented MemoryError and kernel OOM observed separately from ordinary Chromium gain. Allocation failure during normal isolated-world DOM serialization and native runner UTF-8 encoding/reparsing is **unobserved/unqualified**. Same-worker post-OOM database completion and actual subsequent browser gain remain open. |
| G5 durable evidence | New database fault tests unrun by A4; parent runs with current claim/owner/provenance/next-job checks on final image and shared PostgreSQL harness. No DB test or skipped test is claimed as passed here. |
| G6 preserved security/function | Development overlay three-platform gain observed. Complete current browser security/function union and database gates remain parent-owned and open for final image. |

**Observed worker-death profile risk:** killing the outer worker terminates the
bootstrap, namespace init, runner and frozen descendant through the tested death
chain, but leaves its interrupted `/tmp/vct-browser-*` directory. The test records
this and removes only its known directory with a bounded independent helper.
The production in-memory cleanup slot cannot survive worker death; persistent
profile reclamation across worker restarts is not implemented or qualified.
Ordinary live-worker failure cleanup/backlog bounds do not establish that claim.

**Memory/deployment limits:** namespace ownership does not isolate the worker
from shared-cgroup OOM victim selection. A surviving caller in one observed OOM
run is not guaranteed isolation, durable database completion or browser recovery.
Deployed browser availability, source-session/security prerequisites, complete
qualification and activation remain required under A3 and the user's retained
deployed browser requirement. A4 must remain incomplete while its required gates
are open. Parent owns final image, unified thorough review and completion status.
