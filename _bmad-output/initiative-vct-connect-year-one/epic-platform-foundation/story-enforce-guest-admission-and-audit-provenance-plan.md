---
title: 'Enforce guest admission and audit provenance'
type: 'feature'
ticket: '6'
created: '2026-09-29'
status: 'in-review'
baseline_revision: 'dabf8ff47012b0404dcb2254a491a7dc4c1f82f5'
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

**Problem:** The deployed tracer accepts only Clerk customers. Anonymous visitors cannot enter the analysis queue, and accepted analyses leave the reserved mode and scoring-version fields empty. There is no durable admission budget or clear extraction-method and actor provenance.

**Approach:** Add a limited guest submission and private guest status path, perform quota admission atomically with queueing, and record truthful fixture method, mode, actor, and scoring version on both guest and customer analyses.

## Boundaries & Constraints

**Always:** Keep guests anonymous with no Clerk user row; preserve CUSTOMER-only authenticated submissions and role/ownership checks; validate the fixture URL before admission; enforce configurable guest and customer limits in PostgreSQL across replicas; cap the total guest budget because browser identifiers can be reset; queue accepted work through the existing local or Azure transactional path; keep guest result access scoped to its opaque browser cookie. Use `GUEST_PUBLIC` and `ACCOUNT_PUBLIC` modes and `v0.1.0` scoring-version provenance, with `FIXTURE` as the honest tracer method.

**Never:** Trust browser-supplied role, mode, method, version, or forwarding IP headers. Do not expose another guest's result or loosen `/api/v1/analyses/{id}`. Do not add live extraction, paid entitlements, usage billing, or final product quota values.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
| --- | --- | --- | --- |
| First guest | Valid fixture, no guest cookie, budget available | Issue opaque HttpOnly cookie; queue anonymous analysis; allow that cookie to poll | No Clerk user or authenticated route access |
| Repeated guest | Same cookie reaches configured limit | Refuse before analysis/outbox creation | Stable 429 response; no queued work |
| Browser reset or burst | New cookies consume shared guest budget | Shared cap bounds total guest work | Stable 429 when global cap is reached |
| Customer | Valid Clerk CUSTOMER and fixture | Existing endpoint queues with owner and provenance | Configured customer limit rejects before queueing |
| Unauthorized read | Different guest cookie or no Clerk token | No analysis details | Non-disclosing 404 for guest path; 401 for protected path |
| Replay or restart | Accepted analysis is redelivered | First result and provenance remain unchanged | Existing queue idempotency applies |

</frozen-after-approval>

## Code Map

- `backend/app/main.py` — reuse `Submission`, Clerk dependencies, and current protected routes; add guest POST/GET without identity mapping.
- `backend/app/storage.py` — extend atomic submit operations and owner-filtered reads; enforce admission inside the same transaction that writes analysis and outbox/local queue.
- `backend/db/migrations/0006_guest_admission_and_provenance.py` — additive migration after 0005 for guest key hash, actor/method fields, and durable quota counters; retain 0001–0005.
- `backend/app/config.py`, `.env.example`, `infra/azure/main.bicep` — validate and expose provisional, configurable limits and window duration for dev.
- `frontend/apps/web/app/api/_backend.ts`, `app/api/v1/guest-analyses/` — mint/forward an opaque browser identifier at the trusted web boundary and preserve cookie responses; never forward user-supplied guest identity headers.
- `frontend/packages/api-client/`, `frontend/packages/contracts/`, `frontend/apps/web/app/page.tsx` — add guest submit/status contracts and a small anonymous demo path while leaving Clerk customer flow intact.
- `backend/tests/`, `frontend/packages/api-client/src/index.test.ts` — exercise budget concurrency, no-user/no-outbox denials, provenance, guest isolation, and customer compatibility.

## Tasks & Acceptance

**Execution:**
- [x] Add a forward migration for durable admission counters and analysis provenance with safe existing-row defaults.
- [x] Implement atomic guest and customer admission in storage with configurable limits and no queue side effect on denial.
- [x] Add anonymous guest POST/GET and extend customer POST, keeping current Clerk and ownership boundaries.
- [x] Wire the web proxy, shared client/contracts, and anonymous demo entry to the guest routes.
- [x] Add targeted backend/frontend tests and document temporary development limits, cookie behavior, and Azure parameters.

