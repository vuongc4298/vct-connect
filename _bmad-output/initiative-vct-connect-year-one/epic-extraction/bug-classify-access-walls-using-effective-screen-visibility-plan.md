---
title: 'Classify access walls using effective screen visibility'
type: 'bugfix'
ticket: '9'
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

**Problem:** CSS visibility misclassifies access walls. The recorded retrospective contains a reproducible defect in shared extraction behavior.

**Approach:** Use the shared static visibility boundary to resolve effective display, inherited visibility and opacity for supported screen styles.

## Boundaries & Constraints

**Always:** Preserve inline versus stylesheet priority, important priority, selector specificity, display subtree suppression and visibility inheritance. Do not execute source scripts or fetch external CSS. Existing identity, access precedence, layouts and provenance remain valid.

**Never:** Change authentication, quotas, schema, source URL admission or deployed browser activation. Do not claim unknown layouts or manual cloud acceptance passed.

## I/O & Edge-Case Matrix

| Scenario | Expected behavior | Failure handling |
| --- | --- | --- |
| Reported reproduction | Correct source/access outcome within budget | Explicit status; no fabricated evidence |
| Valid representative layouts | Preserve audited selected fields and provenance | Missing fields remain unknown |
| Unsupported or malformed input | Fail with a finite existing outcome | No unsafe fetch or uncaught source exception |

</frozen-after-approval>

## Code Map

- `backend/app/extraction/dom.py` — shared production boundary.
- `backend/app/extraction/browser.py` — consumes access classification and preserves HTTP evidence on fallback failure.
- `backend/app/extraction/browser_runner.py` — isolated computed-style collection must preserve descendants that explicitly override inherited visibility; verify the shared correction also survives actual rendering.
- `backend/tests/test_dom_visibility.py` — new independent behavioral regressions.
- `backend/tests/test_extraction.py`, `test_taobao.py`, `test_alibaba.py`, `test_browser_fallback.py` — existing cross-platform source and runtime regressions.

## Tasks & Acceptance

- [x] Correct the shared boundary without altering source binding or existing valid evidence.
- [x] Add regressions for the recorded failure and adjacent declared rules.
- [ ] Run affected adapter, merge and replay tests; run actual Chromium where supported.
- [ ] Review changed behavior and reconcile any confirmed review finding.

**Acceptance Criteria:**
- Given supported HTML with cascaded styles, when extraction classifies it, then visible login/CAPTCHA text stays visible and invisible text supplies neither a barrier nor selected evidence.
- Given valid audited pages, when the shared correction is used by all adapters, then status, selected fields and raw hashes remain correct.
- Given invalid inputs, when extraction stops, then the result is explicit and no inappropriate supplier snapshot is produced.

## Implementation Notes

The user authorized the six proposals and their execution on 2026-10-03. This plan narrows one independent fix from that accepted scope. Existing unrelated initiative/demo edits are preserved; work is on codex/extraction-retrospective-actions. Subagents are authorized by the build workflow; exact code write scopes are disjoint.

Implementation handoff: edit the scoped source/tests directly in the shared workspace, report every changed path, and do not commit. Other retrospective ticket/document work may appear concurrently; preserve it. Capture baseline-failing regressions by loading baseline source into a temporary isolated checkout/module, never resetting this checkout. Avoid a bespoke full CSS parser: keep the declared supported static boundary small, or use maintained parser dependencies with appropriate tests if needed.

The parent has already initialized bmad-build and read its rendered workflow. This is the explicit step-03 implementation handoff, not a fresh skill invocation. Do not render or restart the workflow; read this plan and its context and implement. The parent owns planning, ticket coordination, review and completion.

## Plan Change Log

## Review Triage Log

Parent unified loop 1 found direct regressions B4/B5/B6 and E1/E2, collector policy gap B8, and heading consumer gap V1. Re-derivation and per-finding evidence are recorded in `../../implementation-artifacts/plan-extraction-retrospective-actions.md`. Existing tests/security/provenance remain KEEP material; the final candidate is not qualified yet. Pre-existing unsupported selector/Unicode and transient mutation boundaries remain separate.

## Verification

Run the new regression module and affected adapter/replay/merge suites. Record real Chromium and disposable-database gates separately from skipped platform-only cases. No automatic release or full epic acceptance follows a passing local suite.

Implementation checkpoint: 152 passed / 76 gated real-browser cases skipped in the final scoped visibility/browser run. Parent adapter/parity/merge/replay union: 724 passed. Baseline isolated visibility regression: 61 failed / 38 passed, including all five reported cases. Actual browser changes (45 added cases) await the parent candidate image gate; no browser qualification is claimed by skipped tests. Full action-set review is owned by `../../implementation-artifacts/plan-extraction-retrospective-actions.md`.
