---
title: Expire trial entitlements without charging
type: story
ticket: 7
status: built
created: 2026-10-08
---

## Scope

Read the PostgreSQL MVP_TRIAL ANALYSIS_ACCESS entitlement at request/admission time. An entitlement qualifies only when ACTIVE, already started, and not expired. The API account view exposes the same active/expired plan transition used for quota admission.

- Configurable free quota: CUSTOMER_LIMIT (default 20 per admission window).
- Configurable pilot trial quota: TRIAL_CUSTOMER_LIMIT (default 40 per admission window).
- Both use the same durable CUSTOMER admission counter; no counters reset at expiry, which prevents free quota bypass by switching plans.
- Guest quotas are unchanged.
- All customer paths (URL submission, browser capture, saved-page import, snapshot renormalization) use the effective trial/free quota when supplied.
- Billing integration, PaymentOrder execution, subscriptions and automatic renewal remain out of scope. Trial participation reward decisions stay deferred.

## Verification

A persisted current trial displays the trial quota. Expiration changes account state to FREE, uses the free quota at the next admission, and causes no charge or renewal. The database checks happen inside each admission transaction to avoid a stale client entitlement decision. Repository CI remains the merge gate.
