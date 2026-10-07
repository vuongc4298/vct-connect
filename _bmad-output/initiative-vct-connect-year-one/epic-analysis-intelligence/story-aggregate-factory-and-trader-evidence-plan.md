---
title: 'Aggregate factory and trader evidence'
type: 'story'
ticket: '4'
created: '2026-10-07'
status: 'built'
baseline_revision: '71896522b2b7e29bb569e668dbdaced987571e11'
route: 'full'
review: 'thorough'
---

<frozen-after-approval reason="user approved Epic 3 Story 3.4 on 2026-10-07">

## Intent

**Problem:** Supplier snapshots contain identity-related evidence, but VCT Connect has no versioned, reproducible factory-versus-trader assessment.

**Approach:** Add a pure deterministic aggregator over sourced identity signals. Each signal carries direction, strength, reliability, source kind, source field, statement, and evidence ID. The aggregator converts weighted evidence into factory/trader likelihoods, confidence, supporting evidence, and explicit uncertainty.

## Boundaries & Constraints

**Always:** Keep identity assessment separate from supplier risk. Preserve provenance and uncertainty. Cap self-claim-only confidence. Reduce confidence when strong factory and trader evidence contradict each other. Map SupplierData conservatively and only from actually-present structured fields.

**Never:** Treat trader status as a supplier-risk penalty. Do not infer factory status from certifications alone. Do not promote seller self-claims into high-confidence identity. Do not add worker persistence or scoring effects yet; Story 3.7 owns integration and Story 3.5 owns risk scoring.

</frozen-after-approval>

## Contract

- schema: factory-trader-assessment.v1
- evidence direction: FACTORY, TRADER, NEUTRAL
- source kind: PLATFORM_PROFILE, SELF_CLAIM, DOCUMENT, DERIVED
- assessment: classification, factory likelihood, trader likelihood, confidence, supporting evidence, uncertainty reasons
- supplier_risk_penalty is fixed at 0 in this contract
- classifications: FACTORY_LIKELY, TRADER_LIKELY, MIXED, UNCERTAIN

## SupplierData adapter

Current adapters can expose fields such as company_information.business_type, factory_area_sqm, production_line_count, qc_staff_count, rd_team_count, and employee_count. Story 3.4 uses only those fields when present. Business-type text is treated as a self-claim. Structured factory-capability counts are treated as platform-profile evidence. Certifications are retained as neutral evidence because certification presence alone does not establish factory/trader identity.

## Verification

- strong independent factory evidence becomes FACTORY_LIKELY
- strong independent trader evidence becomes TRADER_LIKELY while supplier_risk_penalty remains 0
- self-claim-only fixtures remain UNCERTAIN
- contradictory strong evidence remains UNCERTAIN
- certification-only fixtures remain UNCERTAIN
- SupplierData adapter emits evidence only from present supported fields
