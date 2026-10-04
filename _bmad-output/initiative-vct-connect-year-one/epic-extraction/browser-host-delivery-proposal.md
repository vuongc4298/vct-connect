# Compatible browser host delivery proposal — A3 / 2.11

Prepared 2026-10-04. **Proposal only; no provisioning, deployment or activation.** The user retains deployed browser enrichment as required. A4 qualification precedes host approval and release. A Linux VM is a candidate on which the container controls can be configured and measured; compatibility is not established by choosing that host type.

## Proposed delivery

Use one dedicated Linux Docker host in the existing development resource group and VNet for a bounded qualification trial. Keep the web/API/dispatcher, database schema, source admission and user ownership contracts. Run the existing immutable backend image and `python -m backend.worker.main` in finite `WORKER_MODE=job` invocations, with one invocation active at a time. Record the host OS/kernel, Docker version, exact registry digest and container settings before testing.

The proposal requests enough host capacity for Docker plus the unchanged 0.5 CPU / 1 GiB worker container; a planning allowance is 2 vCPU / 4 GiB. This is an estimate, not an approved VM SKU, cost quote or worker-budget increase. Before any paid creation, select the available regional SKU/OS image, obtain its compute/disk/network/logging estimate and a trial spending ceiling, specify the expiry/deallocation owner, and present that concrete infrastructure decision. No new resource is authorized by the earlier acceptance-scope choice.

## Existing and proposed bindings

Read-only Azure network inspection on 2026-10-04 confirmed the existing VNet and its two delegated subnets. No network configuration was changed.

| Binding | Existing value / proposed change |
| --- | --- |
| Resource group / region | `VCT_Connect_Service_Bus` / `southeastasia` |
| VNet | `vct-connect-dev-vnet`, `10.48.0.0/16` |
| Existing app subnet | `container-apps`, `10.48.0.0/23`, delegated to Container Apps |
| Existing database subnet | `postgres`, `10.48.2.0/28`, delegated to PostgreSQL |
| Proposed worker subnet | New nondelegated `browser-workers`, `10.48.3.0/28`; this does not overlap either observed subnet. Recheck availability immediately before provisioning. |
| Database connectivity | Existing private PostgreSQL FQDN and linked private DNS; TLS and current credentials retrieved through the existing secret mechanism. No public database endpoint. |
| Queue | Existing `vct-connect-standard` / `vct-analyse`; live queue consumption requires an explicit canary/cutover decision after isolated qualification. |
| Identity | A dedicated worker managed identity with only required receiver/registry/secret access; verify SDK authentication inside the container before any queue consumer starts. |
| Container controls | UID/GID10001, Chromium sandbox, current `infra/browser-seccomp.json`, `--init --cpus 0.5 --memory 1g --memory-swap 1g --shm-size 256m`; no privileged mode or added capabilities |
| Environment | Existing queue/database settings, `API_RUNTIME=worker`, `WORKER_MODE=job`, 780-second processing lease/lock renewal, `PUBLIC_BROWSER_FALLBACK=false` until release gates pass |

PostgreSQL private access supports clients in a different subnet of the same VNet; its delegated database subnet is reserved for PostgreSQL. The new host therefore needs its own subnet and working private DNS. [Microsoft private-network documentation](https://learn.microsoft.com/en-us/azure/postgresql/network/concepts-networking-private).

Service Bus supports managed-identity authentication and queue-scoped receiver authorization. Registry and database-secret access must be checked independently; a receiver role does not provide them. Identity tokens and database credentials belong only to the trusted worker, whose browser child environment remains filtered. [Microsoft identity documentation](https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-managed-service-identity).

Docker CPU and memory limits are explicit runtime settings. Setting memory-swap equal to memory denies container swap; it does not isolate the worker from an OOM victim decision within that container. [Docker resource documentation](https://docs.docker.com/engine/containers/resource_constraints/).

## Qualification and release sequence

1. **Local source gate:** finish the unified review and immutable-image browser, namespace/death, deadline, database preservation and separate OOM checks. Keep A4's native DOM/encoding failure, durable post-OOM recovery and restart profile reclamation open until directly qualified. A partial pass does not authorize activation.
2. **Host decision:** present the exact OS/SKU, cost ceiling, expiry and networking/identity changes. After approval, build the host without weakening seccomp, namespace or Chromium controls. Missing prerequisites return RUNTIME_UNAVAILABLE; do not change host security policy merely to obtain a pass.
3. **Isolated host qualification:** run the exact image's synthetic three-platform browser and fault tests with `--network none`. Record UID/capabilities, namespace/pidfd prerequisites, descendant/profile outcomes, normalized/raw hashes, access statuses and denied network/storage. No source overlays count as final-image qualification.
4. **Trusted worker integration:** verify private DNS/TLS/database access, managed identity and actual broker receive/renew/settlement with a controlled qualification message. Require current claim, owner isolation, immutable snapshot/provenance, replay and retained HTTP on browser failure. Synthetic local queue tests alone do not prove the deployed broker boundary. Do not start an uncontrolled second consumer on the live queue.
5. **Canary decision:** identify the qualification message/source and owner, the exact producer/consumer routing and the stop/drain procedure for the current job. Retain traceable public-source HTTP first, actual justified browser gain and failure preservation on the deployed image. If the source blocks access, record that status and continue to hold gain acceptance open.
6. **Activation:** only after A4 and exact deployed qualification pass, record release approval and change fallback for the qualified worker. Keep a rollback that stops the candidate consumer, drains active work through existing lease/settlement rules, restores the prior HTTP worker digest/false flag and deallocates trial compute when approved. Preserve completed immutable snapshots.

## Required decision and evidence record

Before provisioning, the host decision must contain the exact VM image/SKU, cost/expiry, subnet/NSG/identity bindings, secret delivery, access method and rollback owner. Before activation, the record must additionally contain the candidate Git revision/registry digest, actual host test results, broker/database canary IDs, and closed A4 prerequisites. These fields are currently unapproved/unqualified; this document prepares the delivery path without claiming it completed.

References: [retained scope decision](browser-runtime-decision.md), [current execution](retrospective-action-execution.md), [A4 handoff and open gates](a4-browser-supervision-handoff.md), [epic completion gate](extraction-completion-gate.md). Repository bindings were checked in `infra/azure/main.bicep`, `backend/app/config.py` and `backend/worker/main.py`.
