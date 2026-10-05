---
title: 'Azure text report activation settings'
type: 'chore'
ticket: ''
created: '2026-10-05'
status: 'built'
route: 'oneshot'
route_source: 'auto'
review: 'quick'
review_source: 'auto'
lenses_ran: ['quick']
context: []
baseline_revision: '010eecc1905d579686f825796c4dbd352191515c'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Azure workers cannot generate the approved saved-evidence Vietnamese report because the deployment template lacks provider configuration and its Key Vault reference.

**Approach:** Add explicit opt-in worker configuration for the approved DeepSeek model, exact returned model, thinking setting, rates, budget and 120-second deadline. Keep generation disabled by default and credentials confined to processing workers. Preserve existing Azure resources and queue settings. Deploy in stages after migration and queue audit, respecting the approved $2 maximum and $0.10 call ceiling and the smaller funded account balance.

</frozen-after-approval>

## Implementation Notes

- One template, fewer than 100 changed code lines; direct oneshot implementation.
- Existing untracked rehearsal evidence is preserved under the user's continuing worktree authorization.
- Compiled Bicep and inspected ARM: only dispatcher/analysis workers receive provider secret references, only when explicitly enabled.
- Preserve an existing audited report opt-in and its non-secret configuration in subsequent deployment script activations.
- Shell syntax valid; deployment contract and preservation tests: 20 passed. Mock CLI corrected to return success after argument inspection.

## Plan Change Log

## Review Triage Log

- Medium, patch: routine deployment would reset paid reports to off. Confirmed script omitted new parameters; activation now reads and preserves existing opt-in/settings. First activation remains manual and gated.

## Verification

- Compile Bicep; inspect compiled worker environment and secret references, and confirm API/web/migration do not receive the provider key.
- Verify defaults remain disabled and backend validation remains authoritative for configured limits.
