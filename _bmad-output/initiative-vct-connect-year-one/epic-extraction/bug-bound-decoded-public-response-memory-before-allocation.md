---
id: 10
type: bug
title: "Bound decoded public response memory before allocation"
parent: epic-extraction
covers: [R4]
after: [8]
refined: true
hitl: false
risk: medium
severity: P2
---

# Bound decoded public response memory before allocation

## Description

Public response decompression exceeds the byte budget. The result must match screen-visible source evidence and the documented resource budget.

## Reproduction

A 2,942-byte gzip body yields a 3,000,000-byte first decoded chunk before the 2 MB application guard. Follow the finite reproduction recorded in the retrospective Behavior verification section.

## Cause Hypothesis

Automatic content decoding produces its output before the application can enforce capacity.

## Acceptance Criteria

1. Given compressed public HTML, when extraction reads it, then decoding remains within the configured allocation budget on every path. Exceeding capacity terminates extraction with status PARSE_FAILED, reason PAGE_TOO_LARGE and no snapshot. Verification observes decoder output allocations and cumulative chunks; rejection alone cannot pass.
2. Given existing valid platform fixtures, when extraction and replay checks run, then supported evidence, source identities and provenance remain correct.
3. Given the reported reproduction, when the completed regression runs, then it fails against the recorded baseline and passes against the correction; if the report does not reproduce, record proof that no change is needed.

## References

- parent - _bmad-output/initiative-vct-connect-year-one/epic-extraction/epic-extraction.md, R4.
- retrospective - _bmad-output/initiative-vct-connect-year-one/epic-extraction/epic-extraction-retrospective.md, A2 and Behavior verification.

## Notes

- Decision: 2026-10-03 - user approved applying the proposal and proceeding with implementation.
- Risk: medium because shared extraction behavior can regress across platforms.
