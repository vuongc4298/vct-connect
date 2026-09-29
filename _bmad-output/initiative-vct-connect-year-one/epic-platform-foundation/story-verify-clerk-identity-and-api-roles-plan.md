---
title: 'Verify Clerk identity and API roles'
type: 'feature'
ticket: '2'
created: '2026-09-27'
status: 'built'
baseline_revision: 'NO_VCS'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['blind-hunter', 'edge-case-hunter', 'verification-gap', 'intent-alignment']
review_loop_iteration: 0
context:
  - '_bmad-output/initiative-vct-connect-year-one/epic-platform-foundation/story-persist-the-core-business-and-evidence-schema-plan.md'
---

<frozen-after-approval reason="human-owned intent - do not modify unless human renegotiates">

## Intent

**Problem:** The tracer has no application identity: any loopback client can submit and read analyses, Clerk subjects are not mapped to VCT users, and PostgreSQL roles cannot protect customer or internal API actions.

**Approach:** Add a minimal Clerk-enabled web shell, verify Clerk session JWTs in FastAPI, resolve the verified subject to a PostgreSQL user, and enforce explicit database-backed role and ownership rules on protected analysis routes. Keep anonymous guest admission for story 1.6.

## Boundaries & Constraints

**Always:** Accept session tokens only; validate signature, time claims, issuer/audience, and authorized party; derive identity from verified `sub`; use PostgreSQL as the only source of VCT roles; return 401 for missing/invalid identity and 403 for a valid but disallowed role; keep worker reads independent of request authorization; keep Clerk and Azure secrets out of browser bundles.

**Never:** Trust role, plan, entitlement, or ownership claims supplied by the browser or Clerk metadata. Never grant `INTERNAL_REVIEWER` or `ADMIN` during automatic mapping. Do not add the guest-analysis endpoint, full `/me` profile, entitlements, quotas, internal evaluation APIs, extension session sync, or production deployment in this story.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|---------------------------|----------------|
| Signed-in customer | Valid Clerk token and mapped CUSTOMER | Submit and poll only that user's analysis | Another user's analysis is non-disclosing 404 |
| Internal access | Valid mapped reviewer/admin | Only explicitly allowed role sets pass | Lower role receives 403 |
| Invalid identity | Missing, malformed, expired, wrong issuer/audience/party token | No protected action or user record | Return 401 without token details |
| Anonymous visitor | No Clerk session | Remains anonymous and creates no Clerk/VCT user | Protected analysis route returns 401 |
| Unknown subject | Valid token with no VCT user | Auto-provision a VCT user with the CUSTOMER role | Never infer an elevated role |

</frozen-after-approval>

## Code Map

- `backend/app/auth.py` - new injectable Clerk verifier, authenticated principal, and explicit `require_roles` dependencies; use the official `clerk-backend-api` request authentication path.
- `backend/app/config.py`, `.env.example` - server-only Clerk JWT key/secret, audience, issuer, and authorized-party configuration; preserve Azure configuration.
- `backend/app/storage.py` - consume story 1.3's `users` and `analyses.user_id`; add subject mapping and user-scoped analysis operations while preserving worker `get`.
- `backend/app/main.py` - protect POST/GET analysis routes and retain loopback development admission as defense in depth.
- `frontend/apps/web/app/layout.tsx`, `page.tsx`, `package.json` - minimal Clerk provider/sign-in state and bearer-token forwarding; no dashboard or role UI.
- `frontend/packages/api-client/src/index.ts` - accept an identity-provider-neutral token supplier/options object; do not import Clerk into the shared client.
- `backend/tests/test_auth.py`, `backend/tests/test_postgres_tracer.py` - token failure/role matrix plus real subject mapping and analysis ownership checks.
- `README.md`, `.gitignore`, frontend `.env.example` - local Clerk setup, secret boundaries, and reproducible live verification.

## Tasks & Acceptance

