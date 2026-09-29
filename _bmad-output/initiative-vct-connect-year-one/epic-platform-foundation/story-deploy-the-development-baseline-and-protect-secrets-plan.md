---
title: 'Deploy the development baseline and protect secrets'
type: 'feature'
ticket: '5'
created: '2026-09-28'
status: 'in-review'
baseline_revision: 'NO_VCS'
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

**Problem:** The authenticated tracer works locally but lacks Azure infrastructure, container images, CI deployment, and managed secrets. Its API rejects non-loopback traffic and its continuous worker cannot run as a finite Job.

**Approach:** Provision parameterized Azure dev infrastructure and container images. Use an always-on outbox dispatcher and event-driven analysis Job; deploy through identity-based CI, run the fixture, and scan the client bundle.

## Boundaries & Constraints

**Always:** Use Container Apps for public web and internal-only FastAPI/dispatcher, a finite Container Apps Job, PostgreSQL Flexible Server, the existing Service Bus Standard queue, Key Vault, and a registry. Keep Clerk, database, and broker secrets in Key Vault or use managed identity; only the Clerk publishable key may enter the browser. Preserve authorization and Story 1.4 queue semantics. Parameterize SKUs and scale limits.

**Never:** Put secrets into source, logs, image layers, build arguments, public variables, or client bundles. Do not expose FastAPI publicly, replace the outbox, introduce Celery, or implement live extraction/YEScale. Do not claim cloud acceptance without a real deployment.

**Azure target decision:** Deploy to subscription `93bd5d96-c7a2-4072-9aa3-458ab6132d92`, resource group `VCT_Connect_Service_Bus`, region `Southeast Asia`. Reuse the existing Service Bus Standard namespace `vct-connect-standard` and queue `vct-analyse`; verify their configuration before deploying, and do not recreate or replace them.

**Azure access decision:** Use the operator's interactive Azure CLI browser sign-in. The signed-in account can read the enabled target subscription and resource group. The namespace and queue are active in `southeastasia`; the queue has a one-minute lock, ten maximum deliveries, and duplicate detection disabled. Preserve the existing queue settings and enforce replay safety in the application.

**Hosted CI decision:** Create a private GitHub repository at `vuongc4298/vct-connect`, use `main` for development deployment, and authorize GitHub Actions through a scoped Azure federated identity. This workspace has no Git repository yet.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Clean deployment | Approved dev target and identity | Infrastructure, migrations, images, web, internal API/dispatcher, and Job become healthy | Missing permission or invalid SKU fails without printing secrets |
| Fixture run | Signed-in customer submits fixture URL | `QUEUED` reaches `COMPLETED` through Standard queue with one result | Polling shows retry/final states |
| Empty queue | API commits an analysis before publication | Dispatcher publishes it and queue scaler starts a finite Job | Outage leaves durable outbox work |
| Untrusted caller | Direct API request or another customer's ID | Internal ingress blocks direct access; API retains owner filtering | No result leaks |
| Secret boundary | Build, logs, artifacts, client bundle | Only Clerk publishable key is browser-visible | Secret scan fails on leakage |
| Replay / restart | Job or dispatcher restarts after uncertain broker outcome | Durable state preserves the first result | Duplicate delivery cannot add a report |

</frozen-after-approval>

## Code Map

- `backend/worker/main.py` — split its combined infinite loop into finite Job and continuous dispatcher modes.
- `backend/app/main.py`, `backend/app/config.py` — add internal Azure runtime mode, retain local loopback and Clerk checks.
- `frontend/apps/web/app/api/_backend.ts`, `frontend/apps/web/next.config.ts` — route the web server to internal API origin.
- `infra/azure/` — Bicep resources, private database, identity/Key Vault, existing queue, and Job scaler.
- `.github/workflows/` — test/build/scan and OIDC deploy workflows; no Git repository exists yet.
- `scripts/scan_frontend_secrets.py`, `backend/tests/`, `README.md` — secret scan, deployment smoke, runbook.

## Tasks & Acceptance

**Execution:**
- [ ] `infra/azure/` — define dev resources, private database, internal ingress, identities/secret references, existing Standard queue integration, Job scaler, diagnostics, and bounded parameters.
- [ ] `backend/worker/main.py`, `backend/app/main.py`, `backend/app/config.py` — add finite Job, continuous dispatcher, and internal API mode; preserve local and queue behavior.
- [ ] `frontend/apps/web/Dockerfile`, `backend/Dockerfile`, `.dockerignore` — build images without secret files and set runtime API routing.
- [ ] `.github/workflows/ci.yml`, `.github/workflows/deploy-dev.yml` — test/build/scan, use OIDC, publish immutable images, apply IaC/migrations, smoke test.
- [ ] `scripts/`, `README.md`, `.env.example` — add deployment/rollback instructions and secret scan.
- [ ] `backend/tests/` and deployment scripts — cover finite Job, dispatcher recovery, ingress mode, and matrix faults.

