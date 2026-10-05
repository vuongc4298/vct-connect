---
title: 'Restore saved report source in the submission form'
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
baseline_revision: '3158f3024aee5896bec1f886be0d68ffcab21a89'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Reopening an owned uploaded-page report leaves the submission form
on the default fixture URL and fixture badge, although the saved evidence is real.

**Approach:** Initialize the form source from the first successful owned analysis
response for every extraction method. Use the persisted method for progress;
do not infer extension capture from the presence of an analysis link. Subsequent
polls must not overwrite a buyer editing the next submission's URL.

</frozen-after-approval>

## Implementation Notes

Small frontend state correction, fewer than 100 changed code lines: oneshot.
Existing worktree and operational artifacts are retained under prior approval.
The form badge describes the next submission, while extraction evidence describes
the saved result. No paid report regeneration is needed for verification.

`page.tsx` initializes source and method from the first successful response in
each polling effect; subsequent responses preserve form edits. Removed the
extension-only assumption during link restoration. Mounted regression now runs
against USER_UPLOAD, PUBLIC_HTTP and EXTENSION_DOM.

Verification: 80 frontend tests passed and workspace typecheck passed. Initial
sandbox run prevented esbuild reading workspace ancestors; the same suite
passed under approved execution outside that restriction.

## Plan Change Log

## Review Triage Log

Quick independent review found no actionable findings. Specialized adversarial
and multi-lens reviews were skipped for this small state correction.

## Verification

- Mounted Page regression: Given an owned uploaded, public or extension analysis,
  when its report is reopened, then the input uses its actual source and the form
  does not show the fixture badge.
- Existing frontend tests and typecheck pass.
- Given the deployed existing READY report, when reloaded signed in, then the
  source URL is correct, the saved report remains visible and no submission occurs.
