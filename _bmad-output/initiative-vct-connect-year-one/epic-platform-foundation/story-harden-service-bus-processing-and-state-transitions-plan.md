---
title: 'Harden Service Bus processing and state transitions'
type: 'feature'
ticket: '4'
created: '2026-09-28'
status: 'built'
baseline_revision: 'NO_VCS'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['blind-hunter', 'edge-case-hunter', 'verification-gap', 'intent-alignment']
review_loop_iteration: 0
context:
  - '_bmad-output/initiative-vct-connect-year-one/epic-platform-foundation/epic-platform-foundation.md'
  - '_bmad-output/implementation-artifacts/deferred-work.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Azure submission currently spans separate database and broker commits, so an ambiguous publish or later database failure can delete a valid analysis, orphan a message, or leave an unrecoverable state. Worker failures retry without an application bound or observable final state, and replay protection does not detect conflicting results or stale local leases.

**Approach:** Introduce a PostgreSQL transactional outbox and lease-safe claims, then process every Azure message at least once with database-backed idempotency, lock renewal, bounded retries, durable status events, and explicit final/DLQ disposition. Expose safe progress and failure metadata through the existing owner-protected API and demo UI.

## Boundaries & Constraints

**Always:** Keep `MessageId=analysis_id`, Peek-Lock, persistence before settlement, and one immutable result per analysis. Work on Azure Basic without broker duplicate detection; Standard duplicate detection may later add defense but cannot be required for correctness. Preserve Clerk verification, ownership filtering, role rules, fixture output, interactive history/notes/evidence, and the local queue option. Sanitize public failures and logs so credentials, exception internals, and supplier-sensitive data do not leak. Make transition and lease updates conditional and transactional.

**Never:** Add Celery, real scraping/AI/scoring, usage or entitlement accounting, a new public endpoint, automatic browser POST replay, or changes to the queue/namespace itself. Do not rewrite migrations 0001–0003, overwrite the first stored result, acknowledge a message before durable persistence, or treat Azure duplicate detection as an exactly-once guarantee.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Submit | Valid owned request; Azure available or temporarily unavailable | One transaction creates a `QUEUED` analysis, initial status event, and pending outbox row; API returns the accepted analysis without waiting on Azure | Dispatcher retries publish with the same MessageId and bounded backoff; exhaustion records a safe final failure |
| Normal delivery | Known analysis and unexpired lock | Transition through active processing, persist the fixture result once, then complete the message | Settlement failure is replayable and cannot duplicate or alter the result |
| Duplicate delivery | Analysis already completed with the same durable result | Skip computation/side effects and complete the duplicate | Conflicting stored payload is preserved and surfaced as an invariant failure for operator action |
| Retryable failure | Processing fails below configured attempt limit | Persist `FAILED_RETRYABLE` plus sanitized code, attempt, next retry, and event; abandon message | Database failure while recording the retry causes abandon without losing the broker message |
| Final failure | Attempt reaches configured limit | Persist `FAILED_FINAL` and DLQ disposition, then dead-letter with a bounded reason/description | Redelivery of a final analysis only retries broker disposition; it never recomputes |
| Bad message | Missing/malformed MessageId or permanently unknown analysis | Dead-letter immediately and emit structured operator evidence | No customer row is invented; logs contain no secret payloads |
| Local lease race | An expired claim is acquired by a new worker | Only the current claim token may complete, retry, or release work | A stale claimant is rejected without changing the newer lease |

</frozen-after-approval>

## Code Map

