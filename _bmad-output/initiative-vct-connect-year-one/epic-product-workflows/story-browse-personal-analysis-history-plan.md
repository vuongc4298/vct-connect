---
title: 'Browse personal analysis history'
type: 'story'
ticket: '2'
created: '2026-10-08'
status: 'built'
baseline_revision: '8d5d112596c499a4deafac82f3f2c3991d9fb989'
route: 'full'
review: 'thorough'
---

## Intent

Replace the seeded signed-in history experience with durable, customer-scoped analysis history from PostgreSQL.

## API contract

`GET /api/v1/analyses` is CUSTOMER protected and returns only analyses owned by the authenticated principal. Results are newest first and bounded to 100 rows.

Each history item contains compact navigation state only:

- analysis ID, source URL, lifecycle status and timestamps;
- mode, extraction method and scoring version;
- supplier/platform labels when persisted evidence exists;
- whether an immutable report is available;
- persisted report risk label, overall risk, confidence and coverage when available.

The history endpoint does not return full report findings, evidence payloads, guest analyses, another user's analyses, or local browser notes.

## UI behavior

The signed-in History workspace fetches the server list when opened, supports local filtering, distinguishes pending/final/completed states, and offers the appropriate action:

- report available -> open the existing authorized full report flow;
- completed without report -> reopen the analysis result/status path;
- pending/retryable -> reopen progress;
- failed final -> reopen the terminal analysis state.

Opening a history item updates the existing analysis query parameter and delegates authorization to the existing owner-only analysis/report endpoints.

## Boundaries

This story owns durable browsing and reopening only. Watchlist persistence is Story 5.3. Trial entitlement changes remain Story 5.7. Seeded/demo history is not treated as customer data.

## Verification

- unauthenticated and non-customer callers cannot list customer history;
- two customers see only their own rows;
- pending and completed rows are both present in newest-first order;
- persisted report summary fields are represented without copying full report evidence;
- web API client uses bearer identity;
- history rendering handles empty, loading, failure, pending, completed, insufficient, and report-opening states;
- repository CI is the merge gate.
