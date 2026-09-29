---
type: epic
title: "Operate and validate the MVP pilot"
parent: initiative-vct-connect-year-one
covers: [R12, R14, R15]
assignee: ""
risk: high
---

# Operate and validate the MVP pilot

## Description

Finish production safeguards and telemetry, run the Azure pilot, measure user/model/technical outcomes, and use the evidence to decide post-MVP investments.

## Outcome

The team has a safe, observable pilot and a documented answer to whether the product delivers useful supplier-risk intelligence at an acceptable cost and speed.

## Requirements

- R12: Finalize production media retention/deletion, private review-media access, platform-term checks, guest limits, cost caps, and provenance audit; platform secrets/roles are implemented by epic-platform-foundation. (Specification section 21)
- R14: Record extraction quality, queue/retry/DLQ behavior, end-to-end latency, model tokens/cost, cost per completed report, and failure patterns; deploy and operate Azure pilot services. (sections 8, 23)
- R15: Evaluate supported-link usefulness at roughly 20-30 seconds or explicit insufficiency, at least 100 registered users, 500-1,000 URLs, at least 30% returning users, model quality, and upgrade intent; paid conversion follows later billing. (sections 24-28)

## Done when

1. Production safeguards, retention/deletion, private media access, rate/budget controls, monitoring, and DLQ recovery are verified in the pilot environment.
2. Pilot dashboards separate platform/mode extraction, latency, quality, and cost, including failures and low-coverage cases.
3. The team records the specification's user and URL targets, returning-user rate, model agreement, high-confidence errors, upgrade intent, and buyer feedback or explicit gaps.
4. A review document decides the next model configuration and post-MVP priorities from observed evidence; it does not activate billing.

## Boundaries

Owns operational readiness, pilot execution, and validation reporting. It does not implement the deferred payment gateway, custom models, monitoring alerts, or new platforms.

## References

- parent - _bmad-output/initiative-vct-connect-year-one/initiative-vct-connect-year-one.md, Requirements R12 and R14-R15.
- specification - VCT_Connect_MVP_Technical_Specification_EN.pdf, sections 8, 21-28.

## Notes

- Open question: media retention period and source-platform terms must be settled before production media storage.
- Open question: final Azure SKUs and scaling limits follow load/cost observations.
- Assumption: pilot participant recruitment and interviews require a human operator; the relevant stories are marked `hitl`.
- Decision: 2026-09-27 - tracer is one deployed report trace from URL through cost; recruitment preparation can proceed before load gates, while live enrollment follows them.
- Assumption: independent high-risk checks are an operator trace reconciliation (7.1), approved retention/deletion drill (7.2), external load/DLQ observation (7.3), cohort-count audit (7.4), and a second-person evidence review of the pilot decision (7.5).