- `backend/db/migrations/0004_harden_analysis_processing.py` — expanded states, transition events, outbox, processing metadata, and lease tokens.
- `backend/app/storage.py` — atomic submission/outbox claims, conditional transitions, bounded retry state, and idempotent result persistence.
- `backend/app/queue.py` — Azure sender/receiver lifecycle, Peek-Lock renewal, settlement, and reconnect boundaries.
- `backend/worker/main.py` — outbox dispatch, delivery attempt policy, replay short circuit, retry/final transitions, and DLQ flow.
- `backend/app/config.py` — validated retry, lease, lock-renewal, and dispatcher defaults.
- `frontend/packages/contracts/src/index.ts` — processing status and sanitized retry/failure metadata.
- `frontend/apps/web/app/page.tsx` — active, retrying, completed, and final-failure presentations.
- `backend/tests/` and `frontend/packages/api-client/src/index.test.ts` — fault injection, migrations, auth-safe contracts, and client behavior.

## Tasks & Acceptance

**Execution:**
- [x] `backend/db/migrations/0004_harden_analysis_processing.py` — add reversible constraints/columns, `analysis_status_events`, uniquely keyed outbox leases, and local claim tokens; preserve existing rows and migration lineage.
- [x] `backend/app/storage.py` — replace the Azure dual write with atomic analysis/outbox creation; add token-checked dispatch/local claims, safe transitions, exact replay detection, first-result preservation, and final disposition helpers.
- [x] `backend/app/queue.py` and `backend/worker/main.py` — dispatch pending outbox rows, renew locks during work, normalize delivery attempts, short circuit completed/final replays, and settle only after committed state.
- [x] `backend/app/config.py`, `.env.example`, and `README.md` — document validated limits, Basic-tier behavior, status meanings, DLQ inspection/replay operations, and startup flow without exposing configured secrets.
- [x] `backend/app/main.py`, `frontend/packages/contracts/src/index.ts`, `frontend/packages/api-client/src/index.ts`, and `frontend/apps/web/app/page.tsx` — return and render safe transition metadata; keep polling for retryable states and stop for completed/final states, with no automatic POST retry.
- [x] `backend/tests/test_migrations.py`, `backend/tests/test_tracer.py`, `backend/tests/test_postgres_tracer.py`, `backend/tests/test_auth.py`, and `frontend/packages/api-client/src/index.test.ts` — cover every matrix row, ownership non-disclosure, and expanded contracts.

**Acceptance Criteria:**
- Given publish acknowledgement loss or a database failure after broker acceptance, when dispatch resumes, then the same analysis is republished safely and ends with exactly one preserved result.
- Given injected transient and terminal processing failures, when the configured limit is crossed, then ordered status evidence exposes attempts, retry timing, sanitized failure code, final state, and DLQ disposition.
- Given concurrent or stale workers, when they attempt lease mutation or settlement, then only the current claimant changes durable state and no completed result regresses.
- Given an authenticated owner polls an analysis, when its state changes, then the UI presents progress/retry/final outcomes while other users continue to receive the existing non-disclosing 404 behavior.

## Implementation Notes

- Added migration 0004 with expanded states, ordered status events, a one-row-per-analysis outbox, expiring outbox and processing leases, and tokenized local claims. Legacy `CREATED` rows become `QUEUED` outbox work; active local claims retain their expiry and receive deterministic tokens.
- Azure API submission no longer opens or waits on Service Bus. The worker dispatches outbox records with stable MessageIds, renews Peek-Locks during computation, and persists retry/final evidence before broker settlement.
- Result completion compares replays against the immutable stored JSON. Identical deliveries settle without computation; conflicting results preserve the original and become an operator-visible invariant failure.
- Public polling returns only stable failure codes and transition metadata. The UI polls queued, processing, and retryable states, then stops on completed or final state. Browser requests time out without repeating POST submissions.
- Verification completed locally: backend `26 passed, 23 skipped` (PostgreSQL/live Azure cases skipped because no test database or broker was configured); frontend API `3 passed`; typecheck, production build, Compose config, Python compilation, and frontend secret scan passed.
- Review fixes separated broker deliveries from database processing attempts, reconciled observed messages with ambiguous outbox sends, bounded claims, and tested timeout, replay, and final-state behavior. Migration 0005 extends disposition constraints on databases that had already applied 0004. Final verification: backend `58 passed, 1 skipped` with PostgreSQL, live Azure round trip `1 passed`, frontend `7 passed`, typecheck and production build passed, and the frontend secret scan found no configured server credentials.

