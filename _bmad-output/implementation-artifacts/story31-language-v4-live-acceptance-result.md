# Language v4 live acceptance — 2026-10-06

The operator approved one fresh owned acceptance request capped at $0.01, with the same model, 120-second deadline, 2,400-token output limit and no retry. It ran exactly once after the v4 release and successful preservation preflight. This authorization is consumed.

Extraction completed with partial source coverage. The report failed INVALID_OUTPUT: safe metadata reports NON_VIETNAMESE_PROSE at findings.text. The rejected report is null and no rejected prose was retained. The exact wording, and whether this was foreign prose or a screen false positive, remain unknown. Substantive grounding, citation and confidence acceptance were not reached; Story 3.1 remains partial.

Analysis: 266e5112-e6c3-4161-8a11-2ab808dc1a83. Snapshot: a86cebea-f120-4cf7-ae1e-19495bbee55c. Dispatch: 73670aad-17e5-499e-b4c5-e4bfe6adeb08. Gateway request: 20261006013140444452264h7PmPJBS. Versions: vi-text.v7 / text-report.v2 / vi-prose.v4. Returned model deepseek-v4-1-flash-260910 matches the expectation for configured deepseek-v4.1-flash, thinking disabled. Usage: 2,050 input / 926 output tokens, 2,976 total; input 8,291 bytes; application latency 17,172 ms. No truncation or deadline failure was reported.

Repeated owned Store reads agree. The saved failure and extracted source reopen successfully, with identical rendered failure text and exactly one dispatch. No retry, replay, reset, top-up or relabeling occurred. Prior saved records remain historical evidence.

Reservation: $0.00283725. Configured-rate estimate: $0.0008631, not an invoice. YEScale's exact request detail displays $0.0006, while its table displays $0.0005. Displayed balance after is $0.0794; its difference from the prior request's $0.0793 is unreconciled. Actual invoice cost remains unknown/null; these UI values do not justify releasing reservations. Cloud ledger: 12 dispatches, $0.02885250 retained, pending zero. Local retained reservations: $0.02385210. Combined retained: $0.05270460, within $0.09.

Evidence: tmp/story31-language-v4-acceptance-result.json; consumed tmp/story31-language-v4-acceptance.fence.json; safe inspection tmp/story31-cloud-language-v4-acceptance-logs.json; visually inspected saved-reopen proof tmp/story31-language-v4-validation-rejection.jpg. No implementation change or additional test suite was needed for this operational acceptance. Deployed code remains 927383b7d833e841ac15043e0f68dcdc16d8e37f at healthy API18/dispatcher27. No Git push.

Next: the separately scoped local diagnostic in story31-language-v4-diagnostic-proposal.md is pending approval. Reason/location alone does not justify another vocabulary change or weakened validation. A later fresh acceptance must still check source meaning, citations, explicitly uncalibrated confidence and owned reopening.
