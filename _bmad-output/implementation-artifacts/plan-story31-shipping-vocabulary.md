---
title: 'Story 3.1 shipping and service vocabulary false positive'
type: 'bugfix'
created: '2026-10-05'
status: 'built'
route: 'oneshot'
route_source: 'auto'
review: 'quick'
review_source: 'auto'
lenses_ran: ['quick']
baseline_revision: '4e3fa00afdf67a473277e6a3de3130ff41de99c9'
context: []
---
<frozen-after-approval reason="human-owned intent">
## Intent
Investigate the approved fresh language diagnostic and correct only failures supported by retained evidence. The redacted first finding is valid Vietnamese seller-attributed shipping/service prose; the small vocabulary recognizes 13 of 28 words against a 14-word threshold. Add missing evidenced Vietnamese shipping/service words, preserving sentence thresholds, foreign-word/script rejection, citations, score/credential guards and compact vi-text.v5 prompt. Keep previous reports/reservations unchanged. Single approved diagnostic under $0.01; no replay, retry, model/timeout/token increase or Git push. Retain only the bounded first field locally, excluded from Git; publish conclusions and synthetic regressions only. Review, verify and commit the correction locally for dev release. Further paid acceptance needs separate approval.
</frozen-after-approval>
## Implementation Notes
Small evidenced lexicon correction; oneshot. Add explicit validation-version metadata to distinguish corrected screening from older runs without claiming the prompt changed. Reuse strict report/provider fixtures. Exercise equivalent Vietnamese shipping wording and reject mixed foreign prose, unsupported scores and unknown citations. Retained exact capture is an offline check only, never a public fixture.
## Plan Change Log
## Review Triage Log
## Verification
Focused report suite, exact retained field offline, independent quick review and actual non-root offline image tests. Release by digest and verify health/settings. No unapproved generation.

Independent quick review found no concrete bugs or unmet intent. All 149 report tests passed locally and in the non-root offline image; parent separately verified the exact retained field offline. Diagnostic is one fresh dispatch, reservation $0.00251655, 1597 input / 943 output tokens, 21812ms, FAILED NON_VIETNAMESE_PROSE/findings.text. No live post-correction acceptance has run.
