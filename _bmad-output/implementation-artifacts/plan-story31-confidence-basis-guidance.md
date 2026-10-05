---
title: 'Story 3.1 confidence explanation guidance'
type: 'bugfix'
ticket: ''
created: '2026-10-05'
status: 'built'
route: 'oneshot'
route_source: 'auto'
review: 'quick'
review_source: 'auto'
lenses_ran: ['quick']
baseline_revision: '18ea6da21296cec37c012bb798fa0661b7ef275b'
context: []
---
<frozen-after-approval reason="human-owned intent">
## Intent
Review the confidence prompt and unsupported-score guard offline after the single live acceptance failed at self_reported_confidence.basis. Clarify the existing dedicated numeric score versus qualitative Vietnamese basis contract, and verify supported qualitative/source-number explanations against prohibited score claims. Preserve the conservative score guard, language/citation/credential protections, application-owned uncalibrated labels, model/settings and immutable prior reports. No paid generation, rejected cloud prose retention, deployment or Git push in this offline slice. Unknown rejected cloud wording must remain unknown; synthetic examples do not establish its root cause or successful live acceptance.
</frozen-after-approval>
## Implementation Notes
Under100 changed code/test lines; oneshot. The existing regex rejects synthetic qualitative confidence-label sentences containing a source count or the ordinary word một. Other qualitative/evidence wording already passes. Clarify basis instructions to describe evidence limits without a confidence label or repeating a score; give a conditional example only when source incompleteness supports it. Bump prompt version to vi-text.v6; preserve validation vi-prose.v3 and schema text-report.v2. Add fake-provider settlement regressions for accepted qualitative bases with counts/prices, rejected actual score claims across all prose fields, and safe rejection metadata/no retry. Keep known conservative guard limitations explicit rather than weakening it without a broader validated design.

Implementation: added explicit qualitative basis guidance with conditional incomplete-evidence example, no score labels/score repetition in basis, and distinction between source numbers and confidence. Added30 fake-provider regression cases; all236 focused tests pass. No guard/schema/dispatch code change, no provider request or deployment.
## Plan Change Log
## Review Triage Log
Quick reviewer reported no findings, confirmed intent and guard/schema/settlement preservation. Thorough lenses skipped for this bounded prompt/test change. Existing conservative score-regex overmatching was recorded in deferred-work.md; prompt clarity does not claim to fix general validation semantics.
## Verification
Given complete fake provider output with qualitative Vietnamese basis and ordinary evidence counts/prices, when processed once, then it stores READY with application-owned model_self_reported/uncalibrated labels and prompt vi-text.v6 metadata. Given numeric or number-word unsupported confidence/risk scores in prose, when validated, then it fails safely with UNSUPPORTED_SCORE and the allowlisted location and does not retry. Given the new prompt, when inspected, then it explicitly forbids score repetition in basis and requires an evidence-dependent qualitative explanation. Run all focused report tests locally and independent quick review; no live provider request or claim of Story3.1 acceptance.
