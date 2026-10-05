---
title: 'Story 3.1 offline language-screen contract investigation'
type: 'chore'
created: '2026-10-06'
status: 'built'
route: 'oneshot'
route_source: 'auto'
review: 'quick'
review_source: 'auto'
lenses_ran: ['quick']
baseline_revision: '777c595304e64fdf1d85194ea657908bbc2a9a94'
context: []
---

<frozen-after-approval reason="human-owned intent">
## Intent
Investigate the language-screen contract offline after v7 live rejection at findings.text. Use independently authored source-related Vietnamese and contrasting foreign/mixed clauses to reproduce limitations and record an evidence-based next step. Preserve the unknown cause of the missing live output. No paid request, private rejected-output read/capture, deployment, production guard change, old record modification or Git push. Deliver reproducible probe inputs/results and reviewed findings; a proposed future correction or diagnostic does not constitute authorization to run it.
</frozen-after-approval>

## Implementation Notes
Oneshot: under100 implementation/data lines, one investigation deliverable. Existing screen_vietnamese and validate_report are reused without changes. Existing corpus covers33 positives/24 negatives but does not exhaust compact clauses or unknown English insertions. Add a clearly labeled synthetic diagnostic fixture and evaluator reporting direct screen and report validation outcomes separately. Labels assess language only, never truth, supplier safety or independent model calibration. Review independently, run the probe and existing focused suite, record boundary limitations and local commit.

Acceptance: Given labeled synthetic inputs, when the offline evaluator runs, then counts and case identifiers reproduce both false rejections and false acceptances without calling a provider. Given report validation, when a valid report envelope uses each probe finding, then its result is distinguished from direct screening. Given unavailable rejected live prose, when findings are summarized, then no case is asserted as the live root cause.

## Plan Change Log
## Review Triage Log
Medium / patch: evaluator initially counted any report failure as a language mismatch. Review reproduced a length-driven SCHEMA_INVALID. Separate report_other_rejections from language mismatch counts and add explicit long-text/schema and unsupported-score regression cases. This corrects the investigation tool; production guard stays unchanged.
## Verification
Run the evaluator against the new probe fixture and existing corpus; review synthetic language labels, JSON error handling and result counts. Run focused report tests to confirm production behavior is untouched. No Docker/PostgreSQL/cloud verification is needed for this offline investigation tool; existing released implementation verification remains historical evidence.

Verification:247 focused tests pass after two meaningful evaluator classification regressions; both probe datasets rerun with unchanged mismatch counts. New probe has no non-language rejections; existing empty-text case is correctly separated as SCHEMA_INVALID. Independent quick review finding fixed; existing language and quotation limitations deferred explicitly. Thorough adversarial, edge-case and verification lenses skipped for this small offline diagnostic change. No production change, deployment, paid call or push.