**Execution:**
- [x] Story 1.3 migration output - consume the canonical `users` table and nullable `analyses.user_id` foreign key; do not recreate them in the tracer's hand-split schema.
- [x] `backend/requirements.txt`, `backend/app/auth.py`, `backend/app/config.py` - add Clerk request authentication with injectable verification and deterministic 401/403 dependencies.
- [x] `backend/app/storage.py`, `backend/app/main.py` - map verified subjects, persist CUSTOMER ownership, protect submission/polling, and enforce explicit internal role sets.
- [x] `frontend/apps/web/`, `frontend/packages/api-client/` - add the minimal web sign-in/token path without coupling shared code to Clerk.
- [x] `backend/tests/` - cover valid, missing, malformed, expired, wrong-claim, unknown-subject, lower-role, database-role-change, and cross-user cases.
- [x] `.env.example`, frontend `.env.example`, `.gitignore`, `README.md` - document Clerk configuration and live role-matrix verification without committing keys.

**Acceptance Criteria:**
- Given valid Clerk sessions mapped to CUSTOMER, INTERNAL_REVIEWER, and ADMIN rows, when each calls protected routes, then FastAPI applies the documented database role and ownership matrix.
- Given missing, expired, invalid, or incorrectly scoped tokens, when a protected route is called, then it returns 401 and creates no user or analysis.
- Given a valid CUSTOMER token, when the browser submits and polls its fixture analysis, then the Azure-backed flow still reaches COMPLETED and another customer cannot retrieve it.
- Given a production frontend build, when its assets are inspected, then they contain no Clerk secret/JWT private material or Azure Service Bus credential.

## Implementation Notes

- Linked the existing Clerk development application `VCT Connect` with Clerk CLI 3.3.0 and kept local credentials in ignored environment files.
- The public Next.js shell uses ClerkProvider and client-side sign-in components; FastAPI is the authorization boundary, so no Next middleware is required.
- The backend accepts bearer session tokens with signature, time, issuer, audience, authorized-party, subject, and session-ID validation. Unknown valid subjects are inserted as CUSTOMER and every request reloads the PostgreSQL role.
- CUSTOMER submissions persist `analyses.user_id`; customer polling uses an ownership predicate, while explicit REVIEWER/ADMIN reads use the worker-compatible unscoped store path. Elevated roles cannot submit.
- Review patches clear browser analysis state when the Clerk user changes, stop terminal polling failures, map JWKS outages to 503, and add executable role, Azure ownership, issuer fallback, and bearer-header coverage.

## Plan Change Log

## Review Triage Log

