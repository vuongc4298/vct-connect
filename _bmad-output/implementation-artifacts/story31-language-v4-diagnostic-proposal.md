# Proposed bounded language v4 diagnostic — 2026-10-06

Status: pending explicit operator approval. No diagnostic request, capture or new spending fence has run. The previous approval authorized the completed cloud acceptance only.

Completion update: the operator subsequently approved this exact proposal. One local request ran and returned READY; no rejected prose was retained. Authorization is consumed. The original pending text above records proposal-time state. See story31-language-v4-diagnostic-result.md for the outcome, retained spending, substantive gaps and next offline scope.

Run one fresh local provider diagnostic, capped at $0.01, using the sanitized authentic Taobao fixture and current evidence projection, vi-text.v7 prompt, text-report.v2 schema and vi-prose.v4 validator. Preserve configured deepseek-v4.1-flash and expected returned deepseek-v4-1-flash-260910, thinking disabled, 120-second deadline, 2,400-token output limit, and no retry. Do not replay a failed cloud job or automatically run another acceptance.

Retain only the first rejected findings.text, redacted, at most 1,600 characters and 8,000 UTF-8 bytes, in tmp/story31-resolution-call-language-v4.private.json. This exact path is Git ignored and currently absent. Retain no entire response, headers, credentials, HTML, account/reviewer identifiers, URLs or contact fields. Keep rejected cloud prose discarded. If rejection is in another field, schema/credential validation fails, or safe redaction cannot be established, save safe metadata only and no prose. A successful response requires no rejected-prose capture.

The prepared local helper passes its offline self-test without provider calls or captures. Its broader field capability is not authorized by this proposal: the execution wrapper must restrict retention to findings.text and enforce the stated limits and credential checks. Create a fresh exclusive one-request fence only after approval; consume it on the single dispatch and retain uncertain spend. Preserve all earlier reservations, snapshots, dispatches and private captures.

Maximum configured reservation is $0.0051936, within the $0.01 call cap. Combined retained reservations would be at most $0.05789820 ($0.05270460 existing plus $0.0051936), within the $0.09 aggregate cap. Configured-rate estimates, displayed gateway charges and unknown invoice actuals must remain distinct. No top-up or ledger reset is included.

Purpose: inspect one concrete rejected finding to distinguish a genuine language violation from an evidenced validation false positive. The diagnostic may fail to produce a safely retainable finding. Record that outcome without retry. Any subsequent implementation correction should use the resulting evidence and offline verification; deployment and additional paid acceptance are outside this proposal.
