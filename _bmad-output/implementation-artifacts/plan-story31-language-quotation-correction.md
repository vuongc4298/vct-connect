---
title: 'Story 3.1 Vietnamese screen and evidence-bound quotation correction'
type: 'bugfix'
created: '2026-10-06'
status: 'built'
route: 'oneshot'
route_source: 'auto'
review: 'quick'
review_source: 'auto'
lenses_ran: ['quick']
baseline_revision: '6ae1aeae552b368f77e7a14e03afab89f7f07ebe'
context: []
---

<frozen-after-approval reason="human-owned intent">
## Intent
Correct the demonstrated language and quotation faults offline before another live attempt. Preserve sentence coverage/diacritic/script thresholds; cover natural Vietnamese compact clauses and reject demonstrated English insertions. Only exact supplied source text may be exempted as a quotation, including straight/curly double quotes, single quotes and backticks. Confidence basis has no source quotation exemption. Preserve stable safe rejection reasons/locations, credential/score/citation/schema checks, no retry and immutable saved results. Version the changed validator. Use broader independently authored language contrasts and meaningful integration tests, then independent review and local commit. No paid call, rejected-output capture, dev deployment, model/prompt/schema change or Git push. This bounded heuristic correction does not claim general language calibration or establish the missing v7 response's cause.
</frozen-after-approval>

## Implementation Notes
Estimated small contracts/tests/data correction; oneshot. Reuse longest-first escaped exact-source pattern and single-pass removal, extending quotation delimiters rather than removing arbitrary spans. Remove unconditional quote deletion from direct screen. Recognized Vietnamese terms are evidence-supported offline vocabulary, not provider-response guesses; known English purchasing/shipping fragments are rejected even within otherwise Vietnamese sentences. Quote-only output must still fail for lack of Vietnamese context; appended/unquoted foreign prose stays visible. Existing apostrophe variants and nested sources retain deterministic matching. Baseline tests contain one unsupported double-quote source exemption; supply actual source value for that legitimate quotation. The original57 corpus and new25 boundary probe remain language-labeled fixtures; add independent contrasts and check direct versus report validation separately where authentic quotation changes the path. Numeric/schema failures stay separate in the evaluator.

Acceptance: Given existing and boundary language cases, when screened/validated offline, then demonstrated Vietnamese clauses pass and foreign/mixed cases fail. Given exact quoted supplied evidence plus Vietnamese context, when validated, then it passes; absent/mismatched quotations and quoted confidence basis do not hide foreign prose. Given failure or readiness, when settled with fake providers and reopened, then versions, safe metadata, citations/confidence and single dispatch behavior remain correct.

Implementation: vi-prose.v4 removes unconditional quotation stripping, extends exact supplied-source quote delimiters, recognizes demonstrated vocabulary, rejects any listed English fragment and unexempted non-Latin alphabetic characters. Thresholds and other guards remain. Independent24-case probe exposed six additional product-description gaps, corrected without changing coverage thresholds. One new quote control initially lacked Vietnamese diacritics after source removal; corrected its framing to Nguồn ghi, preserving the existing ambiguous-prose rule. All305 focused tests pass locally/final offline non-root image; all13 isolated PostgreSQL checks pass. No dev release or paid generation.

## Plan Change Log
## Review Triage Log
Independent quick review: no actionable findings. Reviewer reran305 focused tests and supplementary quotation controls. Parent separately verified13 PostgreSQL tests and final non-root offline image. Thorough adversarial/edge/verification lenses skipped for this small correction; language calibration remains outside scope.
## Verification
Run focused report tests and offline probe evaluator; broaden with independently authored cases and quote controls. Run isolated PostgreSQL settlement/owner/reopen tests with fake providers. Build and verify the non-root backend image without provider networking, mounting the offline scripts directory read-only for the investigation-tool tests because runtime image intentionally includes backend only. No registry push or dev release.
