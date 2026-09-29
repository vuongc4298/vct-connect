# VCT Connect MVP development pipeline

Source: `VCT_Connect_MVP_Technical_Specification_EN.pdf`, especially sections 24-28. The initiative and epic tickets hold the authoritative work breakdown.

| Stage | Epic | Demonstrable gate | Main handoff |
| --- | --- | --- | --- |
| 1. Foundation | 1 - Platform foundation | A submitted analysis reaches a durable queue, worker, persisted state, and authenticated polling path in Azure dev. | Versioned API/data contract, auth/role rules, Service Bus behavior. |
| 2. Extraction | 2 - Extraction | A 1688 URL yields a normalized, traceable snapshot or an explicit failure; Taobao, Alibaba, and fallback paths follow. | SupplierData, extraction status, completeness, provenance, fixtures. |
| 3. Analysis | 3 - Analysis intelligence | The same snapshot yields Vietnamese interpretation, review/factory findings, and reproducible Risk/Confidence/Coverage. | Versioned findings, evidence IDs, model-run metadata, score contract. |
| 4. Reporting | 4 - Reporting | A buyer sees a usable Vietnamese report, with unknowns and evidence visible. | Report payload and guest/full authorization contract. |
| 5. Repeat-use workflow | 5 - Product workflows | A signed-in user can save and revisit suppliers; the extension enriches a page and opens the report. | Trial and usage events, extension payload contract. |
| 6. Quality feedback | 6 - Human evaluation | Reviewers label blind cases and compare candidate models by quality, latency, and cost. | Labeled benchmark and error categories. |
| 7. Pilot | 7 - Pilot validation | The Azure pilot records target usage, speed, extraction quality, model quality, cost, and upgrade intent. | Evidence for model choice, scaling, and post-MVP billing decision. |

The earliest cross-system demo is one 1688 URL through the web API, queue, worker, extractor, deterministic assessment, and report. Story dependencies in each `tickets.toml` permit parallel work after the relevant contracts exist. Each story's `verify` is its completion check; production gates also require authorization, privacy, and operational checks from the parent epic.

## Release gates

1. **Development baseline:** local and Azure dev environments, migrations, Clerk verification, Service Bus processing, secrets, and CI are working.
2. **Vertical report:** one supported URL produces an evidence-backed report or an explicit insufficient-information/access result; replay does not duplicate effects.
3. **MVP breadth:** all three platforms, three analysis modes, history, Watchlist, trial, and evaluation console meet their epic Done when checks.
4. **Pilot readiness:** media retention/deletion, source terms, role/guest limits, monitoring, dead-letter handling, and cost caps are settled and verified.
5. **Validation review:** report the source targets and observed quality/cost/latency by platform and mode; decide the next model and paid-launch work from the evidence.

## Decisions to resolve at the gates

- Foundation: field-level SupplierData optionality, guest/account quotas, trial dates, API/report sharing authorization.
- Extraction: permitted media capture and source-platform terms; coverage calculation and fallback budget.
- Analysis: evidence reliability, critical override criteria, and candidate model/version pins.
- Pilot readiness: media retention/deletion duration, Azure SKUs/scaling, and evaluation sampling thresholds.
- Paid launch, outside this MVP: reward eligibility threshold and payment provider; no user is charged automatically.

The PDF's four-week plan is an aspirational sequence. The acceptance gate is observed behavior, especially extraction reliability and the approximately 20-30 second report target under normal supported conditions.

## First-month planning target

| Week | Target emphasis | Evidence to carry forward |
| --- | --- | --- |
| 1 | Foundation and first 1688 HTTP snapshot | Queued analysis tracer, schema, Clerk/Service Bus baseline, explicit extraction failures. |
| 2 | Extraction breadth and assessment | Playwright fallback, Taobao/Alibaba basics, YEScale adapter, review/factory evidence, risk v0.1.0. |
| 3 | Buyer experience and repeat use | Full/guest reports, history, Watchlist, free trial, authenticated extension flow. |
| 4 | Human evaluation and pilot | Blind console, Azure pilot, latency/cost/error review, user feedback and calibration. |

These weeks express the PDF's sequencing target; stories move through their dependency gates even if source-platform extraction takes longer.