## Plan Change Log

- 2026-09-28 — Implemented all execution tasks and matrix-focused tests. Live PostgreSQL migration and Azure round-trip checks remain environment-dependent and are represented by collected integration tests.
- 2026-09-28 — Review identified broker retry inflation, ambiguous outbox races, replay conflict evidence, client timeout gaps, and missing adapter/integration coverage. Patched and verified those paths; kept 0004 immutable and added forward migration 0005 for the new `PUBLICATION_FAILED` disposition. Deferred only pre-existing malformed local demo-history validation.

## Review Triage Log

- 2026-09-28 — Fixed review findings around durable attempt derivation, same-lock retry waits, lease/renewal bounds, outbox exhaustion and observed-delivery reconciliation, conflict evidence, end-to-end browser timeouts, terminal UI presentation, and sanitized settlement diagnostics.
- Targeted verification: `backend/tests/test_tracer.py` 18 passed; `backend/tests/test_postgres_tracer.py` 7 skipped without `VCT_TEST_DATABASE_URL`; normal frontend test command 7 passed; focused configuration validation 2 passed.

### Thorough review pass 1

- `blind-01` — **high / patch** — `waiting` and `busy` Azure deliveries are immediately abandoned, so broker delivery count can reach the DLQ before `next_retry_at`; keep the lock and retry the durable claim without an abandon loop.
- `blind-02` — **high / patch** — broker delivery count includes non-compute deliveries and cannot be the application attempt counter; derive attempts from fenced database state.
- `blind-03` — **medium / patch** — an expired processing lease can be reclaimed after the configured limit because claim acquisition does not enforce the limit; enforce it transactionally during claim.
- `blind-04` — **medium / patch** — Azure lock renewal can outlive the database processing lease, permitting overlapping computation; validate a database lease at least as long as the renewal window.
- `blind-05` — **medium / patch** — expired outbox claims can increment beyond the application bound; claim/failure transitions must cap durable attempts and handle lost mark-published acknowledgements safely.
- `blind-06` — **high / patch** — outbox exhaustion can overwrite `PROCESSING` or `FAILED_RETRYABLE`; an observed delivery must reconcile the outbox as published and publication failure must not regress active work.
- `blind-07` — **medium / patch** — publication exhaustion uses a DLQ disposition when no broker message is confirmed; use publication-specific final metadata and allow a later observed delivery to reconcile an ambiguous send.
- `blind-08` — **false / reject** — the message remains inspectable in Azure's DLQ and PostgreSQL remains durably `FAILED_FINAL/DLQ_PENDING`; the failed confirmation update does not lose the message or the final result.
- `blind-09` — **medium / patch** — a conflicting completed replay is followed by a stale-token failure, so no durable conflict evidence is written; record the replay conflict separately and dead-letter that duplicate.
- `blind-10` — **medium / patch** — configuration permits an application attempt bound above Azure's common queue limit; cap the validated setting and document that queue MaxDeliveryCount must be at least the application bound.
- `blind-11` — **false / reject** — `attempt_count` is explicitly the processing attempt count, while outbox attempts remain operational metadata and the public failure code identifies publication exhaustion without claiming it was processing attempt one.
- `blind-12` — **low / patch** — final failure uses the spinning `working` orb and current step; give terminal failure a nonanimated visual state.
- `verification-01` — **medium / patch** — fake queue tests do not prove the real adapter sets `ServiceBusMessage.message_id`; add an always-run adapter test.
- `verification-02` — **medium / patch** — no PostgreSQL test invokes the real outbox retry/exhaustion transition; add retry, lease release, and terminal assertions.
- `verification-03` — **medium / patch** — no test injects `complete_message` failure after durable completion; prove redelivery skips computation and preserves the result.
- `verification-04` — **medium / patch** — frontend tests do not exercise retry/final polling and presentation; route the page through tested pure state helpers included in the normal test command.
- `edge-01` — **false / reject** — as with `blind-08`, a post-settlement database failure leaves a truthful unconfirmed disposition and an inspectable DLQ message, not a lost analysis.
- `edge-02` — **medium / defer** — malformed legacy localStorage history can break rendering, but this predates Story 1.4 and is unrelated to queue/status hardening.
- `edge-03` — **false / reject** — the completion effect is not triggered by `userId`; the user-change effect clears `id`, `analysis`, and history readiness before its dependencies can run again.
- `edge-04` — **medium / patch** — the request timer stops after headers, so a stalled JSON body exceeds the advertised timeout; keep the abort active through response parsing.
- `edge-05` — **medium / patch** — Clerk token acquisition is outside the timeout; apply the same bound before starting fetch.
- `edge-06` — **high / patch** — independently confirms the abandon/retry-count mismatch in `blind-01/02`.
- `edge-07` — **high / patch** — an ambiguous accepted publish can be labelled final before its message is consumed; reconcile on observed delivery and never block that delivery from completing.
- `edge-08` — **high / patch** — outbox finalization can clear a current processing token; constrain publication failure transitions to nonactive analyses.
- `intent-01` — **medium / patch** — decisive cross-system cases rely on doubles; the adapter, settlement-failure, and real PostgreSQL outbox tests above close the demonstrated gaps while the live Azure happy path remains green.
- `intent-02` — **medium / patch** — the worker's conflict route diverges from storage's immutable-result guarantee; add durable conflict evidence without changing the preserved completed result.
- `intent-03` — **medium / patch** — token fencing exists but the configured lock/lease windows can permit concurrent workers; enforce the lease relationship and test expired-claim bounds.
- `intent-04` — **medium / patch** — publication exhaustion and DLQ confirmation need distinct durable meanings; correct publication metadata while retaining `DLQ_PENDING` for processing messages awaiting broker disposition.
- `intent-05` — **false / reject** — the approved intent targets the existing developer tracer; malformed/unknown message handling plus the fixed fixture satisfy that surface without adding later extraction/AI work.
- `intent-06` — **false / reject** — the API exposes ordered events and disposition while the customer UI intentionally summarizes safe progress/failure fields; the missing behavioral test is already accepted as `verification-04`.