**Acceptance Criteria:**
- Given a fresh anonymous browser, when it submits the fixture, then one queued analysis has no user and stores guest mode, actor, fixture method, and scoring version.
- Given exhausted guest or customer limits, when another submission arrives, then the API returns 429 and neither an analysis nor an outbox/local queue row is added.
- Given concurrent guest requests, when the remaining budget is one, then at most one request queues and the shared cap is never exceeded.
- Given a guest analysis ID, when a different browser polls it or accesses the protected analysis endpoint, then no result is disclosed.
- Given existing Clerk roles and queue replay, when customers submit and workers resume, then owner authorization, one stored result, and provenance stay correct.

## Implementation Notes

- Migration 0006 adds durable admission counters and guest/provenance fields. It keeps prior modes and scoring versions, and derives historical extraction method from a linked snapshot when present.
- Guest web submissions use a random HttpOnly cookie; the private API stores only its SHA-256 hash. The guest read expires after 30 days and sends a private, no-store response. Clerk customer routes remain separate.
- Admission limits are temporary, configurable development values. PostgreSQL enforces both a per-browser guest cap and a shared cap transactionally with analysis and queue/outbox creation; customer admission uses the same mechanism.
- The guest landing screen shows fixture progress and a limited preview. CI now runs PostgreSQL integration tests, and deployment smoke submits and polls a guest fixture through the public web route.

## Plan Change Log

## Review Triage Log

| Lens | Finding | Verdict and evidence | Route |
| --- | --- | --- | --- |
| Blind | Guest ID disappears on refresh | low: the landing page holds the ID in component state; refresh loses the current view, but resumable guest history is outside this admission slice and persistence adds a separate privacy policy. | reject |
| Blind | Guest GET lacks an explicit cache policy | medium: the response can carry a completed result; the fetch option alone does not specify the HTTP response policy. | patch |
| Blind | Copied guest key works beyond cookie expiry | medium: PostgreSQL lookups did not enforce the web cookie's 30-day lifetime. | patch |
| Blind | One visitor can drain the shared budget | false: the shared cap intentionally bounds total guest cost and browser identity is explicitly resettable; its availability tradeoff is documented. | reject |
| Blind | Admission counters lack cleanup | low: rows accumulate, but the development fixture's volume is small and safe cleanup requires a separate retention policy. | reject |
| Blind | Azure limits lack application maximums | medium: a Bicep-valid oversized value makes Settings reject API startup. | patch |
| Blind | Historical snapshots are labeled FIXTURE | medium: a linked snapshot can record another method; backfill must not invent fixture provenance. | patch |
| Blind | Unknown historical mode aborts migration | false: the current application never writes a non-null mode, and future unsupported values should fail visibly rather than be silently remapped. | reject |
| Blind | Guest POST has no idempotency key | low: every accepted POST is a separate request and counts toward the limit; the client does not automatically replay POST. | reject |
| Edge | Concurrent first requests use separate cookies | low: the per-browser key is a convenience limit, not a hard identity; the database-wide cap still bounds total accepted work. | reject |
| Edge | Azure limits lack maximums | medium: same verified issue as Blind Azure limits. | patch |
| Verification | PostgreSQL admission tests skip in CI | high: CI had no PostgreSQL service or test URL, so the transaction/concurrency checks never ran there. | patch |
| Verification | Valid-cookie GET path untested | medium: the existing route test covered only the missing-cookie denial. | patch |
| Intent | No deployed guest round trip in pipeline | medium: isolated tests cover each layer, but deployment smoke still exercises only signed-in ingress. | patch |

## Design Notes

The browser key limits repeat use but can be cleared; a separate database-wide cap bounds total guest cost. Values in configuration are temporary development guardrails, not a product quota decision. Guest reads use the key hash associated with the submitted analysis. The existing authenticated GET remains Clerk protected. The tracer stores `FIXTURE` as its method because no HTTP extraction, Playwright, or scoring run occurs yet.

## Verification

**Local result (2026-09-29):** PostgreSQL 16 integration suite: 80 passed, 1 opt-in Azure test skipped. Frontend: 13 passed; typecheck and production build passed. Secret scan reported no configured server credentials in the frontend build. Azure Bicep template compiled. Live dev guest smoke remains pending deployment.

**Commands:**
- `.venv/Scripts/python.exe -m pytest backend/tests -q` — guest/customer admission, migration, auth, and queue tests pass against an isolated PostgreSQL test database.
- `npm test --prefix frontend` and `npm run typecheck --prefix frontend` — guest and Clerk client paths pass.
- `npm run build --prefix frontend` and `.venv/Scripts/python.exe scripts/scan_frontend_secrets.py` — web build succeeds without server secrets.
- `az bicep build --file infra/azure/main.bicep` — deployment template compiles.
