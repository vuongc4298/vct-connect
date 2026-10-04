---
title: 'Bound decoded public response memory before allocation'
type: 'bugfix'
ticket: '10'
created: '2026-10-03'
status: 'in-progress'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: []
review_loop_iteration: 0
baseline_revision: '50c9f37df40476c8be22f1a49af745e0a4e120e8'
context: ['_bmad-output/initiative-vct-connect-year-one/epic-extraction/epic-extraction.md']
---

<frozen-after-approval reason="human-owned intent — user authorized applying retrospective proposals">

## Intent

**Problem:** Public response decompression exceeds the byte budget. The recorded retrospective contains a reproducible defect in shared extraction behavior.

**Approach:** Bound streaming decoded output before applying the shared page byte cap.

## Boundaries & Constraints

**Always:** Preserve decoded response-byte hashes, charset handling, bounded retries, redirect safety and deadlines. Cover identity, gzip and deflate encodings, malformed compressed input and incremental output. Unsupported encodings fail explicitly.

**Never:** Change authentication, quotas, schema, source URL admission or deployed browser activation. Do not claim unknown layouts or manual cloud acceptance passed.

## I/O & Edge-Case Matrix

| Scenario | Expected behavior | Failure handling |
| --- | --- | --- |
| Reported reproduction | Correct source/access outcome within budget | Explicit status; no fabricated evidence |
| Valid representative layouts | Preserve audited selected fields and provenance | Missing fields remain unknown |
| Unsupported or malformed input | Fail with a finite existing outcome | No unsafe fetch or uncaught source exception |

</frozen-after-approval>

## Code Map

- `backend/app/extraction/fetch.py` — shared production boundary.
- `backend/app/extraction/browser.py` — consumes access classification and preserves HTTP evidence on fallback failure.
- `backend/tests/test_response_limits.py` — new independent behavioral regressions.
- `backend/tests/test_extraction.py`, `test_taobao.py`, `test_alibaba.py`, `test_browser_fallback.py` — existing cross-platform source and runtime regressions.

## Tasks & Acceptance

- [x] Correct the shared boundary without altering source binding or existing valid evidence.
- [x] Add regressions for the recorded failure and adjacent declared rules.
- [ ] Run affected adapter, merge and replay tests; run actual Chromium where supported.
- [ ] Review changed behavior and reconcile any confirmed review finding.

**Acceptance Criteria:**
- Given compressed public HTML, when extraction reads it, then decoding remains within the configured allocation budget on every path. Exceeding capacity terminates extraction with status PARSE_FAILED, reason PAGE_TOO_LARGE and no snapshot. Verification observes decoder output allocations and cumulative chunks; rejection alone cannot pass.
- Given valid audited pages, when the shared correction is used by all adapters, then status, selected fields and raw hashes remain correct.
- Given invalid inputs, when extraction stops, then the result is explicit and no inappropriate supplier snapshot is produced.

## Implementation Notes

The user authorized the six proposals and their execution on 2026-10-03. This plan narrows one independent fix from that accepted scope. Existing unrelated initiative/demo edits are preserved; work is on codex/extraction-retrospective-actions. Subagents are authorized by the build workflow; exact code write scopes are disjoint.

Implementation handoff: edit the scoped fetch source and response-limit tests directly in the shared workspace, report every changed path, and do not commit. Other retrospective ticket/document work may appear concurrently; preserve it. Capture baseline-failing regressions in an isolated temporary baseline module/checkout, never resetting this checkout. Verify MockTransport pre-read response compatibility as well as production raw streaming. Observe bounded decoder output allocations, not only the final rejection code.

The parent has already initialized bmad-build and read its rendered workflow. This is the explicit step-03 implementation handoff, not a fresh skill invocation. Do not render or restart the workflow; read this plan and its context and implement. The parent owns planning, ticket coordination, review and completion.

## Plan Change Log

- 2026-10-03: Independent pre-execution validation tightened the acceptance wording to require bounded allocation on failure as well as success. This clarifies the approved A2 scope; rejection after an oversized allocation is insufficient.

## Review Triage Log

Parent unified loop 1 verified B1/E3: a valid raw-deflate stream can start with a plausible zlib header and be falsely rejected. The non-frozen format decision is being re-derived with bounded initial replay, preserving all decoded allocation, malformed-input, provenance and retry gates. Full evidence and KEEP instructions are in `../../implementation-artifacts/plan-extraction-retrospective-actions.md`; the final candidate is not qualified yet.

## Verification

Run the new regression module and affected adapter/replay/merge suites. Record real Chromium and disposable-database gates separately from skipped platform-only cases. No automatic release or full epic acceptance follows a passing local suite.

Implementation checkpoint: 775 passed / 76 gated browser cases skipped in affected adapters, browser policy, merge/replay/parity. New module: 103 cases; six allocation regressions fail against isolated baseline, observing up to 32 MB output allocation. Retained content is capped at 2,000,000 bytes; a separately bounded one-byte overflow detector distinguishes exact capacity from larger pages, is never retained or parsed, and makes cumulative decoder output at most 2,000,001 bytes. Already pre-read client responses were decoded before this boundary and cannot have those external allocations prevented here; production uses raw streaming. Parent owns actual candidate/browser/database gates and the unified action-set review.
