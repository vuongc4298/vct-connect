---
title: 'Find recurring complaints and statistical review anomalies'
type: 'feature'
ticket: '2'
created: '2026-10-06'
status: 'in-progress'
baseline_revision: '58d9baacf337a0bd04eb9c0c3ca02d867aca86e7'
route: 'full'
route_source: 'auto'
review: ''
review_source: ''
lenses_ran: []
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Saved reviews lack reproducible complaint/anomaly analysis. Extraction
retains limited, often deduplicated samples without individual dates/ratings.

**Approach:** Build a pure, versioned ReviewAnalysis module grouping explicit
complaint matches and duplicate/timing/rating-text/volume indicators with cited
evidence, limitations and qualitative reliability. Story 3.2 accepts fixtures;
3.3 adds semantics and 3.7 integrates persistence/worker.

## Boundaries & Constraints

**Always:** Evidence IDs preserve snapshot identity/ordinal; retain source URL,
matched spans and rule/version. Keep report-local E IDs separate. Same input/version
yields identical JSON without clock/random dependence. Counts describe retained
occurrences, not independent buyers or population prevalence.

Missing dates, individual ratings/scales, sampling, history and freshness remain
unknown. Shop ratings never substitute for review ratings. Checks distinguish
detected/no match/unavailable with eligible denominators/reasons. Exact scoped
totals differ from accessible counts; approximate display counts remain approximate.

Rules are development heuristics, not calibrated probabilities. Qualitative
reliability/confidence retain bases/unknowns; no indicators never certifies trust.
No complaint triggers a critical override or fake-review/misconduct claim.

**Never:** Change extraction/merging or saved reports; recover discarded duplicates;
call providers; add embeddings/media/risk scores; change DB/worker/API/UI; deploy
or spend money. Lifecycle/report integration remains 3.7.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
| --- | --- | --- | --- |
| Complaint | Two explicit same-topic phrases | Candidate topic/count/spans | Exclude negation/praise |
| Duplicate | Separate ordinals, equal normalized bodies | Sample-local group | Exclude empty; disclose truncation |
| Sparse | Legacy text-only fixture | Text checks; other checks unavailable | No invented population rate |
| Timing/rating | Sourced individual metadata | Eligible-sample indicators | Exclude invalid/ambiguous values with reasons |
| Volume | Comparable complete windows | Cited spike indicator | Missing/incomparable/zero baseline unavailable |
| Invalid | Oversize/malformed/nonfinite/bool inputs | Typed failure | No mutation, partial assessment or value leakage |

</frozen-after-approval>

## Code Map

Checkout: `C:/Users/eidel/Desktop/VCT Connect/tmp/oct6-text-report-worktree`;
relative paths refer there. Preserve primary unrelated edits and operational `tmp/`.

- `backend/app/extraction/contracts.py`: reviews guarantee text/source_url only.
- `backend/app/extraction/{offer1688,taobao,alibaba,extension_merge,renormalize}.py`: deduplication and 20-review/2,000-character retention preclude population claims.
- `backend/app/interpretation/service.py`: E IDs cover minimized first-12 projection; preserve prompts.
- `backend/app/storage.py`: existing snapshots/ownership; integration belongs to 3.7.
- `backend/tests/fixtures/taobao_item_1076425861755.html`: authentic compatibility fixture, not benchmark.
- Specification sections 10/12/14–16 and tickets 3.2/3.3/3.7 establish these boundaries.

## Tasks & Acceptance

**Execution:**
- [ ] `backend/app/review_analysis/{contracts,__init__}.py` — bounded input/results, sourced optional metadata, versions and typed failures; legacy compatibility.
- [ ] `backend/app/review_analysis/rules.py` — conservative Chinese/Vietnamese/English phrases, negation exclusions and parameters.
- [ ] `backend/app/review_analysis/service.py` — pure analyzer, evidence/eligibility/limitations and qualitative reliability.
- [ ] `backend/tests/fixtures/review_analysis_cases.json`, `backend/tests/test_review_analysis.py` — labeled positives/negatives/boundaries, authentic compatibility, replay and references.
- [ ] `README.md`, `_bmad-output/implementation-artifacts/epic3-continuation-handoff.md` — scope/results; no ticket marking.

**Acceptance Criteria:**
- Given a mixed fixture, when analyzed, then complaints/patterns match labels and all references resolve.
- Given fixed input/version, when rerun or serialized/reloaded, then results match and input remains unchanged.
- Given legacy text-only input, when analyzed, then unavailable checks/limits remain visible without fabricated metadata.
- Given negation/missing metadata/boundaries, when analyzed, then conservative exclusions and eligibility hold.
- Given no provider/database, when analyzed, then it completes without networking.

## Implementation Notes

- Workflow initialization is already complete for this run: after the parent
  renderer hit restricted-network failure, the operator ran it locally and
  supplied `_bmad/render/bmad-build/vct-connect-ed5eaeebe2cd/a5568380f304d539f90b/workflow.md`.
  The parent followed steps 1/2, obtained plan approval, and is executing step 3's
  implementation handoff. A delegated implementer is continuing this active
  workflow, not initiating another bmad-build invocation; implement this plan
  directly without rerunning the renderer or resetting its approval/state.

## Plan Change Log

## Review Triage Log

## Design Notes

Proposed parameters: recurring ≥2 occurrences. Duplicate normalization is NFC
plus whitespace, preserving case/punctuation. Timing requires ≥10 dated reviews,
≥80% on one UTC day. Rating mismatch requires explicit individual 1–5 rating ≥4
and unambiguous negative phrase. Volume requires complete disjoint equal-duration
windows, current ≥10 and ≥3× positive baseline. Test boundaries; no significance
or calibration claim.

Bounds: 200 reviews/4,096 characters each, no silent truncation. Legacy sampling
is unknown. Explicit topics: material, size/color/specification, quantity,
delivery, image mismatch, packaging, batches and after-sales; unmatched stays unclassified.

## Verification

- Primary `.venv/Scripts/python.exe -m pytest backend/tests -q` from implementation checkout: new/offline regressions pass; DB/cloud suites run only when safely configured.
- `git diff --check`: clean patch; independent workflow review/triage before acceptance.
