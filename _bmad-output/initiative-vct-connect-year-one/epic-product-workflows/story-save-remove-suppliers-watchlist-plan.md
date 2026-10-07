---
title: 'Save and remove suppliers in Watchlist'
type: 'story'
ticket: '3'
created: '2026-10-08'
status: 'built'
baseline_revision: 'a2e0ed4ff5ecdf4d386674f6a6b70e60786524f3'
route: 'full'
review: 'thorough'
---

## Intent

Add a durable, user-scoped Watchlist for suppliers already resolved by VCT Connect analyses.

## Data model

`watchlist_entries(user_id, supplier_id)` is unique per customer/supplier pair. The server resolves the supplier from an owned analysis; clients never submit or choose an arbitrary supplier ID.

## API

- `GET /api/v1/watchlist` lists only the authenticated customer's entries.
- `POST /api/v1/watchlist/{analysis_id}` resolves the supplier from that owned analysis and idempotently saves it.
- `DELETE /api/v1/watchlist/{entry_id}` removes only an entry owned by the authenticated customer.

Foreign analyses or entries return 404 so ownership is not disclosed.

## Presentation

Completed full reports expose a “Lưu vào Watchlist” action. The signed-in workspace includes a Watchlist view showing supplier identity, latest owned analysis/report summary, and actions to reopen the existing authorized analysis/report flow or remove the supplier.

## Boundaries

Watchlist does not copy findings/evidence, create new analyses, change trial or billing state, or expose guest suppliers. Latest risk/confidence/coverage are projections from the customer's own most recent persisted analysis/report for that supplier.

## Verification

- duplicate saves for the same user/supplier produce one entry;
- another user cannot list, save from, or remove the owner's entry;
- client cannot forge a supplier identifier;
- watchlist UI renders supplier/report state and empty state;
- repository CI is the merge gate.
