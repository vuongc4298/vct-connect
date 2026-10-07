---
title: 'Sign in from the supported-page extension'
type: 'story'
ticket: '4'
created: '2026-10-08'
status: 'built'
baseline_revision: '273db56e263977d647c12f0592087f2b18871ebf'
route: 'full'
review: 'thorough'
---

## Intent

Turn the existing extraction-era Chrome popup into an explicit signed-in product entry point without widening source-page access or changing the permitted evidence contract.

## Extension shell

The popup uses Clerk's Chrome extension provider and Sync Host integration. Its product state is explicit and testable:

- auth still loading;
- signed out;
- checking the active page;
- unsupported page;
- ready: signed in on a supported 1688 offer or Taobao item/shop.

Only the ready state exposes **Analyze this page**.

Supported-page detection reuses the audited canonical URL parser. The submission routine performs the same page/source check again immediately before script injection so a page change between popup rendering and action cannot bypass the gate.

## Shared client/contracts

Owner-scoped analysis result lookup now uses the shared `@vct/api-client` and `Analysis` contract. The shared analysis client accepts an optional HTTP(S) origin/timeout for extension calls through the VCT web boundary while existing same-origin web callers are unchanged.

The capture submission itself remains the already-audited narrow selected-evidence path and is owned by Story 5.5 for product integration changes.

## Authorization and privacy

- signed-out popup state cannot submit enhanced evidence;
- unsupported pages cannot submit enhanced evidence;
- capture still requires a fresh Clerk token and a Clerk user ID;
- backend audience/authorized-party verification remains authoritative;
- the exact stable Chrome extension origin remains configured and tested;
- source pages retain no persistent host permission; selection is user-invoked through `activeTab`;
- no platform passwords, cookies, session tokens, storage, scripts, page globals, or full HTML are added.

## Verification

- pure shell tests cover 1688/Taobao support classification and every auth/page gate;
- signed-out and unsupported gates are not submission-capable;
- shared API-client test verifies fresh bearer auth to an explicit web origin;
- the existing backend test continues to verify the exact configured extension origin;
- existing extraction tests continue to verify source URL binding and selected-DOM limits;
- extension build/typecheck and repository CI remain the merge gate.

## Boundaries

Story 5.4 does not add new DOM fields, media capture, Alibaba extension support, report verdict presentation, or progress polling. Story 5.5 owns sending/enriching permitted page evidence as a product workflow; Story 5.6 owns progress and condensed verdict presentation.
