---
title: 'Story 3.1 compact report within existing output cap'
type: 'bugfix'
created: '2026-10-05'
status: 'built'
route: 'oneshot'
route_source: 'auto'
review: 'quick'
review_source: 'auto'
lenses_ran: ['quick']
baseline_revision: 'b0babd5fb749dbec76567932b117551c00334d01'
context: []
---
<frozen-after-approval reason="human-owned intent">
## Intent
The v4 cloud request exhausted its 2400 output tokens and returned OUTPUT_INCOMPLETE. Guide the model to produce a compact complete Vietnamese report: at most two summary sentences, six findings, three limitations, three actions and one confidence-basis sentence. Keep source citations, seller attribution, unknown freshness/missing evidence and uncalibrated interpretation confidence. Keep model, 120-second timeout, 2400-token cap, schema, validation, reservations and saved reports unchanged. User approved implementation, review, local commit, dev deployment and exactly one fresh owned acceptance request under the prior $0.01 per-call ceiling. No retry, replay, model switch or Git push.
</frozen-after-approval>
## Implementation Notes
Prompt-only change under 100 lines; oneshot route. Bump prompt provenance to vi-text.v5. Add per-field character targets and avoid repeated source titles/boilerplate so the requested structure can fit the existing cap. These are prompt guidance, not a token guarantee or new strict schema. Preserve truncation rejection and existing safety/citation/language guards. Previous language corrections remain in place.
## Plan Change Log
## Review Triage Log
## Verification
Run the existing focused report regressions (including finish_reason=length rejection/no retries, immutable source citations, strict confidence and language guards). Independently review the diff. Build and verify the non-root image without networking. Release by digest, verify healthy revisions and retained ledgers, fence exactly one UI submission. Live success requires READY, substantive fixture-grounded Vietnamese interpretation and owner-scoped identical reopen. Stop honestly if the single request fails.

Independent quick review found no concrete bugs or unmet implementation intent. All 147 focused tests passed locally and in the non-root built image with networking disabled. Live completion is unverified until the separately approved single acceptance request.

Dev release and single paid test completed. Response ended at 991 output tokens, but NON_VIETNAMESE_PROSE/findings.text blocked acceptance. No rejected prose retained; no retry. Full outcome: story31-compact-report-result.md. Built status represents implementation/review only, not Story 3.1 live acceptance.
