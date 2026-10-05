# Story 3.1 v2 release and bounded live acceptance

2026-10-05. Implementation commit `21fed98ffce528f250872a65d4d263300f8ca55d`.
Local commit only; no Git push was performed. Story 3.1 remains incomplete.

The release adds required model self-reported confidence to `vi-text.v2` /
`text-report.v2`, with application-owned `model_self_reported` / `uncalibrated`
labels and separate buyer UI. Legacy reports retain their saved content and no
inferred confidence. Validation diagnostics persist only fixed category/location.

Verification: 145 focused backend tests (also in the non-root built container
with network disabled), 13 PostgreSQL report tests, 83 frontend tests, typecheck
and web production build passed. Four independent review lenses completed.
Small patches covered repeated confidence scores, quoted foreign confidence
basis, natural Vietnamese confidence vocabulary, deep JSON nesting, duplicate
members hiding escaped credentials, and exact confidence diagnostic assertions.
Factual support of model prose, including supplier assurances in a confidence
basis, remains a human evaluation limitation; no calibration is claimed.

## Deployed release

- Backend: `sha256:c3bc804e9b306cdb67c91d48060ab29ab6a51294f536d076797ab9972c0239e8`.
- Web: `sha256:410c164eba65e801b5b79b62d0a41e7ed90f20753aa54d56daa871cb2a16d17a`.
- Dispatcher `vct-connect-dev-dispatcher--0000020`, API
  `vct-connect-dev-api--0000011`, web `vct-connect-dev-web--0000011` healthy
  and running; analysis/migration job templates use the same backend digest.
- Only images changed. Effective configuration and secret references verified
  unchanged; Azure update responses normalized placeholders differently, so final
  resource reads were used. No database migration was needed for JSONB fields.
- Preflight: four dispatches, retained reservations $0.0083376, no pending jobs.
- Model `deepseek-v4.1-flash`, expected return `deepseek-v4-1-flash-260910`,
  thinking disabled, deadline 120 seconds, output 2400 tokens, ledger cap $0.09.

## Single live Chinese rehearsal

Submitted the authentic sanitized saved Taobao item through the signed-in web
UI exactly once. Analysis `44607bff-73f3-40d0-8651-ef9ef05049b5`, snapshot
`ab693ee6-81d5-406d-b7ef-9f1e639a01d2`: extraction COMPLETED/PARTIAL;
report FAILED/INVALID_OUTPUT, no accepted report and no generated_at.

The new diagnostic is `NON_VIETNAMESE_PROSE / findings.text`. This identifies
the validator and field; it does not establish whether the rejected text was
untranslated or valid Vietnamese outside the conservative lexicon. Rejected
prose was not retained. No blind validation relaxation or paid retry followed.

One dispatch `9407326c-0856-4a6d-8158-e5a73bb3b970`; request
`20261005184734760712627SbSbozfl`. Returned exact expected model;
1304 input / 2109 output tokens, application latency 29321ms, input 4538 bytes.
Reservation $0.0022743 remains retained; configured-rate usage estimate
$0.001461 is not an invoice. Actual ledger cost remains unknown/null.
YEScale completed successfully, gateway latency 29208ms, displayed charge
$0.0015 and rounded balance after $0.09 at 18:48:03 Asia/Bangkok.

Read-only inspection execution `vct-connect-dev-migrate-497titl` confirmed five
total dispatches, reservations $0.0106119 and no pending jobs. Owned failure
reopen shows extraction fallback unchanged. No old analysis was replayed.
Operational evidence remains under untracked `tmp/story31-cloud-acceptance-logs.json`
and `tmp/azure-story31-v2-deployment.json`; UI proof is
`tmp/story31-live-language-rejection.jpg`.

The existing READY demo `36677413-84b7-45b5-8255-828fbe4cd0c8` reopened on
the released UI with identical report DOM text and no confidence field. Its
persisted version remains v1; no generation was triggered.

## Remaining gate

The chosen live Chinese interpretation criterion did not pass. Do not mark
Story 3.1 complete or move on as though its original acceptance passed.
The next proposed experiment is documented in
`story31-language-diagnostic-proposal.md`: one fresh bounded diagnostic with
only safely redacted rejected finding prose retained locally. This is proposed,
not authorized or executed; it requires approval of the changed retention policy.
