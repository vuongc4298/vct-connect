# Approved schema followup result

2026-10-05. The operator approved exactly one new schema diagnostic. One local
dispatch ran; no replay, additional paid call, validator change or deployment ran.

Analysis `9a17fa59-c036-4b1e-91f1-631b40c20950`, snapshot
`53746125-523a-415d-b2d7-a3bdfe8d1935`, schema
`story31_schema_diagnostic_20261005`, dispatch
`fb737c27-01e7-4bce-9963-df8bf23e6098`.

The returned report passed strict structural schema validation. It then failed
`NON_VIETNAMESE_PROSE / summary`. Safe schema detail is null because this response
had no structural failure. This does not recover the previous call's unknown
schema subtype or prove its cause. No prose was captured: the approved storage
rule covered only rejected `findings.text`, not summary. The proposed capture
was too narrow for the observed variation; rejected response text is now absent.
No language guard correction is supported by the available evidence.

Same model/settings/fixture as before: requested `deepseek-v4.1-flash`, returned
`deepseek-v4-1-flash-260910`, thinking disabled, deadline 120s, output cap 2400,
prompt/schema v2. Request `20261005190754518894982uMZOhsy9`, 1304 input / 1995
output tokens, application latency 28062ms, input 4538 bytes. Snapshot, reviews,
raw evidence and extraction result remained unchanged.

Retained reservation $0.0022743, configured-rate usage estimate $0.0013926,
actual cost unknown/null. YEScale detail at 19:08:22 Asia/Bangkok shows charge
$0.0012, gateway latency 27727ms and rounded balance $0.0883. The request-list
row has different rounding; these dashboard amounts are not invoice values.

Prior local reservations $0.0144495 and cloud reservations $0.0106119 were
accounted for before dispatch. Current combined retained reservations are
$0.0273357, leaving $0.0626643 under the conservative $0.09 cap. Previous
failed/uncertain jobs and reservations remain intact. The used local schema
prevents this invocation from repeating.

## Prepared correction to the diagnostic design

An offline helper now identifies the first rejected prose field among summary,
finding text, limitation, action, or confidence basis. It retains at most one
redacted field, bounded to 1600 characters / 8000 UTF-8 bytes, and withholds
credentials, ambiguous duplicate members, markup and account-shaped identifiers.
It saves nothing on structural errors; fixed schema subtype/location metadata
remains available for those failures.

Offline checks passed across all five prose fields, first-failing-item selection,
URL/email/phone redaction, literal/escaped credentials, size bounds, valid output,
duplicate keys and unsafe markup/identifier withholding. The helper is untracked
under `tmp/story31_prose_capture.py`; it has not been used on a live response.

Capturing summary or other prose exceeds the earlier findings-only policy and
requires approval of `story31-bounded-resolution-proposal.md`. The proposed
bounded batch also needs new spending authorization. Story 3.1 remains incomplete;
the working saved v1 demo and deployed v2 implementation remain available.
