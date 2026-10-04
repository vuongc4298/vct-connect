---
id: 9
type: bug
title: "Classify access walls using effective screen visibility"
parent: epic-extraction
covers: [R4]
after: [8]
refined: true
hitl: false
risk: medium
severity: P2
---

# Classify access walls using effective screen visibility

## Description

CSS visibility misclassifies access walls. The result must match screen-visible source evidence and the documented resource budget.

## Reproduction

The five CSS wrappers in the retrospective yield four missing AUTH_REQUIRED statuses and one false AUTH_REQUIRED status. Follow the finite reproduction recorded in the retrospective Behavior verification section.

## Cause Hypothesis

Static hiding rules are applied before resolving the effective screen declaration and inherited visibility.

## Acceptance Criteria

1. Given supported HTML with cascaded styles, when extraction classifies it, then visible login/CAPTCHA text stays visible and invisible text supplies neither a barrier nor selected evidence.
2. Given existing valid platform fixtures, when extraction and replay checks run, then supported evidence, source identities and provenance remain correct.
3. Given the reported reproduction, when the completed regression runs, then it fails against the recorded baseline and passes against the correction; if the report does not reproduce, record proof that no change is needed.

## References

- parent - _bmad-output/initiative-vct-connect-year-one/epic-extraction/epic-extraction.md, R4.
- retrospective - _bmad-output/initiative-vct-connect-year-one/epic-extraction/epic-extraction-retrospective.md, A1 and Behavior verification.

## Notes

- Decision: 2026-10-03 - user approved applying the proposal and proceeding with implementation.
- Risk: medium because shared extraction behavior can regress across platforms.
