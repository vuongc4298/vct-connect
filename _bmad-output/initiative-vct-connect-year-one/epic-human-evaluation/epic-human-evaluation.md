---
type: epic
title: "Evaluate model decisions with blind human review"
parent: initiative-vct-connect-year-one
covers: [R13]
assignee: ""
risk: high
---

# Evaluate model decisions with blind human review

## Description

Create an internal reviewer workflow for independent labels on sampled text, image, and video cases, reveal the stored model verdict only after submission, and aggregate benchmark/error metrics.

## Outcome

The team can compare candidate model configurations and distinguish model mistakes from ambiguous cases using traceable human judgments.

## Requirements

- R13: Enforce reviewer roles; sample random/targeted cases; capture blind labels and confidence, media annotations, second reviews and adjudication; retain run provenance; compare quality by model, prompt, platform, complaint, severity, and media type. (Specification sections 16-17, 20, 22)

## Done when

1. Authorized reviewers can label a case without seeing its model verdict, submit it, then see and compare the stored verdict.
2. Text, image, and video evidence supports the specified annotation fields, with private time-limited media access.
3. A subset can receive independent second labels and adjudication, retaining both original judgments.
4. The deployed console reports agreement, high-confidence errors, and model/prompt/platform/media breakdowns from versioned runs.

## Boundaries

Owns internal evaluation UI, annotation data, sampling, adjudication, and metrics. Analysis owns model inference and raw model-run provenance.

## References

- parent - _bmad-output/initiative-vct-connect-year-one/initiative-vct-connect-year-one.md, Requirement R13.
- specification - VCT_Connect_MVP_Technical_Specification_EN.pdf, sections 16-17, 19-22.

## Notes

- Open question: evaluation sample sizes, double-review fraction, and model acceptance thresholds need to be chosen before the pilot benchmark.
- Assumption: the console uses existing Next.js internal routes and FastAPI role checks.
- Decision: 2026-09-27 - tracer is one API-blinded review label and reveal; full media, independent second labels, supplier cases, metrics, and candidate comparison follow.
- Assumption: independent high-risk checks are a second-person blind API/role audit (6.1), private-media link expiry review (6.3), and review-leakage checks during second labels, supplier labels, and model comparison (6.4/6.8/6.6).
