---
title: 'Trace one queued analysis through the platform'
type: 'feature'
ticket: '1'
created: '2026-09-27'
status: 'built'
baseline_revision: 'NO_VCS'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['blind-hunter', 'edge-case-hunter', 'verification-gap', 'intent-alignment']
review_loop_iteration: 1
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The repository has planning artifacts but no runnable application path. Developers cannot yet submit an analysis, observe queue processing, or inspect a durable result.

**Approach:** Build one locally running Next.js → FastAPI → PostgreSQL → Azure Service Bus → Python worker tracer, using a deterministic 1688 fixture. Keep the PostgreSQL-backed queue adapter as an optional offline fallback. Return an analysis ID at submission and let the web app poll through completion.

## Boundaries & Constraints

**Always:** Use the specification's web/API/PostgreSQL stack. The Azure adapter must publish `analysis_id` as `MessageId`, receive with Peek-Lock, and complete only after persistence. A Basic queue may be used for initial development testing, while the source specification's Standard tier remains the MVP target. Keep Azure credentials server-side through environment configuration. Make the fixture and developer-only admission visible as such. Preserve one result per analysis ID and store UTC timestamps.

**Never:** Treat the fixture as live supplier evidence or deploy an unauthenticated tracer route as a production buyer endpoint. Do not implement Clerk, the full business schema, real extraction, scoring, reporting, quota enforcement, or production retry/DLQ policy in this story; those have later owners.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Submit fixture | Valid supported 1688 fixture URL | API stores `QUEUED`, sends ID to Azure queue, returns ID/status; web polls | Show request errors in web |
| Worker completion | Valid queued ID | Worker persists exactly one fixture result, sets `COMPLETED`, then completes queue message | Abandon message if persistence fails |
| Unknown analysis | Missing ID | Poll returns 404 | Web shows a clear missing-analysis message |
| Invalid submission | Unsupported/malformed URL | No analysis or message is created | API returns 422 with a usable message |
| Queue unavailable | Azure publish fails | No silently stranded `QUEUED` job | Analysis transaction rolls back and API returns a service error |

</frozen-after-approval>

## Code Map

- `VCT_Connect_MVP_Technical_Specification_EN.pdf` — source for stack, queue flow, and status contract (sections 3, 5–8; appendix A–B).
- `_bmad-output/initiative-vct-connect-year-one/epic-platform-foundation/tickets.toml` — story 1.1 acceptance and later-story boundaries.
- `frontend/apps/web/` — new Next.js local submit/poll UI.
- `frontend/packages/` — new shared TypeScript contracts and API client.
- `backend/app/` and `backend/worker/` — new FastAPI API, persistence, and Service Bus worker.
- `compose.yaml`, `.env.example`, and developer README — new local PostgreSQL/configuration/run path.

## Tasks & Acceptance

**Execution:**
- [x] `frontend/packages/contracts/`, `frontend/packages/api-client/` — define typed submit/status/result payloads and browser client so UI and API agree.
- [x] `backend/app/` — add configuration, minimal analysis/result tables, POST `/api/v1/analyses`, and GET `/api/v1/analyses/{id}` with validation and explicit Azure publish failure handling.
- [x] `backend/worker/` — receive Azure messages with Peek-Lock, write the deterministic fixture result once, and complete only after database commit. Keep the local adapter as an optional fallback.
- [x] `frontend/apps/web/` — provide a dev tracer page that submits the fixture and polls to a visible result/error.
- [x] `compose.yaml`, `.env.example`, setup docs — make local PostgreSQL and server-side Azure settings reproducible without committing secrets.
- [x] `backend/tests/` and front-end checks — verify invalid URLs, missing IDs, publish failure, worker persistence ordering, and the Azure queue-backed happy path once credentials arrive.

**Acceptance Criteria:**
- Given the local stack and Azure dev queue are configured, when a developer submits the fixture URL in the web app, then they see a pollable analysis ID move from `QUEUED` to `COMPLETED` with exactly one stored result.
- Given a worker persistence error, when it handles a locked message, then it does not complete the message and the result remains uncommitted.
- Given no Azure credential in the browser, when the web bundle is built, then it contains no Service Bus secret.
- Given Azure credentials are supplied later, when transport is switched to `azure`, then the same API and worker contract can be verified against Azure Service Bus without changing the web app.

## Implementation Notes

- The local `vct_test` database isolates integration tests from the developer tracer database. The main database schema was upgraded after the `CREATED` state was added.
- No version-control repository is present in this workspace, so this build has no commit.

