---
title: 'Harden the demo against slow or intermittent Azure connectivity'
type: 'bugfix'
created: '2026-09-28'
status: 'built'
route: 'quick'
baseline_revision: 'NO_VCS'
review: 'quick'
review_source: 'auto'
lenses_ran: ['quick']
---

<frozen-after-approval reason="user-reported HTTP 500 on slow internet">

## Intent

Prevent transient Azure Service Bus and local API proxy failures from surfacing as an unexplained HTTP 500 during the authenticated demo.

## Boundaries & Constraints

**Always:** Preserve Azure Service Bus as the configured transport, keep the existing authenticated API contract, bound Azure retries and worker backoff, and return actionable HTTP errors.

**Never:** Expose credentials, silently switch to the local queue, automatically replay a submission, or alter Story 1.4 behavior.

</frozen-after-approval>

## Tasks & Acceptance

- [x] Capture the failing runtime evidence and distinguish DNS, socket, API, and browser timeout failures.
- [x] Add bounded Azure retry, socket timeout, clean reconnect, and worker backoff behavior.
- [x] Replace the opaque Next.js rewrite failure with a controlled server route that preserves upstream responses and reports connection failures as 503.
- [x] Verify backend tests, frontend tests and typecheck, and a live Azure round trip.

## Implementation Notes

- Worker logs showed repeated Azure DNS failures while the frontend rewrite reported local connection resets.
- `AzureQueue` now gives slow sockets five seconds, uses five SDK retries with bounded backoff, and recreates a failed AMQP client.
- The worker resets the connection and backs off exponentially to a maximum of 30 seconds after failures.
- Next.js route handlers preserve upstream JSON errors and do not abort a submission whose final outcome could still be committed by FastAPI.

## Verification

- Backend unit tests: 22 passed.
- Frontend typecheck: passed.
- Frontend API client test: passed.
- Frontend route to running API: expected HTTP 401 without authentication.
- Final live Azure publish, receive, persistence, and cleanup: passed in 28.35 seconds on the slow connection.

## Review Triage Log

- Removed the frontend proxy abort because cancelling only the proxy can lose a successful acknowledgement and encourage a duplicate user retry.
- Serialized API-side sends and AMQP client replacement so one failed concurrent publish cannot close another request's sender.
- Replaced component-specific timeout and port assumptions with one accurate API connection error.
