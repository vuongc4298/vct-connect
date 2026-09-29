---
type: epic
title: "Interpret supplier evidence and compute transparent risk"
parent: initiative-vct-connect-year-one
covers: [R5, R6, R7, R8]
assignee: ""
risk: high
---

# Interpret supplier evidence and compute transparent risk

## Description

Interpret normalized supplier evidence in Vietnamese, detect review and identity signals, and calculate a deterministic versioned assessment that keeps Risk, Confidence, and Data Coverage separate.

## Outcome

The same snapshot and scoring version reproduce an evidence-linked assessment, including uncertainty when the evidence is weak or missing.

## Requirements

- R5: Use backend-only LLMProvider/YEScale for contextual interpretation, structured output, controlled model/version pins, and cost/provenance metadata. (Specification section 11)
- R6: Combine deterministic review signals, off-the-shelf embeddings, and structured LLM interpretation for complaints, suspicious patterns, reliability, and accessible media; manipulation reduces confidence in review-derived Quality, Delivery, and After-sales evidence; avoid definitive fake-review claims. (section 12)
- R7: Aggregate factory/trader evidence by direction, strength, reliability, and provenance into likelihood, confidence, and uncertainty; trader status alone is not a risk penalty. (section 13)
- R8: Implement deterministic risk v0.1.0 with seven specified weights, confidence factors, 0-34/35-64/65-100 labels, insufficient information below 45% coverage or 40% confidence, strict critical floors, and stored scoring version. (section 14)

## Done when

1. A versioned SupplierData fixture produces Chinese-to-Vietnamese interpretation, review findings, and factory/trader estimates with cited evidence.
2. The risk engine reproduces the same dimensions and overall result for a fixed input/version, including insufficient-information and critical-signal boundaries.
3. Model runs retain model/prompt/schema/pipeline versions, tokens, latency, cost, and output needed for later human evaluation.
4. An integrated worker processes live normalized evidence and persists findings and scores without exposing YEScale credentials.

## Boundaries

Owns interpretation, review/factory analysis, and risk scoring. Extraction owns source snapshots; reporting owns presentation; human evaluation owns the labeled benchmark and final model selection evidence.

## References

- parent - _bmad-output/initiative-vct-connect-year-one/initiative-vct-connect-year-one.md, Requirements R5-R8.
- specification - VCT_Connect_MVP_Technical_Specification_EN.pdf, sections 11-14 and 22.2.

## Notes

- Open question: exact model/version choice remains Decision 7B until human-labeled benchmark results; use pinned candidates during evaluation.
- Open question: evidence reliability calibration and critical-override eligibility need explicit review before pilot; no ambiguous single review can cause a critical floor.
- Assumption: the source's numeric v0.1 weights and thresholds are initial heuristics, not validated predictions.
- Decision: 2026-09-27 - tracer is one pinned YEScale interpretation on SupplierData, followed by review/factory/risk fixtures and a text-only worker report; media enriches the same path later.
- Assumption: independent high-risk checks are a gateway cost/secret audit (3.1), labeled review and identity spot checks (3.3/3.4), owner-approved scoring fixtures (3.5), private-media provenance review (3.6/3.9), and worker replay/cost monitoring (3.7).