| ID | Lens | Verdict | Route | Evidence |
|---|---|---|---|---|
| V1 | verification-gap | medium | patch | ADMIN cross-customer access was implemented but not distinguished from owner access in tests; added a second-user ADMIN retrieval and submission denial assertion. |
| V2 | verification-gap | medium | patch | The authenticated Azure branch passed `user_id`, but ordinary tests could not detect its loss; added an injected Azure API test that asserts owner persistence, owner polling, completion state, and cross-customer 404. |
| V3 | verification-gap | medium | patch | Typecheck/build did not observe request headers; added a shared-client runtime test proving fresh bearer headers on POST and GET. |
| V4 | verification-gap | medium | patch | All verifier tests supplied an explicit issuer; added valid, malformed, and absent publishable-key fallback cases. |
| B1 | blind-hunter | medium | patch | Clerk SDK v6 categorizes any supported signed JWT shape as a session token; requiring a nonblank `sid` now rejects signed custom JWTs without a Clerk session. |
| B2 | blind-hunter | medium | patch | JWKS transport and server reasons could surface as 500 or 401; known infrastructure failures and request exceptions now map to `AuthenticationUnavailable`/503, with a regression test. |
| B3 | blind-hunter | medium | patch | Polling previously depended only on the analysis ID; it now also requires an active signed-in state. |
| B4 | blind-hunter | medium | patch | Analysis state could survive account changes in a shared browser; a `userId` effect now clears the ID, result, error, and delay state. |
| B5 | blind-hunter | medium | patch | Polling retried 401/403/404 forever because errors had no status; `ApiError` retains status and terminal authorization/not-found errors stop the loop. |
| B6 | blind-hunter | medium | patch | Activation-time and session-shape claims lacked negative tests; future `iat`, future `nbf`, and missing `sid` are now covered. |
| B7 | blind-hunter | medium | patch | The role matrix did not prove cross-owner ADMIN access or both elevated-role submission denials; assertions now cover ADMIN cross-owner read and ADMIN/REVIEWER POST 403. |
| B8 | blind-hunter | medium | patch | Azure ownership isolation was only live-tested for its owner; the injected Azure API test now checks a second customer receives 404 after completion. |
| B9 | blind-hunter | low | patch | PostgreSQL API tests reused a fixed Clerk subject and left its user row; each test now uses a unique subject and removes the orphaned user. |
| B10 | blind-hunter | low | patch | Reproducible verification omitted the production build and credential scan; README now includes both. |
| B11 | blind-hunter | low | patch | Clerk Doctor does not exercise authorization; README now documents the CUSTOMER/REVIEWER/ADMIN live matrix and local role changes. |
| B12 | blind-hunter | low | patch | Root `API_INTERNAL_ORIGIN` is not loaded by the Next app; README now places it in the web app's `.env.local`. |
| B13 | blind-hunter | low | patch | Other Next local environment variants remained trackable; `**/.env*.local` now ignores them while example files remain visible. |
| B14 | blind-hunter | low | patch | `CLERK_JWT_KEY` was supported but undiscoverable; the examples and README now document the networkless verification option. |
| E1 | edge-case-hunter | medium | patch | Same root cause as B2: JWKS outages now produce a controlled 503 instead of invalid-identity or uncaught responses. |
| E2 | edge-case-hunter | low | reject | A database role can change in the microseconds between principal resolution and the data query, but request-time freshness is the approved invariant; transaction-scoped role authorization would add substantial complexity for a very unlikely single-request race. |
| E3 | edge-case-hunter | medium | defer | Ambiguous broker acceptance after a publish exception is a pre-existing Story 1.1 distributed-transaction problem; recorded for queue reconciliation work. |
| E4 | edge-case-hunter | medium | defer | Failure of the compensating delete can strand a CREATED row in the pre-existing Azure path; recorded for repair/reconciliation work. |
| E5 | edge-case-hunter | medium | defer | Failure of the post-publish QUEUED update can prompt a duplicate client retry; recorded for the production outbox/idempotency work. |
| E6 | edge-case-hunter | medium | defer | Local claims have no ownership token, so a stale worker can clear a newer claim; this pre-existing fallback-queue issue is recorded separately. |
| E7 | edge-case-hunter | medium | patch | Same root cause as B4: account changes now clear the previous analysis from browser state. |
| E8 | edge-case-hunter | medium | patch | Same root cause as B5: terminal polling responses now stop retries. |
| E9 | edge-case-hunter | medium | defer | Fetches can remain pending indefinitely, but that behavior predates Clerk in the Story 1.1 shared client; bounded request timeouts are recorded as deferred work. |
| E10 | edge-case-hunter | low | patch | Same root cause as B11: README now contains reproducible live role-matrix steps. |
| I1 | intent-alignment | false | reject | The frozen boundary explicitly makes PostgreSQL the source of VCT role values and FastAPI the protected-route enforcement surface; it does not require PostgreSQL login roles, grants, or row-level security in this story. |

## Design Notes

Use explicit allowed-role sets instead of an implicit hierarchy. Clerk proves the subject; a fresh PostgreSQL lookup supplies the role so a database role change takes effect without waiting for a new Clerk token. Normal tests use injected verifier results and local cryptographic fixtures; live Clerk validation is a separate smoke test.

Story 1.3 is the prerequisite and owns the canonical schema. A previously unseen, valid Clerk subject is created as `CUSTOMER`; elevated roles require a database-side administrative change. Clerk setup follows Clerk's official skill and CLI flow using development credentials, while deterministic automated tests continue to use local cryptographic fixtures.

## Verification

**Commands:**
- `.venv/Scripts/python.exe -m pytest backend/tests -q` with the local PostgreSQL test URL - 45 passed, 1 opt-in live-Azure check skipped.
- `npm test --prefix frontend` - bearer-header request test passed.
- `npm run typecheck --prefix frontend` and `npm run build --prefix frontend` - passed; the production build generated all four routes.
- `.venv/Scripts/python.exe scripts/scan_frontend_secrets.py` - no configured Clerk, Azure, or JWT-key values found in the frontend build.
- `npx -y clerk@latest doctor` - account and `VCT Connect` application link reachable; CLI 3.3.0 current. The doctor emits a non-fatal environment warning despite both required variables being present and the build/live flow succeeding.
- Live browser flow - Clerk account creation/sign-in, CUSTOMER submission, Azure processing, and polling reached COMPLETED. PostgreSQL confirmed CUSTOMER ownership and a persisted result.
