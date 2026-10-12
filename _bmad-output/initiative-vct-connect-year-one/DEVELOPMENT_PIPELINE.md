# VCT Connect MVP development pipeline

Source: `VCT_Connect_MVP_Technical_Specification_EN.pdf`, especially sections 24-28. The initiative and epic tickets hold the authoritative work breakdown.

## Current implementation audit — 2026-10-11 (Asia/Bangkok)

Earlier demo planning records are historical. The current checkout includes later completed build records and implementation; `built` describes the implementation/review state, not completed live buyer or pilot acceptance. See [the functionality audit](../implementation-artifacts/progress-functionality-audit.md) and [end-user test guide](../../END_USER_TEST.md) for verification evidence and repeatable acceptance steps.

| Epic | Current checkout | Remaining acceptance |
| --- | --- | --- |
| 1. Platform foundation | Clerk/role boundary, PostgreSQL schema, local queue/Service Bus outbox/retries, CI/deployment definitions implemented. Local runtime and database checks are part of this audit. | Fresh signed-in deployed assessment/report journey; the historical guest tracer smoke verifies queue plumbing only. |
| 2. Extraction | 1688, Taobao and Alibaba public adapters; 1688/Taobao saved HTML and extension evidence; explicit blocked/partial outcomes. | Accessible live success-path acceptance across platforms; browser fallback remains disabled in Azure pending compatible runtime. Alibaba import/capture is unsupported. |
| 3. Analysis intelligence | Provider-neutral YEScale interpretation, deterministic/semantic review analysis, identity scoring, Risk/Confidence/Coverage, worker composition and optional multimodal contracts implemented. | Local worker needs YEScale credentials for reports. Deterministic test providers do not verify live model output. Standard worker does not acquire live private media; calibration/model selection remains pending. |
| 4. Reporting | Persisted authorized Vietnamese full reports, guest projection, source evidence, freshness and insufficiency handling implemented. Audit remedies source-value rendering and honest tracer completion. | Fresh live provider-backed customer/guest acceptance. A terminal extraction result or synthetic tracer is not a report. |
| 5. Product workflows | Database-backed history, Watchlist, account/trial state and expiry, signed-in extension capture/progress implemented. Audit remedies saved-HTML report handoff, effective trial quotas and reopening state. | Real Chrome session sync/capture/reopen and signed-in buyer walkthrough. Active trial allocation is an operator/product decision; new users are not automatically granted a trial. |
| 6. Human evaluation | Stories 6.1 and 6.2 implement reviewer-only blind text labeling and complete annotation fields. | Private media review, double review/adjudication, supplier-level labels, metrics and candidate benchmark are still pending. |
| 7. Pilot validation | Ticketed/planned; no completed pilot plans in this checkout. | Recruitment, live privacy/budget gates, representative load/latency/cost measurements, return usage and quality/upgrade-intent evidence. |

There is also an older untracked `in-progress` statistical-review plan alongside the later built review-analysis plans. This audit preserves it as existing work; its status is not evidence that the implemented review engine is absent or that the old draft has been independently accepted.

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