## Design Notes

The outbox deliberately provides at-least-once publication: publishing and marking an outbox row cannot be atomic across PostgreSQL and Service Bus. Reusing the analysis ID as MessageId and making completion idempotent turns every ambiguous publisher or settlement outcome into a safe replay. A worker may dispatch outbox work before receiving messages, avoiding a new service for the MVP. Public states follow the specification (`QUEUED`, active phase states, `FAILED_RETRYABLE`, `FAILED_FINAL`, `COMPLETED`); DLQ disposition is additive metadata so a final customer result does not depend on broker settlement succeeding synchronously.

## Verification

**Commands:**
- `.venv\Scripts\python.exe -m pytest backend/tests` — all unit, migration, PostgreSQL, auth, replay, lease-race, and injected-failure tests pass.
- `npm test --prefix frontend` — expanded API contract and timeout/error behavior pass without POST replay.
- `npm run typecheck --prefix frontend` — all shared status types and UI branches compile.
- `npm run build --prefix frontend` — the authenticated Next.js app builds successfully.
- `docker compose config` — stack configuration resolves with the new documented settings.

**Manual checks (if no CLI):**
- Submit in the browser and observe queued/active/completed states; inject a retryable failure and a final failure, verify the Vietnamese UI, PostgreSQL event order, Azure DLQ entry, and unchanged single result after replay.
