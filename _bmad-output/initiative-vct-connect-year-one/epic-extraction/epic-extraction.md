---
type: epic
title: "Extract and normalize evidence from supported platforms"
parent: initiative-vct-connect-year-one
covers: [R4]
assignee: ""
risk: high
---

# Extract and normalize evidence from supported platforms

## Description

Convert supported supplier/product URLs and permitted extension page data into versioned SupplierData snapshots, with explicit incompleteness and access failures.

## Outcome

A buyer's link supplies reliable, traceable evidence for analysis without bypassing source access controls or treating missing fields as reassuring.

## Requirements

- R4: Support 1688, Taobao, and Alibaba URL validation/normalization, per-platform HTTP adapters, justified Playwright fallback, extension payload merge/deduplication, status enumeration, and raw/normalized snapshots with method, mode, version, missing fields, completeness, and timestamp. (Specification sections 4, 9-10, 22.1)

## Done when

1. Representative URLs from all three platforms yield SupplierData snapshots or a correct explicit status in the deployed analysis path.
2. Public HTTP extraction is tried first; browser fallback is bounded and used only when justified; auth/CAPTCHA/block conditions direct the user to the extension.
3. Raw and normalized snapshots retain provenance, missing fields, coverage, and extractor version for re-normalization and audit.
4. Extension data merges without duplicate evidence or transmission of platform passwords, cookies, or session tokens.

## Boundaries

Owns platform adapters, extraction, normalization, and snapshot provenance. Analysis meaning and risk scoring belong to epic-analysis-intelligence.

## References

- parent - _bmad-output/initiative-vct-connect-year-one/initiative-vct-connect-year-one.md, Requirement R4.
- specification - VCT_Connect_MVP_Technical_Specification_EN.pdf, sections 4, 9-10, 21-22.

## Notes

- Decision: 2026-10-04 - A6 records surviving static-boundary concerns in planned 2.15 and the prior official-API assessment in planned 2.16; these are inventory ownership records, not implementation or acceptance decisions. The completed historical 2.8 sweep remains intact and 2.14 is the current remediation set's completion audit, so no second sweep is inserted into this approved action set. Any future implementation/refactor scope is refined before execution; API assessment never substitutes for the retained deployed-browser criterion.

- Decision: 2026-10-04 - the user retained deployed browser enrichment as required and left full epic acceptance pending. No A3 scope waiver is accepted; compatible-host exact-image deployed gain/preservation remains an activation and acceptance gate.
- Decision: 2026-10-03 - the user authorized applying retrospective A1-A6 and proceeding with their action items. Track them as 2.9, 2.10, 2.11, 2.12, 2.13 and 2.14 respectively (A4 maps to 2.12 before A3 runtime qualification at 2.11). The completed 2.8 refactor remains historical; the added entries are remediation and acceptance follow-ups, and 2.14 supplies their completion gate rather than another refactor sweep.
- Decision: 2026-10-03 - implement confirmed defects and qualification evidence before any browser activation. Existing source-session and deployment prerequisites remain explicit; this instruction does not claim that an unavailable manual check has passed.

- Assumption: 1688 is the first live platform, following section 25.
- Open question: agree permitted media capture and platform terms before production media collection.
- Open question: field optionality and completeness calculation need representative samples; do not treat an absent field as a zero-risk signal.
- Decision: 2026-09-27 - the first live tracer is 1688 HTTP extraction; Taobao and Alibaba follow the shared contract.
- Decision: 2026-09-27 - freeze SupplierData and status contracts with the 1688 tracer; platform adapters may then proceed separately before fallback, extension merge, and layout verification.
- Assumption: independent high-risk checks are a sampled 1688 snapshot audit (2.1), separate Taobao/Alibaba page audits (2.3/2.4), browser-cost and block-rate monitoring (2.5), and extension payload network inspection (2.6).
