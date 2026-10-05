---
title: 'Story 3.1 embedded source language correction'
type: 'bugfix'
created: '2026-10-05'
status: 'built'
route: 'oneshot'
route_source: 'auto'
review: 'quick'
review_source: 'auto'
lenses_ran: ['quick', 'quick-followup']
baseline_revision: 'a34a3feb7764d356c52280443ba92d9a4a3524e7'
context: []
---
<frozen-after-approval reason="human-owned intent">
## Intent
The approved bounded diagnostic captured Vietnamese summary prose containing an unquoted Chinese brand name. Require Vietnamese rendering of embedded source descriptions and generic Vietnamese wording when a proper-name rendering cannot be established. Preserve validation, source evidence, citations, uncertainty labels, saved reports and all prior reservations. This evidenced correction and local commit/dev release are authorized by the bounded resolution proposal; three fresh requests maximum, $0.03 batch and $0.01 per call. No remote push.
</frozen-after-approval>
## Implementation Notes
Small prompt correction uses oneshot. Advance prompt provenance without changing the schema. Verify synthetic mixed-script rejection and equivalent Vietnamese acceptance; run focused report suite. Rejected sample remains Git-excluded; only the conclusion and synthetic examples enter history.
## Plan Change Log
## Review Triage Log
## Verification
Focused report tests and independent quick review must pass. Live acceptance remains separate and must be recorded honestly.

Second capture proved a valid Vietnamese tissue description with an exact quoted source title failed the small lexicon. Add only evidenced Vietnamese product terms, preserving script checks, per-sentence cues, foreign-word rejection and thresholds. Prompt v4 also explicitly attributes product-title suitability/shipping claims. Quick reviewer found no issue in the initial prompt patch; rerun review for this additional correction.

Independent quick reviews of both correction stages found no concrete bugs or unmet intent. 147 report tests pass locally and in the non-root built image with networking disabled. The exact second retained field also passes corrected validation offline with its supplied title evidence. Live cloud acceptance is pending.
