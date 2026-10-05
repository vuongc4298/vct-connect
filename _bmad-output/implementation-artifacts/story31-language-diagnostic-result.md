# Approved language diagnostic result

2026-10-05. Exactly one new local diagnostic request was authorized and executed.
No failed cloud analysis was replayed and no production code or configuration
was changed. Story 3.1's live Chinese acceptance remains open.

Analysis `620d7cf7-c814-408d-819e-0fe4cffa0179`, snapshot
`39685259-3fb0-4c58-a056-47cd8965510a`, retained isolated schema
`story31_language_diagnostic_20261005`. Same sanitized Taobao source and selected
evidence, `vi-text.v2` / `text-report.v2`, pinned expected returned model
`deepseek-v4-1-flash-260910`, thinking disabled, deadline 120s, output 2400 tokens.

Result: FAILED/INVALID_OUTPUT, `SCHEMA_INVALID / findings`, one dispatch
`f794a9d2-3ac7-47bf-a018-338ab86d9a3c`. The response failed structural validation
before reaching the earlier NON_VIETNAMESE_PROSE/findings.text failure. No rejected
prose was saved, because the approved capture applies only to the first rejected
finding text and a safely identified language rejection. The actual structural
subtype remains unknown; do not infer an extra field, wrong type or count limit.
No language-validator correction is supported by this experiment.

Request `20261005185853815014236RCAN2hAg`, 1304 input / 1746 output tokens,
application latency 30860ms. Reservation $0.0022743 retained, usage estimate
$0.0012432; actual cost remains unknown/null. YEScale detail reports completion
at 18:59:24 Asia/Bangkok, gateway latency 30580ms, displayed charge $0.0011 and
rounded balance after $0.0895. The request-list row rounds this charge differently;
the detail is the recorded dashboard figure, not an invoice amount.

Prior local reservations $0.0121752 plus cloud reservations $0.0106119 were
deducted from the conservative $0.09 cap before dispatch. Including this call,
retained reservations total $0.0250614, leaving $0.0649386 under that cap.
Extraction/snapshot/reviews/provenance remain unchanged. No retry followed.

## Preparation for the next diagnostic

The local harness now maps schema failures to fixed safe codes and allowlisted
locations, without messages, values, dynamic keys or rejected response storage.
Offline checks pass for extra keys, too many findings and missing citations,
as well as credential withholding and URL/email/phone redaction. This helper was
prepared after the call and cannot recover its absent historical subtype.

The original invocation refuses to run again when its retained schema exists.
A distinct schema-followup mode is prepared but has not been run or approved.
No further paid request is authorized by the completed one-call experiment.
The proposed followup keeps the same $0.10 request ceiling, model and retention
policy, and adds only fixed local schema subtype/location metadata. It needs a
fresh call approval; no production guard will be weakened based on a guess.

Operational script/result remain untracked under `tmp/`; the private prose
capture path is excluded via local Git metadata and no such file was created.