**Acceptance Criteria:**
- Given approved Azure dev access and an empty or previously deployed resource group, when the deployment pipeline runs, then infrastructure converges and a signed-in fixture analysis completes exactly once through Service Bus Standard.
- Given a worker restart or duplicate queue delivery, when the cloud job resumes, then the result and status remain correct and the Job exits after its finite unit of work.
- Given a CI build and deployed web response, when scanning client artifacts and build logs, then no Clerk secret, database password, broker connection string, or future YEScale key is present.
- Given an unauthenticated external caller, when it targets the FastAPI service directly, then Container Apps ingress rejects the request before the API.

## Implementation Notes

## Plan Change Log

## Review Triage Log

| Lens | Finding | Verdict and evidence | Route |
| --- | --- | --- | --- |
| Verification | Smoke accepts any nonempty result | medium: deployed result fields are not checked. | patch |
| Verification | Proxy outage lacks a route test | medium: only a mocked client 503 is tested. | patch |
| Edge | Smoke succeeds without a token | high: code returns before fixture submission. | patch |
| Edge | Manual deployment bypasses CI | medium: `workflow_dispatch` passes the job condition unconditionally. | patch |
| Edge | Workers start before migrations | high: deployment creates active workers before starting the migration Job. | patch |
| Edge | Retry loop exceeds lock renewal | medium: the loop has no deadline while renewal is bounded. | patch |
| Edge | Quoted env secret escapes scanner | medium: file parsing retains matching outer quotes. | patch |
| Edge | Unknown future YEScale key escapes scanner | low: no YEScale key or integration exists; configured values are scanned. A future key format needs a rule when integrated. | defer |
| Edge | Empty group fails preflight | false: the approved target necessarily contains the existing Standard queue; no empty target is authorized. | reject |
| Blind | Failed CI build prints log before scanning | medium: the failure branch runs `cat` directly. | patch |
| Blind | Stored smoke token expires | medium: every later automatic deployment reads a short-lived token. | patch |
| Blind | Missing token passes smoke | high: same observed return as Edge smoke finding. | patch |
| Blind | External API 401/403/503 passes ingress check | medium: only 200 is rejected; a reachable API can fail for other reasons. | patch |
| Blind | Deployed web response is unscanned | medium: scanner reads local artifacts and build log only. | patch |
| Blind | SHA image tags can move | medium: reruns rebuild mutable bases and overwrite the same tag. | patch |
| Blind | DB update after dead lettering can fail | medium: settlement precedes `mark_dead_lettered`; this is inherited from Story 1.4 and needs a reconciliation path. | defer |
| Blind | Lock renewal can end before settlement | medium: same unbounded wait as Edge renewal finding. | patch |
| Blind | First migration execution lookup can fail | medium: lookup errors currently abort without retry. | patch |
| Blind | Apps and dispatcher lack explicit probes | low: Azure supplies ingress probes to web/API; a probe would not detect the dispatcher's caught network outage. | reject |
| Blind | Bootstrap absent from deploy workflow | false for the approved target: bootstrap is an operator prerequisite that establishes OIDC trust before CI can authenticate. | reject |

The intent auditor found the remaining evidence gap: local files and tests exist, while live Azure fixture and ingress acceptance still require deployment. Complete those checks before calling the story built.

## Design Notes

The worker must publish outbox records even when the queue is empty. A Service Bus Job cannot wake for pending PostgreSQL rows, so an always-on dispatcher publishes them and the analysis Job exits after one message. The deterministic fixture needs no YEScale key; reserve its future server-only secret boundary.

## Verification

**Commands:**
- `.venv\Scripts\python.exe -m pytest backend/tests` — worker modes, auth, migrations, queue replay, and database tests pass.
- `npm test --prefix frontend` and `npm run build --prefix frontend` — contracts and deployable web build pass.
- `.venv\Scripts\python.exe scripts/scan_frontend_secrets.py` — no configured server credential appears in client output.
- `az bicep build --file infra/azure/main.bicep` — deployment template compiles.
- `docker build` for web and Python images — each image builds without ignored secret files.
- Hosted CI plus deployed smoke command — fixture reaches `COMPLETED`, one result persists, and direct API ingress is denied.
