---
title: 'DeepSeek structured report compatibility'
type: 'bugfix'
ticket: ''
created: '2026-10-11'
status: 'built'
route: 'oneshot'
route_source: 'auto'
review: 'quick'
review_source: 'auto'
lenses_ran: ['quick']
review_loop_iteration: 0
baseline_revision: 'cc4437613bbfcbe4621974b8b1b11c12790a520a'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The operator-selected YEScale deepseek-v4.1-flash returns HTTP 200 but consumes all 1,800 completion tokens on reasoning and returns empty answer content. This prevents the approved historical 1688 sample from producing a report.

**Approach:** Disable thinking for structured chat requests to DeepSeek V4 and its documented flash/pro aliases, including provider-prefixed names. Keep the chosen model, bounded token budgets, schema validation and server-only credentials. Apply the same request setting to text and multimodal JSON generation; record it in model provenance. Leave other model requests and embedding requests unchanged. Given a supported DeepSeek model, when structured JSON is requested, then the request disables thinking and the saved settings reflect it. Given another model, when JSON is requested, then no DeepSeek parameter is sent. Verify only the already-approved saved 1688 sample through YEScale, and check the persisted report through the signed-in UI.

</frozen-after-approval>

## Implementation Notes

- Oneshot: a small shared request-settings function and focused adapter regression tests. Existing unrelated dirty files are preserved under the continuing audit authorization.
- Live diagnostic: response model cb/deepseek-v4.1-flash, finish_reason length, content length zero, completion/reasoning tokens 1800. Reasoning text was never printed or persisted.
- Official parameter reference: https://api-docs.deepseek.com/guides/thinking_mode/ documents thinking.type disabled and default enabled thinking.
- Live output after disabling thinking was too verbose and truncated. Supplier prompt v2 requests concise findings and explicitly enumerates canonical evidence references; schemas and token budgets are retained.
- Browser acceptance exposed same-ID reopening: openHistoryAnalysis cleared the report but the stopped polling effect did not restart because its ID dependency was unchanged. A reopenVersion dependency restarts lookup for History and Watchlist; two mounted regressions cover this. This is necessary to complete the original end-user report journey.
- Approved sample 1591350c-8239-4945-ad1c-f85ecde61f9e completed through normal worker assessment/report functions on attempt 4. A prior bounded attempt hit a transient provider connection failure. No other queued analysis was processed.
- Persisted provenance: model cb/deepseek-v4.1-flash, prompt.v2, thinking disabled, finish stop, 1074 input / 875 output tokens, latency 5182ms. Report has no overall risk score, confidence 0.475, coverage 0.5 and INSUFFICIENT_INFORMATION.
- 39 adapter/interpretation tests, 52 assessment/report/scoring tests and 7 PostgreSQL worker tests passed; 126 frontend tests and typecheck passed. Quick review returned no findings for adapter/prompt changes; final frontend delta review pending.
- Final quick review of the frontend reopening delta returned no findings. Production web build, configured server-secret scan and diff whitespace checks passed. Rebuilt browser verified same-ID reopening from both History and Watchlist, and refreshed report persistence. Only the approved sample was processed; no continuous worker is running.

## Plan Change Log

## Review Triage Log

- Quick review after adapter patch: no findings.
- Quick review after concise versioned prompt patch: no findings.
- Quick review after same-ID reopening patch: no findings. No deferred code findings.

## Verification

- Run intelligence, media and semantic-review adapter tests; require all pass.
- Run the approved sample using the real worker assessment/report functions; require completed persisted report and provenance with thinking disabled.
- Inspect browser report, source evidence, history reopening and Watchlist save/deduplication. Keep cloud/Chrome/second-account gates pending.
