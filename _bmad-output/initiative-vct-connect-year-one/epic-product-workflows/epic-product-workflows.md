---
type: epic
title: "Support repeat use through account and extension workflows"
parent: initiative-vct-connect-year-one
covers: [R10, R11]
assignee: ""
risk: high
---

# Support repeat use through account and extension workflows

## Description

Give signed-in customers history, Watchlist, profile/trial state, and an extension-enhanced path that contributes permitted browser-rendered evidence to the same analysis engine.

## Outcome

Customers can repeat a supplier check and use richer evidence without losing the web report or sending source-platform session material.

## Requirements

- R10: Provide profile, history, Watchlist, and free MVP trial entitlement; trial expiry returns to Free, with no payment or automatic charge. (Specification sections 2, 4, 17-20)
- R11: Require Clerk sign-in in the Chrome extension, detect supported pages, send only permitted DOM/page-state evidence, show progress/condensed verdict, and open the full web report. (sections 4, 6, 9, 17, 21)

## Done when

1. A signed-in pilot user can revisit analysis history, add/remove a supplier in Watchlist, and inspect trial/usage state on the deployed web app.
2. Trial entitlements apply to protected requests and expire to Free without creating a charge.
3. The extension analyzes a supported signed-in page, shows progress and a condensed verdict, and opens the authorized full report.
4. Extension network traffic contains no 1688/Taobao/Alibaba password, cookie, or session token; server-side authorization still controls plans and reports.

## Boundaries

Owns repeat-use customer workflow and extension shell/integration. Extraction owns interpreting extension page data; reporting owns the full report page.

## References

- parent - _bmad-output/initiative-vct-connect-year-one/initiative-vct-connect-year-one.md, Requirements R10-R11.
- specification - VCT_Connect_MVP_Technical_Specification_EN.pdf, sections 2, 4, 6, 9, 17-21.

## Notes

- Open question: trial start/end dates, free limits, and eligible-participant reward rule need product decisions; the paid-launch reward rule can remain deferred during the no-payment MVP.
- Assumption: extension session synchronization is implemented only where Clerk/Chrome support it reliably; sign-in remains required.
- Decision: 2026-09-27 - tracer is a signed-in account state and report, then history/Watchlist and a signed-in extension submission using the shared API client.
- Assumption: independent high-risk checks are a Chrome sign-in/session audit (5.4), extension network credential inspection (5.5), and an operator time-shifted trial expiry/no-charge check (5.7).
