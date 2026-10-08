---
title: 'Show extension progress and condensed verdict'
type: 'story'
ticket: '6'
created: '2026-10-08'
status: 'built'
route: 'full'
review: 'thorough'
---

## Intent

Keep the extension useful after selected evidence is accepted and handed to the analysis worker. Do not confuse completed extraction with a completed scored assessment.

## Behavior

- The popup reloads its last analysis for the current Clerk owner using the authenticated shared client.
- It polls QUEUED, PROCESSING, ASSESSING, REPORTING and FAILED_RETRYABLE every three seconds while the popup is mounted.
- COMPLETED and FAILED_FINAL stop polling. A completed result attempts an owner-authorized report fetch using the explicit VCT web origin.
- Condensed Risk, Confidence and Coverage appear only when an actual persisted full report is returned.
- INSUFFICIENT_INFORMATION is a distinct verdict, never an inferred LOW score.
- Blocked/extraction-only results and report-unavailable states are explicitly unscored.
- The existing open-web-result action remains the path to the full authorized report.
- Polling uses the owner Clerk bearer, not guest cookies or page-origin credentials.

## Boundaries

No scoring is performed in the extension. It does not invent risk or evidence, broaden page capture, or bypass the authenticated report endpoint. Polling exists only while the popup remains open.

## Verification

- pending/retry states continue polling, terminal states do not;
- a completed analysis without a report has no risk verdict;
- insufficient information preserves real confidence/coverage without becoming low risk;
- blocked extraction is terminal and unscored;
- shared report fetch uses owner bearer and explicit VCT origin;
- repository CI remains the merge gate.
