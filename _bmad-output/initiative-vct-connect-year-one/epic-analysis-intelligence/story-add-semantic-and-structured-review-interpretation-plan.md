---
title: 'Add semantic and structured review interpretation'
type: 'story'
ticket: '3'
created: '2026-10-07'
status: 'built'
baseline_revision: 'd5888278362e93ffc74c58a45895747c315ca0e5'
route: 'full'
review: 'thorough'
---

<frozen-after-approval reason="user approved Epic 3 Story 3.3 on 2026-10-07">

## Intent

**Problem:** Story 3.2 provides deterministic lexical/statistical review signals, but paraphrased duplicate language and nuanced complaint severity need semantic interpretation.

**Approach:** Add a provider-neutral embedding contract and YEScale OpenAI-compatible embeddings adapter, cluster near-duplicate review language by cosine similarity, then feed review evidence plus deterministic and semantic signals to the existing structured LLM boundary for Vietnamese category/severity findings.

## Boundaries & Constraints

**Always:** Preserve deterministic Story 3.2 signals. Pin and record embedding/chat model identifiers, request IDs, usage/cost, prompt/schema/pipeline versions, input hash and threshold in the run object. Cite only supplied review evidence IDs. Compute review reliability deterministically.

**Never:** Label an individual review fake or fraudulent. Do not let the LLM calculate supplier risk. Do not persist findings or call this from the durable worker yet; Story 3.7 owns persistence, idempotency and worker integration. Do not hard-code an undocumented production embedding model; the operator selects YESCALE_EMBEDDING_MODEL until human evaluation settles the candidate.

</frozen-after-approval>

## Contract

- schema: review-interpretation.v1
- semantic clustering: cosine similarity, default threshold 0.88, connected components
- structured findings: category, severity, Vietnamese statement, confidence, evidence IDs
- combined suspicious patterns retain Story 3.2 patterns and add SEMANTIC_NEAR_DUPLICATE
- final review reliability starts from deterministic Story 3.2 reliability and receives a bounded semantic near-duplicate penalty
- run provenance includes embedding and chat provider responses plus prompt/pipeline/schema versions and deterministic input hash

## Verification

- mixed fixture yields Quality/Delivery severity findings, semantic near-duplicate clusters, combined suspicious patterns, reduced review reliability, confidence and full run provenance
- unknown evidence IDs and extra risk-score fields are rejected
- embedding response order is restored by provider index and malformed/non-finite vectors fail closed
- no live provider call is required in CI; fake embedding/chat providers make the Story deterministic
