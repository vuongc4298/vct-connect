---
title: 'Story 3.1 offline prose-screen coverage'
type: 'bugfix'
created: '2026-10-05'
status: 'built'
route: 'oneshot'
route_source: 'auto'
review: 'quick'
review_source: 'auto'
lenses_ran: ['quick']
baseline_revision: '29667d9a1227b6fbe23ae5d7bdbd5d9db55e044f'
context: []
---
<frozen-after-approval reason="human-owned intent">
## Intent
Broaden offline coverage before further paid attempts, and correct supported Vietnamese screen gaps. Use synthetic source-related wording spanning product/title claims, reviews, packaging/texture, prices, shipping/service, metrics, missing evidence, freshness, verification actions and interpretation confidence. Include foreign/mixed-language negatives, ambiguous text and Unicode normalization. Preserve sentence thresholds and language/script, citation, credential and score guards. No new paid request, model/timeout/token change, legacy report modification or Git push. Verify/review, commit locally and release the supported correction to existing dev resources. Story3.1 live acceptance remains separate.
</frozen-after-approval>
## Implementation Notes
Small code/data change under100 lines; oneshot. Agent-curated synthetic examples are development regressions, not independent language accuracy calibration. Baseline vi-prose.v2 misclassifies3/33 positives (smooth packaging, including decomposed accents) and0/24 negatives. Other tested domain wording already passes. Add only the missing demonstrated packaging vocabulary and advance validation_version to vi-prose.v3. Prompt vi-text.v5 and schema text-report.v2 stay unchanged. Corpus labels describe language only, not truth or safety of statements. Retained private model samples never enter the corpus.
## Plan Change Log
## Review Triage Log
## Verification
Run all focused report tests plus corpus cases, meaningful negative guards and existing integration/settlement regressions. Independent quick review includes corpus labels and source context. Verify actual non-root offline image, deploy by digest and check health/settings. No live generation is part of this change; report coverage scope honestly.

Independent quick review found no actionable findings; corpus labels and NFC/NFD behavior checked. All206 focused tests pass locally and in the non-root offline image; all13 isolated PostgreSQL settlement tests pass using fake providers. Review initially skipped database tests without configured DB; parent subsequently ran them successfully against the disposable database. No paid provider calls.
