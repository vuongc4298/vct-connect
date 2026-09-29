---
type: initiative
title: "Validate VCT Connect supplier-risk intelligence MVP"
parent: none
covers: [R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, R11, R12, R13, R14, R15]
after: []
assignee: ""
risk: high
---

# Validate VCT Connect supplier-risk intelligence MVP

## Description

Deliver a pilot of VCT Connect for Vietnamese sellers sourcing from 1688, Taobao, and Alibaba. A supported supplier or product URL produces an evidence-backed Vietnamese risk report, or an explicit explanation of insufficient or inaccessible evidence. The technical specification is the source for product behavior and locked engineering choices.

## Outcome

Pilot users can assess pre-order supplier risk with transparent evidence, and the team can measure repeat usage, report quality, latency, cost, and upgrade intent before activating paid billing.

## Requirements

- R1: Run the Next.js web app, React Chrome extension, FastAPI backend, PostgreSQL/JSONB, and Azure services as a modular monolith with a worker. (Specification pp. 3-5, 13-14)
- R2: Use Clerk identity, FastAPI JWT verification, PostgreSQL business roles and entitlements, and anonymous guest analysis. (pp. 3, 10-11)
- R3: Queue analyses through Service Bus Standard; process idempotently with persisted results, bounded retries, and dead-letter handling. (pp. 5, 13)
- R4: Extract and normalize 1688, Taobao, and Alibaba links with HTTP, justified Playwright fallback, extension data, explicit statuses, and raw/normalized snapshots. (pp. 5-6, 11-12)
- R5: Produce contextual Chinese-to-Vietnamese interpretation through a backend LLMProvider using YEScale, with model/version provenance. (pp. 6-7, 9-10)
- R6: Analyze complaints, suspicious review patterns, reliability, and accessible text/image/video evidence without claiming individual reviews are fake. (pp. 7, 9-10)
- R7: Estimate factory versus trader likelihood from sourced signals, confidence, and uncertainty; trader status alone is not a risk penalty. (pp. 7-8)
- R8: Calculate versioned deterministic Risk, Confidence, and Data Coverage with the specified dimensions, thresholds, insufficient-information state, and strict critical overrides. (pp. 8-9)
- R9: Show a Vietnamese evidence-backed report with limitations, positive signals, recommended pre-order actions, and suitable guest/full access. (pp. 9, 11)
- R10: Provide authenticated history, Watchlist, profile, and the free MVP trial entitlement with expiry to Free and no automatic charge. (pp. 2-4, 10-11)
- R11: Provide a signed-in Chrome extension that extracts permitted rendered data, shows progress/verdict, and opens the full web report without sending platform credentials or session material. (pp. 3-4, 11)
- R12: Protect secrets, authorization, private media, guest budget, source data, and audit provenance; define production media retention and deletion. (pp. 4, 10-11)
- R13: Provide an authorized blind human evaluation workflow, model-run provenance, sampling, adjudication, and comparison metrics. (pp. 9-10, 12)
- R14: Instrument extraction, queue, model, latency, and cost behavior; deploy an observable Azure pilot. (pp. 5, 11-12)
- R15: Validate the pilot against approximately 20-30 second supported-link reports or transparent insufficiency, at least 100 registered users, 500-1,000 URLs, at least 30% returning users, model quality, and upgrade intent. (pp. 12-13)

## Done when

1. A supported link from each initial platform completes a guest, account, or extension path as applicable, yielding an evidence-backed report or a clear insufficiency/access explanation.
2. The pilot deployment enforces identity, roles, entitlements, source-data privacy, and budget limits, and exposes operational and model-quality measures.
3. Internal reviewers can label blind cases and compare candidate model runs using retained provenance.
4. Pilot evidence reports the specification's user, URL, return, latency, quality, cost, and upgrade-intent measures; gaps and failures are visible rather than silently counted as success.
5. Trial expiry returns users to Free without charging them, and real-money billing remains off.

## Boundaries

The MVP covers the web app, Chrome extension, FastAPI/worker, and Azure pilot for 1688, Taobao, and Alibaba. It excludes real-money payments, custom-trained models, logistics API integration, a buyer-intelligence database, category-specific risk models, enterprise workflows, continuous monitoring, Tmall/Pinduoduo, and large-scale paid human review. Tracer path: submit one 1688 URL, queue and extract it, assess evidence, then view a Vietnamese report with coverage and limitations.

- Touch point: Clerk - identity and JWT issuance; owner: epic-platform-foundation.
- Touch point: YEScale - model gateway and cost metadata; owner: epic-analysis-intelligence.
- Touch point: source-platform pages - permitted public or browser-rendered data; owner: epic-extraction.
- Touch point: Azure Key Vault, Blob Storage, Service Bus, PostgreSQL, and Container Apps - pilot infrastructure; owner: epic-platform-foundation, with operational validation in epic-pilot-validation.

## References

- specification - VCT_Connect_MVP_Technical_Specification_EN.pdf, sections 1-28 and appendices A-B.

## Notes

- Assumption: the development pipeline follows the specification's recommended sequence, while independent stories may run concurrently when their contracts are ready.
- Assumption: the four-week sprint is a planning target, not a release commitment; extraction difficulty may extend it (specification p. 13).
- Open question: exact LLM/model configuration is chosen after the labeled benchmark, not before it (Decision 7B).
- Open question: guest and authenticated quotas, trial dates, report sharing rules, and the trial reward eligibility threshold need product decisions before their dependent release steps.
- Open question: production media retention and source-platform terms need approval before storing review media in production.
- Open question: Azure SKUs and scaling limits follow load and cost evidence.
