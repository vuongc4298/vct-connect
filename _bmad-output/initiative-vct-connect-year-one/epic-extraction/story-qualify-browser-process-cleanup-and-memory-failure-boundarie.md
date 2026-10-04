---
id: 12
type: story
title: "Qualify browser process cleanup and memory failure boundaries"
parent: epic-extraction
covers: [R4]
after: [9, 10]
risk: high
---

# Qualify browser process cleanup and memory failure boundaries

## Description

Exercise abrupt runner death, slow cleanup and allocation failure under the existing sandbox limits and correct any demonstrated loss of cleanup or preserved HTTP evidence.

## Acceptance Criteria

Verify: Actual container fault probes report descendant cleanup, bounded termination, worker survival and preserved HTTP evidence with no skipped covering case.

## References

- parent — _bmad-output/initiative-vct-connect-year-one/epic-extraction/epic-extraction.md
- preparation — _bmad-output/initiative-vct-connect-year-one/epic-extraction/browser-runtime-decision.md, Concrete qualification path. This prepares controls; it does not claim cloud qualification.
- retrospective — _bmad-output/initiative-vct-connect-year-one/epic-extraction/epic-extraction-retrospective.md, A4 and F4–F6.

## Notes

- Open question: The three runtime failure hypotheses require measured qualification before activation.
