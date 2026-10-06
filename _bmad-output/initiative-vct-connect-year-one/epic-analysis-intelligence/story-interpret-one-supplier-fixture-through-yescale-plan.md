---
title: 'Interpret one supplier fixture through YEScale'
type: 'story'
ticket: '1'
created: '2026-10-06'
status: 'built'
baseline_revision: '50c9f37df40476c8be22f1a49af745e0a4e120e8'
route: 'full'
review: 'thorough'
context:
  - '_bmad-output/initiative-vct-connect-year-one/epic-analysis-intelligence/epic-analysis-intelligence.md'
  - '_bmad-output/initiative-vct-connect-year-one/epic-analysis-intelligence/tickets.toml'
---

<frozen-after-approval reason="user approved starting Epic 3 implementation on 2026-10-06">

## Intent

**Problem:** Extraction now produces versioned SupplierData snapshots, but VCT Connect has no backend AI interpretation or immutable model-run provenance. The current risk UI remains demonstration-only.

**Approach:** Add a provider-neutral LLM boundary and a server-only YEScale adapter, validate one grounded Vietnamese interpretation against a strict schema, and persist the complete run provenance for one already-completed supplier snapshot. Keep Story 3.1 outside the extraction worker so paid model calls cannot yet be duplicated by queue replay; Story 3.7 owns end-to-end worker integration.

## Boundaries & Constraints

**Always:** Use only normalized SupplierData evidence; missing fields remain unknown. Persist model, prompt, pipeline and schema versions, settings, provider request ID, tokens, latency, cost when reported, and structured output. Keep YEScale credentials server-side. Retain deterministic input hashing and strict output validation.

**Never:** Let the LLM emit the product's overall risk score, risk label, factory/trader verdict, or final purchasing decision. Do not label individual reviews fake. Do not expose the YEScale key to Next.js, the Chrome extension, API responses, logs, or source control. Do not change current extraction `COMPLETED` semantics in this story.

</frozen-after-approval>

## Code Map

- `backend/app/intelligence/contracts.py` — versioned Vietnamese interpretation schema and canonical evidence references.
- `backend/app/intelligence/provider.py` — provider-neutral structured completion interface and usage/provenance record.
- `backend/app/intelligence/yescale.py` — OpenAI-compatible YEScale Chat Completions adapter using `api.yescale.io/v1` and `X-YEScale-Metadata`.
- `backend/app/intelligence/interpretation.py` — stable SupplierData projection, prompt, deterministic input hash and schema validation.
- `backend/app/intelligence/store.py` — snapshot lookup and immutable LLM run persistence.
- `backend/app/intelligence/service.py` — sidecar Story 3.1 orchestration for a completed snapshot.
- `backend/app/intelligence/cli.py` — manual one-snapshot tracer.
- `backend/db/migrations/0010_llm_review_runs.py` — model-run provenance schema.
- `infra/azure/main.bicep` — map Key Vault secret `yescale-api-key` only into the analysis Job.
- `backend/tests/test_intelligence*.py` — provider/contract tests plus PostgreSQL provenance integration.

## Acceptance

- A fixed SupplierData fixture produces Vietnamese structured output with calibrated confidence and only canonical evidence references.
- Extra fields such as `risk_score` are rejected by schema validation.
- A fake provider proves persistence of output, confidence, requested/actual model, prompt/pipeline/schema versions, settings, request ID, token counts, latency, cost and created time.
- YEScale requests use bearer auth, JSON-object mode and bounded metadata; errors do not echo provider bodies or credentials.
- The Azure analysis Job resolves `yescale-api-key` from Key Vault; web/API/dispatcher do not receive it.
- No worker path invokes YEScale yet; full queued assessment and duplicate-spend prevention remain Story 3.7.

## Cost provenance note

YEScale's public guidance exposes request IDs and token usage while cost is primarily reconciled in Control Plane. The adapter records provider-returned cost when present; otherwise `cost_status=UNAVAILABLE` and the provider request ID remains the audit key for later Control Plane reconciliation. No estimated price is invented in application code.

## Verification

- `pytest -q backend/tests/test_intelligence.py` — isolated provider/contract tests.
- `pytest -q backend/tests/test_intelligence_postgres.py` with `VCT_TEST_DATABASE_URL` — migration and persisted provenance.
- `python -m py_compile backend/app/intelligence/*.py backend/db/migrations/0010_llm_review_runs.py`.
- Normal repository CI remains the release gate after the change is pushed.

