---
title: 'Show signed-in profile and trial state'
type: 'story'
ticket: '1'
created: '2026-10-08'
status: 'built'
baseline_revision: '8e24f9c2bb165491b5d29b3d004ec957afc3a0be'
route: 'full'
review: 'thorough'
---

## Intent

Expose the signed-in customer's server-owned account state without creating a second plan system in the frontend.

## Contract

`GET /api/v1/me` is CUSTOMER-only and returns:

- the authenticated user's internal ID, email when known, and role;
- effective plan: `FREE` or `MVP_TRIAL`;
- current/recent MVP-trial dates and stored status;
- current CUSTOMER admission usage, configured limit, remaining uses, window size, and reset time.

The effective MVP trial exists only when a persisted entitlement has:

- `entitlement = ANALYSIS_ACCESS`;
- `source = MVP_TRIAL`;
- `status = ACTIVE`;
- `starts_at <= now`;
- no expiry or `expires_at > now`.

Otherwise the effective plan is `FREE`. An expired row is reported as inactive; this story does not mutate it.

## Boundaries

Story 5.1 is read-only account presentation.

It does **not**:

- grant a trial;
- choose pilot trial start/end defaults;
- change submission limits by plan;
- expire entitlement records;
- create payment orders, charge a user, or renew anything;
- implement the one-month post-trial premium reward.

Those product/admission transitions remain owned by Story 5.7 and the deferred paid-launch decision.

## UI

The signed-in workspace gains an Account view showing:

- verified account identity/role;
- Free vs MVP Trial state;
- trial dates/status when present;
- analysis usage against the real admission counter;
- a clear statement that the MVP does not automatically charge or renew.

## Verification

- guests receive 401 from `/api/v1/me`;
- non-customer roles receive 403;
- each signed-in customer sees only their own state;
- PostgreSQL tests prove active and expired `MVP_TRIAL` entitlement semantics;
- usage is sourced from the current CUSTOMER admission-counter window;
- API client sends a bearer token, not the guest key;
- UI tests distinguish Free and active Trial state;
- repository CI remains the merge gate.
