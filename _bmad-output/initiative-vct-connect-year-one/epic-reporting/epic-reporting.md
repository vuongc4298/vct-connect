---
type: epic
title: "Deliver evidence-backed Vietnamese reports"
parent: initiative-vct-connect-year-one
covers: [R9]
assignee: ""
risk: high
---

# Deliver evidence-backed Vietnamese reports

## Description

Turn persisted assessment results into a clear Vietnamese decision-support report and a limited guest preview, with provenance and uncertainty visible.

## Outcome

Buyers can decide what to verify before ordering and understand when the available evidence is insufficient.

## Requirements

- R9: Present supplier/platform/date, Risk/Confidence/Coverage, factory/trader likelihood, key risks, positive signals, review and supplier summaries, recommended actions, evidence/sources, missing information, and limitations; authorize full and guest access. (Specification sections 4, 15, 20)

## Done when

1. A completed analysis displays the specified report fields in Vietnamese on the deployed web app, with each material finding traceable to evidence.
2. Low-coverage or blocked paths visibly explain limits and offer an appropriate next step without a false low-risk verdict.
3. Guest preview and authenticated full-report routes enforce their access rules in FastAPI.
4. Report pages work for supported links under the product's observed latency target, with accessible loading, failure, and completion states.

## Boundaries

Owns report payload, authorization rules, and web presentation. It consumes scores and evidence from analysis; account history and extension UI belong to epic-product-workflows.

## References

- parent - _bmad-output/initiative-vct-connect-year-one/initiative-vct-connect-year-one.md, Requirement R9.
- specification - VCT_Connect_MVP_Technical_Specification_EN.pdf, sections 4, 6, 14-15, 20 and 24.

## Notes

- Open question: whether any report is shareable publicly and its authorization/expiry rule must be settled before enabling sharing.
- Assumption: visual layout is designed during the report UI story because no UX design artifact is supplied.
- Decision: 2026-09-27 - tracer is one persisted authorized report after scoring; the full web view owns shared report components before the guest projection uses them.
- Assumption: independent high-risk checks are queue/report persistence replay and an access audit (4.1), anonymous-versus-full access review (4.3), and sampled evidence/source claim review (4.5).
