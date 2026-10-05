# Compact report implementation and single acceptance request

Status: implementation reviewed, committed and deployed; single authorized paid test consumed; Story 3.1 live acceptance remains open.

## Implementation and release

The operator approved compact prompt guidance and one fresh owner-scoped acceptance request under the previous $0.01 per-call ceiling. Prompt vi-text.v5 guides at most two summary sentences, six findings, three limitations, three actions and one confidence-basis sentence, with per-field character targets totaling 2200 prose characters. This is generation guidance, not a strict structural/token guarantee. Schema text-report.v2, validation guards, model, 120-second deadline and 2400-token cap remain unchanged. No saved reports or reservations were reset.

Code commit d303ec498bbecd5dbca02cac2537c13297d8b6e3 is local, not pushed. Independent quick review found no concrete issues. All 147 focused tests passed locally and in the built non-root image with networking disabled, including truncation rejection and no retries.

Backend digest sha256:f38cf33002a9c6001d5c18e846a57a3316eb33ced48879124480ee6dc061c1ec. API vct-connect-dev-api--0000013 and dispatcher vct-connect-dev-dispatcher--0000022 are Healthy / Provisioned / Running. Analysis/migration job templates use the same digest; effective settings and secrets preserved. Web image unchanged.

## Live result

Analysis 3d7823f1-36c6-418f-9754-4f8c31cce090, immutable snapshot 7b8f953e-97b4-4065-ad72-ab3133ac1ac7. Exactly one dispatch c1e5d1fa-7a36-4aa4-9677-d33ee9502140. Request 20261005195247258444093gn2te5zE, expected returned model deepseek-v4-1-flash-260910, thinking disabled. Prompt vi-text.v5 / schema text-report.v2.

Complete provider response: 1597 input / 991 output tokens, latency 20901ms. This run avoided the earlier 2400-token truncation. Validation then failed INVALID_OUTPUT / NON_VIETNAMESE_PROSE / findings.text. No rejected body or prose was retained from this cloud test. Foreign content versus another vocabulary false positive cannot be determined from metadata, and section-count adherence or translation quality cannot be claimed. No READY report or self-confidence/reopen acceptance exists.

Owner-scoped browser reopen preserves the failure and public source extraction with unknown capture freshness. Screenshot tmp/story31-v5-language-rejection.jpg. No retry, replay, fallback generation, model change or new paid diagnostic occurred.

Reservation $0.00251655, within $0.01. Configured-rate usage estimate $0.00083415; displayed billing detail charge $0.0008, rounded balance $0.0828. Actual invoice cost unknown/null. Cloud ledger seven retained dispatches / $0.01550865; local retained reservations $0.02133555; combined $0.03684420, within the conservative $0.09 cap. Cloud pending jobs zero. Prior diagnostic captures remain Git-excluded.

## Remaining gate

The next investigation must inspect a safely redacted first failing field under an explicitly authorized fresh diagnostic, or evaluate the Vietnamese screen against an independently labeled offline corpus. Do not weaken the screen or claim the cloud rejection is a false positive without evidence. Further paid requests require separate authorization; the single-request approval is consumed. Story 3.1 remains partial, with downstream stories governed by their original dependencies.