## Plan Change Log

- 2026-09-27: Review found that publishing inside an uncommitted analysis transaction can race the worker or leave an orphan on commit failure. Commit a `CREATED` analysis first, then publish, then conditionally move it to `QUEUED`; on explicit publish failure remove the unqueued row before returning an error. Preserve the successful Azure tracer, one-result constraint, and the existing API/worker separation. Full crash recovery and broker-level deduplication remain with story 1.4.

## Review Triage Log

- Blind 1 — medium, bad_plan: Azure publish precedes commit in `Store.submit_azure`; worker may see no row. Apply the post-commit state transition in the change log.
- Blind 2 — medium, patch: permanently unknown Azure IDs are repeatedly abandoned. Dead-letter them after a committed-row lookup fails, while database exceptions remain retryable.
- Blind 3 — low, defer: the current deterministic fixture commits in seconds, and `Store.complete` is idempotent if a lock expires; long-running lock renewal belongs to story 1.4.
- Blind 4 — medium, defer: the optional local queue can release a newer five-minute claim by ID; it is outside the Azure acceptance path. Track claim ownership before relying on the fallback for concurrent workers.
- Blind 5 — low, patch: the page displays `QUEUED` after a failed first poll although no status was observed. Show an unknown/loading state until a successful response.
- Blind 6 — low, patch: PostgreSQL session timezone can vary, contradicting the UTC timestamp claim. Normalize the session to UTC.
- Blind 7 — medium, patch: in-memory store tests cannot detect real transaction or uniqueness failures. Add PostgreSQL-backed tests and run them.
- Blind 8 — medium, patch: Azure submission is not exercised by the existing tests. Add a configured, opt-in Azure integration check; the manual live trace on 2026-09-27 already passed.
- Blind 9 — low, patch: the README invokes global `python` for pytest after installing into `.venv`. Use the environment interpreter.
- Edge 1 — medium, bad_plan: same publish-before-commit race as Blind 1; apply that plan change.
- Edge 2 — low, patch: fixed-interval browser polling can overlap on slow responses. Schedule the next poll after the previous request resolves.
- Edge 3 — low, patch: a stalled worker leaves the page polling with no guidance. Show a delayed processing notice while allowing continued polling.
- Edge 4 — medium, patch: if an operator binds the unauthenticated tracer publicly, remote clients can submit/read. Reject non-loopback request clients.
- Verification 1 — medium, patch: no test covers Azure submission/publish failure. Add a real-store test with recording and failing publisher.
- Verification 2 — medium, patch: no test covers PostgreSQL result write and GET. Add a real-store completion and API read test.
- Verification 3 — medium, partial: the browser service exposed no browser in this session. The Next.js page returned HTTP 200 with its heading and fixture notice; a submission through its `/api` rewrite moved from `QUEUED` to `COMPLETED`. Direct clicking and rendered-state inspection remain unverified.
- Intent alignment — medium, patch: the diff implements the components but its tests establish only a narrower simulated path; add database/Azure checks and correct the README claim about an integration test.

## Design Notes

Use a fixture URL under the 1688 offer path and a clearly marked fixture payload with `source_url`, `supplier_name`, and `fixture: true`. Keep the minimal tracer schema additive so story 1.3 can expand it through migrations. Commit the analysis row before publishing its ID; remove it on explicit publish failure, and never regress a worker-completed row back to `QUEUED`. The local queue is only an offline fallback. Bind the local API to a developer environment; later identity/admission stories own public access.

## Verification

**Results (2026-09-27):** Docker PostgreSQL healthy; 11 backend checks passed locally and the opt-in Azure test passed outside the restricted network sandbox (4 database-backed tests total). Frontend typecheck and production build passed. A request through the Next.js `/api` rewrite returned `QUEUED`, then `COMPLETED` with the fixture; PostgreSQL contained exactly one result for that ID. The page served HTTP 200 with the expected fixture notice. The built public static files had zero matches for the configured Service Bus connection string or key. The in-app browser was unavailable, so no click-through test was possible.

**Commands:**
- `docker compose up -d db` — local PostgreSQL becomes healthy.
- `python -m pytest backend/tests` — API and worker edge cases pass.
- `npm run typecheck` — shared contracts and web compile.
- `npm run dev` plus API/worker commands — manual Azure dev queue tracer reaches `COMPLETED` and shows one database result.
