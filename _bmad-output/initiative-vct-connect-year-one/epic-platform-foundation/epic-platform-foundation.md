---
type: epic
title: "Run the secure platform and analysis job baseline"
parent: initiative-vct-connect-year-one
covers: [R1, R2, R3, R12]
assignee: ""
risk: high
---

# Run the secure platform and analysis job baseline

## Description

Stand up the web, extension, API, database, and Azure worker baseline with one queued analysis path, verified identity, protected business state, and controlled secrets. This epic owns the shared contracts that later epics consume.

## Outcome

Developers can submit, process, persist, and poll an analysis safely in Azure dev, while the same contracts work locally.

## Requirements

- R1: Use the locked frontend/backend/database/Azure stack, modular monolith, shared TypeScript types and API client, deployable development environment, and CI. (Specification sections 3, 5-8, appendix B)
- R2: Verify Clerk JWTs in FastAPI; map authenticated subjects to users; keep roles, plan, entitlements, and usage in PostgreSQL; leave guests anonymous. (sections 17, 19-20)
- R3: Create a QUEUED analysis and publish `analysis_id` as MessageId; process with Peek-Lock, idempotency, persist-before-complete, retries/DLQ, and pollable state. (section 7, appendix A)
- R12: Keep secrets server-side in Key Vault and enforce API roles and guest admission controls; record audit provenance. Other R12 media/retention checks close in pilot validation. (sections 17, 21)

## Done when

1. The web/API/worker/database baseline deploys to Azure dev and passes its CI checks.
2. A sample analysis is queued, processed once despite replay, persisted, and visible through the status endpoint; failures reach a visible retry/final state.
3. Guest, customer, reviewer, and admin requests receive the intended API access without leaking server secrets.
4. Shared API and data contracts are usable by the extraction, analysis, reporting, and extension epics.

## Boundaries

Owns the shared platform, schema, identity, and job mechanics. Later epics implement real extraction, assessment, reports, user workflows, and pilot operations.

## References

- parent - _bmad-output/initiative-vct-connect-year-one/initiative-vct-connect-year-one.md, Requirements R1-R3 and R12.
- specification - VCT_Connect_MVP_Technical_Specification_EN.pdf, sections 3, 5-8, 17, 19-21 and appendix A-B.

## Notes

- Assumption: the opening tracer runs a deterministic fixture through the queue until the extraction epic supplies live SupplierData.
- Open question: guest and registered quotas and trial timing need product defaults before release; schema supports configuration without inventing them.
- Decision: 2026-09-27 - source-locked stack and Service Bus behavior are adopted as written in the specification.
- Decision: 2026-09-27 - tracer is one locally running web-to-worker fixture through Azure dev Service Bus; schema precedes Clerk mapping, then queue hardening and full Azure deployment.
- Assumption: independent high-risk checks are operator replay of the deployed tracer (1.1/1.5), a second-person API role matrix (1.2), migration rehearsal on a fresh and populated database (1.3), and injected queue failure/DLQ monitoring (1.4).
