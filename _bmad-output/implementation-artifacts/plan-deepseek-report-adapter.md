---
title: 'Accept configured DeepSeek returned version and bound thinking'
type: 'bugfix'
ticket: ''
created: '2026-10-05'
status: 'built'
route: 'oneshot'
route_source: 'auto'
review: 'quick'
review_source: 'auto'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
baseline_revision: '541d99e827f31b7cd9e4a8ecb1378ed25d6ed7ca'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The approved DeepSeek V4.1 Flash rehearsal requested
`deepseek-v4.1-flash` but YEScale returned `deepseek-v4-1-flash-260910`; the
existing exact equality guard rejected it. The request consumed all 2400 output
tokens in 58 seconds. DeepSeek documents default high-effort thinking, although
the first call's retained trace does not establish its exact finish reason.

**Approach:** Add an optional exact expected returned model ID, retaining strict
equality to that configured ID and defaulting to the requested ID for existing
configurations. Add an optional explicitly validated thinking setting; disable
thinking for the deliberate second DeepSeek rehearsal. Preserve requested and
expected/actual returned IDs plus thinking configuration in backend provenance.
Test accepted mapping, rejected alternatives, unchanged default requests,
invalid thinking configuration and report service validation. Preserve all
budget, evidence, citation, output, deadline and no-retry controls. Use a new
analysis for any approved live verification; never requeue the first dispatch.
User approved this fix in the existing worktree while preserving rehearsal files.

</frozen-after-approval>

## Implementation Notes

One-shot route: about 25–35 implementation lines and 40–60 test lines across
provider.py, service.py and test_text_reports.py. Backend settings only;
deployment configuration and Azure activation remain subsequent work. Existing
API/model metadata stays backward compatible. No prefix matching, automatic
alias discovery or acceptance of arbitrary returned models. The named returned
version is provenance, not proof of immutable vendor routing.

Added YESCALE_EXPECTED_RETURNED_MODEL and YESCALE_THINKING with strict enum
validation. Service and adapter share exact returned_model_matches guard.
Default request omits thinking; explicit disabled emits DeepSeek's documented
body shape. 86 focused tests passed. Quick reviewer launched with inherited
parent model; all retained untracked operational evidence included in review diff.

## Plan Change Log

## Review Triage Log

Quick review: no actionable bugs, rule violations or unmet implementation intent.
Reviewer correctly notes that post-fix live acceptance remains pending; it is
recorded as operational verification rather than claimed from automated tests.
No deferred findings. All 86 focused tests and 10 isolated PostgreSQL tests pass;
git diff --check passes. One existing Starlette/httpx deprecation warning.

Post-build live verification exposed a reachable validator false positive:
valid Vietnamese descriptions of fabric, returns, payment and disputes failed
NON_VIETNAMESE_PROSE because the lexicon lacked ordinary purchasing vocabulary.
Verdict medium, route patch: extend the lexicon without changing foreign-script,
English-word, per-sentence cue, citation, score or schema guards. Six regressions
cover the observed rejected phrases. 92 focused tests pass. The retained paid
diagnostic response now passes validation offline; failed database jobs were
not changed and no additional paid request was needed for this verification.

Second quick review of the language correction: no actionable findings.
Committed as 2762ce8. A subsequent fresh-analysis live completion check timed
out at 90s; YEScale reconciled it as upstream 503/transient_upstream with no
displayed charge. Kept UNCERTAIN and its reserve; no replay. Provider availability
is an external limitation, not a reason to relax report validation. Final live
READY persistence remains unverified; saved real diagnostic output validates
offline after the correction. Four calls cost approximately $0.0035 at dashboard
precision. Deployment remains pending.

## Verification

- Run backend/tests/test_text_reports.py: all provider and service cases pass.
- Run backend/tests/test_postgres_text_reports.py against disposable PostgreSQL
  with an isolated pytest temp directory: defaults/persistence remain valid.
- Review a diff against the canonical baseline with a context-free quick reviewer.
- A deliberate live call uses 90s, $0.10 per-call, $0.10 available-balance cap;
  preserve the earlier $0.0016 charge in total accounting. Retain the new ledger,
  inspect schema/citation/Vietnamese quality and reconcile dashboard billing.
