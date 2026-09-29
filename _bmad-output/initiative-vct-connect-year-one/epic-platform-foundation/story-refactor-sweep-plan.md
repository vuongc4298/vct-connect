---
title: 'Refactor sweep'
type: 'refactor'
ticket: '7'
created: '2026-09-29'
status: 'built'
baseline_revision: 'de721f0cdd472f989e0b09bba8ec03c3283aa178'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['blind-hunter', 'edge-case-hunter', 'verification-gap', 'intent-alignment']
review_loop_iteration: 0
context:
  - '_bmad-output/initiative-vct-connect-year-one/epic-platform-foundation/epic-platform-foundation.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Epic 1's Azure workflow duplicates the deployment command and its parameter mapping in the baseline and activation phases. The duplication makes later maintenance risky because those phases must stay identical except for processor activation.

**Approach:** Give the two phases one checked-in deployment command, preserving their existing order and behavior. Keep this sweep focused on the foundation deployment path identified during the completed Azure builds.

## Boundaries & Constraints

**Always:** Keep the approved subscription/resource group, image digest deployment, two-phase processor gate, private migration Job, Service Bus queue, Clerk configuration, and guest/customer smoke behavior. Fail before Azure mutation for an invalid phase or missing required parameter.

**Never:** Change Bicep resource shapes, credentials, queue settings, schema, API contracts, guest/customer behavior, or the sequence of quiesce → baseline → migrations → activation → smoke. Do not convert this sweep into extraction or product feature work.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
| --- | --- | --- | --- |
| Baseline phase | Valid digest and configuration variables | Invoke the existing Bicep template with `enableProcessing=false` and a unique baseline deployment name | Azure failure stops the workflow before migration |
| Activation phase | Successful migration, same variables | Invoke the same template and parameter map with `enableProcessing=true` and a unique active deployment name | Azure failure stops before smoke |
| Bad invocation | Unknown phase or missing required variable | No Azure deployment command runs | Nonzero exit with a safe diagnostic |

</frozen-after-approval>

## Code Map

- `.github/workflows/deploy-dev.yml` — two duplicated `az deployment group create` blocks and phase environment bindings; keep distinct ordered steps around `scripts/wait_container_job.py`, move static bindings to job scope, and pass validated image digests through `GITHUB_ENV`.
- `scripts/deploy_dev.sh` — new Bash entry point for phase validation and the one common Bicep invocation; read digests and nonsecret configuration from existing workflow environment variables.
- `backend/tests/test_deploy_script.py` — run the script with a fake `az` executable to verify exact phase-specific arguments and fail-before-call behavior; check workflow phase order and shared bindings. CI already runs backend tests.
- `infra/azure/main.bicep` — template stays unchanged; compile it and inspect deployment outcome as regression evidence.

## Tasks & Acceptance

**Execution:**
- [x] `scripts/deploy_dev.sh` — implement one validated Bicep invocation for baseline and activation phases.
- [x] `.github/workflows/deploy-dev.yml` — replace inline commands, validate static configuration before Azure mutation, share environment bindings, and retain phase order.
- [x] `backend/tests/test_deploy_script.py` — cover both phases, missing/invalid configuration, and workflow phase order.

**Acceptance Criteria:**
- Given either valid phase, when the script runs, then it passes the same image digests and configuration to the same template, changing only deployment name and `enableProcessing`.
- Given missing or invalid inputs, when the script runs, then it fails without calling Azure.
- Given the deployed foundation, when CI and Azure deployment run, then migrations, guest fixture, customer authorization, queue processing, and private ingress remain healthy.

## Implementation Notes

- The two workflow phases now call one Bash command. Static configuration is bound once at job scope and checked before Azure login; validated image digests are written to `GITHUB_ENV` before processor quiescence.
- The review found a missing workflow-order check and a path that could quiesce processors before detecting an absent issuer. Both were patched. Issuer URL/trust-domain validation remains a pre-existing deferred concern.

## Plan Change Log

## Review Triage Log

| Lens | Finding | Verdict and evidence | Route |
| --- | --- | --- | --- |
| Blind | Static configuration is checked after processors stop | medium: a missing Clerk issuer can reach quiescence because the workflow supplies it only at the later deployment step. | patch |
| Blind | Environment bindings remain duplicated | medium: each phase still maps the same GitHub variables and image outputs independently, so a future edit can diverge. | patch |
| Blind | Workflow phase order lacks a check | medium: the script tests pass even if the workflow calls activation before migration. | patch |
| Blind | Verification claims hosted success and omits customer smoke | false: the section lists commands to run, not passed results; customer authorization is covered by the existing tests and the previously recorded signed-in acceptance, while this change does not touch auth. | reject |
| Edge | Non-numeric run identifiers pass | low: direct script invocation could pass malformed deployment names, although GitHub supplies numeric values. A simple numeric check keeps the helper deterministic. | patch |
| Edge | Malformed Clerk issuer passes | medium: malformed nonempty values can break auth, but the previous workflow passed them through unchanged and this refactor does not define Clerk issuer validation. | defer |
| Verification | Baseline call can move after migration undetected | medium: no test of the workflow ordering exists; changing the first call to activation leaves focused script tests green. | patch |
| Intent | Workflow variable mapping remains duplicated | medium: the broad reading of the intent includes each phase's `env` bindings, which the initial diff did not consolidate. | patch |
| Intent | Tests do not exercise workflow wiring or Azure | medium: focused tests cover only the script; workflow ordering needs a local check and the hosted pipeline must run before acceptance. | patch |

## Design Notes

The two explicit workflow steps remain visible around migration; only their duplicated command body moves. This keeps the operator-facing sequence legible and minimizes changes to the proven quiesce and recovery logic.

## Verification

**Local result (2026-09-29):** 19 focused deployment tests passed; Bash syntax, Bicep compile, 73 backend tests, 13 frontend tests, and frontend typecheck passed. The local backend run skipped 27 PostgreSQL tests because Docker Engine was off.

**Hosted result (2026-09-29):** CI run `36586971118` passed with its PostgreSQL service, frontend checks, image builds, and Azure template compile. Deploy run `36587445034` passed early configuration validation, processor quiescence, baseline deployment, private migration Job, activation, and the public guest fixture through the deployed queue. The analysis Job returned to its Event trigger, the dispatcher minimum is one replica, and Service Bus has zero active, scheduled, or dead-lettered messages. Customer authorization remains covered by CI and the signed-in Story 1.6 acceptance run; no identity path changed in this refactor.

**Commands:**
- `bash -n scripts/deploy_dev.sh` — shell syntax passes.
- `.venv/Scripts/python.exe -m pytest backend/tests/test_deploy_script.py -q` — command contract and fail-fast cases pass.
- `.venv/Scripts/python.exe -m pytest backend/tests -q`, `npm test --prefix frontend`, `npm run typecheck --prefix frontend` — foundation checks pass.
- `az bicep build --file infra/azure/main.bicep` — template compiles without resource changes.
- GitHub CI and Azure Deploy dev — both phases, migration Job, and guest fixture smoke succeed.
