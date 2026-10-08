---
title: 'Send permitted page evidence for enhanced analysis'
type: 'story'
ticket: '5'
created: '2026-10-08'
status: 'built'
baseline_revision: '9cf3cb036c76e901e4b69da39971435db64ae18a'
route: 'full'
review: 'thorough'
---

## Intent

Connect the signed-in extension shell to the existing selected-evidence capture/merge path without broadening the permitted browser evidence contract.

## Submission path

The extension continues to collect only the audited `SelectedCapture` shape from the active supported 1688/Taobao page after an `activeTab` user action.

Submission now uses the shared authenticated API client:

- `POST /api/v1/analyses/capture`;
- fresh Clerk bearer identity;
- explicit VCT web origin;
- 45 second request timeout;
- `credentials: omit` so browser cookies are not attached to the extension-to-VCT API request;
- 16 KB UTF-8 request bound before network access.

The backend remains authoritative for role checks, schema validation, source identity normalization, quota admission, secret rejection, owner/source baseline selection, immutable merge provenance and snapshot persistence.

## Privacy boundary

Before the request leaves the extension, the selected JSON is recursively checked for credential-shaped values and keys matching the backend secret policy. Password, cookie, authorization/token/session/CSRF shaped content and cookie-pair strings are rejected locally.

The capture implementation does not read source-site cookies, storage, full HTML, page globals or arbitrary scripts. No new source-site host permission is added.

## Merge and assessment handoff

No merge algorithm or evidence schema changes are introduced by this story. Story 2.6 remains the source of truth for same-owner/same-page baseline selection, immutable prior snapshots, item bounds, field/item provenance and secret rejection.

For successful/partial extension extraction, the merged snapshot is persisted first and the analysis transitions to `ASSESSING`. The same analysis is then placed on the local queue or durable Azure outbox. Worker replay sees the existing snapshot and resumes at assessment instead of recrawling the source page, then proceeds through REPORTING to the immutable report. Non-extracted capture results remain terminal extraction results.

Outbox publication exhaustion now also finalizes pre-extracted ASSESSING work, while a late broker delivery can reopen through the existing publication-recovery path and resume from the stored snapshot.

## Verification

- supported-page capture tests continue to throw if source cookies or full HTML are touched;
- the extension-side privacy guard rejects credential-shaped selected data before submission;
- the shared API client sends exactly the selected JSON plus VCT bearer authorization;
- the extension-to-VCT request explicitly omits browser credentials;
- oversized capture payloads are refused before fetch;
- successful captures persist the snapshot and enqueue assessment/reporting without source recrawl;
- existing backend merge, ownership, deduplication and secret-rejection suites remain in CI;
- repository CI is the merge gate.
