# Browser runtime decision — ticket 2.11 / A3

Status: delivery scope decided on 2026-10-04; deployed qualification remains open.

## Human decision — 2026-10-04

The user selected: **“Keep deployed browser enrichment required; leave full epic acceptance pending.”** No scoped deferral was accepted. Preserve epic criterion 2 / R4 as declared. Continue compatible-host planning and exact-image local qualification; deployed gain, queue/preservation and activation prerequisites remain required. The current disabled flag stays false until those gates pass. No new paid host or deployment is authorized by this scope decision.

## Observed environment

Read-only Azure inspection on 2026-10-03 found `vct-connect-dev-analysis` on Consumption with 0.5 CPU / 1 GiB, Event trigger and `PUBLIC_BROWSER_FALLBACK=False`. Its backend digest was `sha256:36f806aecb13f9eba21aa9d88f512bf16f369d703482d4b0985bf5b9f9cdda6e`.

The October 2 probe used an earlier image and returned `RUNTIME_UNAVAILABLE` on all three adapters, preserving HTTP evidence. It does not qualify the current image. This code includes both supervision prerequisite failures and sandboxed Chromium launch failures; the historical result cannot identify a particular failed syscall.

Namespace/seccomp incompatibility is a hypothesis: CI explicitly permits the namespace and pidfd operations used by Chromium, while the inspected Azure Container Apps Jobs schemas expose no custom seccomp configuration. Sources: [Playwright Docker guidance](https://playwright.dev/python/docs/docker), [Azure Jobs schema](https://learn.microsoft.com/en-us/azure/templates/microsoft.app/2026-07-01/jobs). No compatible VM or AKS host was found in the approved resource group.

## Concrete qualification path

[The compatible-host delivery proposal](browser-host-delivery-proposal.md) records the observed VNet/subnets, proposed dedicated worker binding, unchanged container controls, identity/database/broker integration and the approval/rollback sequence. It is prepared planning work; its host, cost and deployment qualification remain unapproved.

1. Build an immutable candidate image containing tickets 2.9, 2.10 and the qualified 2.12 changes.
2. Run Linux Docker with nonroot `vct`, `chromium_sandbox=True`, `--init`, the existing `infra/browser-seccomp.json`, 0.5 CPU, 1 GiB memory, 256 MiB shared memory and `--network none` for synthetic rendering.
3. Record three-platform gain and HTTP preservation, explicit access walls, denied network, reparented descendants, independent cleanup deadlines and allocation-failure survival. A local pass is local evidence.
4. Before cloud activation, identify and approve a controlled Linux host that supports these controls. A new paid VM requires a concrete infrastructure decision. Qualify the exact deployed image there, including private database access, broker identity, queue lease/settlement and ownership/provenance.
5. Enable fallback only after all gates pass and the release decision is recorded. Keep the current deployed flag false meanwhile.

## Alternative considered, not adopted

> Accept deployed HTTP extraction and extension recovery with public browser enrichment explicitly deferred. Keep fallback disabled until the exact-image sandbox, supervisor and deployed gain/preservation gates pass. Local browser success does not count as deployed fallback coverage.

The user did not adopt this scoped deferral. The full epic remains unaccepted until its declared completion gate, including deployed enrichment, passes.

Selected path: retain the full deployed browser requirement and prepare a separate compatible-host delivery plan after local qualification. A new infrastructure/release decision remains necessary before paid resources or activation. No deployment, new resource or runtime flag change was made by this investigation.

References: [epic](epic-extraction.md), [retrospective](epic-extraction-retrospective.md), [historical browser build](story-use-playwright-only-when-public-http-evidence-is-insufficien-plan.md).
