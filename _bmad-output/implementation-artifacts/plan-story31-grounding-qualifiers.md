---
title: 'Story 3.1 source units and qualified claims'
type: 'bugfix'
ticket: ''
created: '2026-10-06'
status: 'built'
route: 'oneshot'
route_source: 'auto'
review: 'quick'
review_source: 'auto'
lenses_ran: ['quick']
review_loop_iteration: 0
baseline_revision: 'edb31e5472772cbf3800e59754450aef231d974d'
context: []
---

<frozen-after-approval reason="human-owned intent">
## Intent
Correct the demonstrated grounding gaps offline using the accepted v7/v4 local report: tissue pull counts must not become sheet counts, member-qualified positive-review rates must retain their population and metric, and a review's continued use must survive summarization. Include the title's price/shipping wording as an attributed unverified seller claim distinct from displayed starting prices and unknown final fees. Clarify general generation guidance and version it; add meaningful offline compatibility and source-projection regressions. Preserve Vietnamese prose, exact citations, uncalibrated model confidence, privacy, immutable saved reports, model/timeout/output limits and existing schema/validator/pipeline contracts. Do not add a semantic validation engine or claim fake-provider output proves model adherence. No paid request, rejected-content capture, dev deployment, registry push or Git push is included. The earlier missing cloud rejection remains unexplained and Story 3.1 remains partial.
</frozen-after-approval>

## Implementation Notes
Small prompt/version/test correction, expected below 100 changed code lines; oneshot route. Continue in the existing authorized codex/oct6-text-report worktree; preserve its operational tmp artifacts and primary checkout edits. Its tracked tree is clean at baseline. The generated workflow lives in the primary project, while this plan and changes stay in the implementation worktree for continuity.

Modify backend/app/interpretation/service.py SYSTEM with general distinctions: 抽 versus 张, metric/group qualifiers, continued use without inventing repeat purchases, and title shipping claims without assuming final pricing. Use compact attribution rather than repeated caveats to preserve the existing output budget. backend/app/interpretation/contracts.py changes PROMPT_VERSION only to vi-text.v8. Source projection and validation vi-prose.v4 need no change.

Update backend/tests/test_text_reports.py's authentic Taobao settlement case with hand-authored compact clauses retaining all corrected meanings and matching source evidence. Assert that source values and stable E1–E6 references survive projection without copying identities, and that settlement preserves claims, confidence provenance and one dispatch. Include independent differently phrased Vietnamese clauses covering these boundaries through full report validation, so an accidental language-screen incompatibility is detectable. Keep prompt version assertions synchronized. Do not write tests that merely search the prompt for the added instructions.

Acceptance: Given the authentic source, when minimized for generation, then title units/shipping wording, member review-rate qualifier and both review meanings remain available with the same citations and no private fields. Given correctly qualified hand-authored Vietnamese output, when settled and reopened offline, then it remains READY with cited evidence and explicitly uncalibrated confidence and cannot dispatch twice. Given the prompt update, when a new report settles, then its metadata identifies v8 while saved v7 records remain unchanged. Offline success does not close substantive live acceptance.

Implemented vi-text.v8 guidance and expanded the authentic settlement example plus four independent language-compatibility clauses. All 309 focused tests pass locally. No validator/projection change was needed. Hand-authored fixtures demonstrate compatibility only; model effectiveness and cloud acceptance remain unverified.

## Plan Change Log
## Review Triage Log
Medium / patch: reviewer found that corrected clauses were verified only in MemoryStore, while the PostgreSQL authentic reopen case had old unqualified content. Extended backend/tests/test_postgres_text_reports.py with corrected units, membership, continued use and attributed title shipping claim; assert reopened findings, citations, confidence provenance, v8 metadata and exactly one dispatch. All 13 PostgreSQL checks pass after correction; reviewer rechecked and found no remaining findings. No deferrals. Thorough lenses skipped for this small prompt/test correction.
## Verification
Run the focused report/language corpus tests locally, then the same tests in the non-root backend image with network disabled and scripts mounted read-only. Run the existing isolated PostgreSQL fake-provider owner/reopen/settlement suite without provider networking. Verify the accepted local v7 diagnostic retains its canonical hash and one dispatch with no additional generation. Independent quick review is required; record its findings and any corrections before a specific-file conventional local commit. Record exact checks, local commit and unchanged live release in the result and continuation handoff.

Completed: 309 focused tests locally and final non-root offline image, 13 PostgreSQL tests; accepted v7 report hash unchanged with one dispatch. Image sha256:107b7e1178af2ca36f5753e89dd672cc8f1a0e417db4472cd20501a0b95cd605. No paid request or deployment. Full evidence and semantic acceptance rubric: story31-grounding-qualifiers-result.md.
