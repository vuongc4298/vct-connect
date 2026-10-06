"""Persistence boundary for Story 3.1 model-run provenance."""
from __future__ import annotations

from decimal import Decimal
import json
from uuid import UUID, uuid4

from backend.app.storage import Store

from .interpretation import InterpretationRun


def load_supplier_snapshot(store: Store, analysis_id: UUID) -> tuple[UUID, dict]:
    with store.connect() as conn:
        row = conn.execute(
            """SELECT s.id AS supplier_snapshot_id, s.normalized_data
               FROM analyses a
               JOIN supplier_snapshots s ON s.id = a.supplier_snapshot_id
               WHERE a.id = %s AND a.status = 'COMPLETED' AND s.analysis_id = a.id""",
            (analysis_id,),
        ).fetchone()
    if row is None:
        raise LookupError("Completed analysis with a supplier snapshot not found")
    return row["supplier_snapshot_id"], row["normalized_data"]


def persist_interpretation_run(
    store: Store,
    *,
    analysis_id: UUID,
    supplier_snapshot_id: UUID,
    run: InterpretationRun,
) -> UUID:
    run_id = uuid4()
    response = run.provider_response
    cost = response.usage.cost_usd
    with store.connect() as conn:
        with conn.transaction():
            linked = conn.execute(
                """SELECT 1
                   FROM analyses a JOIN supplier_snapshots s ON s.id = a.supplier_snapshot_id
                   WHERE a.id = %s AND s.id = %s AND s.analysis_id = a.id""",
                (analysis_id, supplier_snapshot_id),
            ).fetchone()
            if linked is None:
                raise ValueError("Supplier snapshot does not belong to the analysis")
            conn.execute(
                """INSERT INTO llm_review_runs (
                       id, analysis_id, supplier_snapshot_id, provider, provider_request_id,
                       model, model_version, prompt_version, pipeline_version, schema_version,
                       settings, input_sha256, input_payload, output, confidence, prompt_tokens,
                       completion_tokens, total_tokens, cost_usd, cost_status, latency_ms,
                       raw_usage, finish_reason, created_at
                   ) VALUES (
                       %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                       %s::jsonb, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s, %s, %s,
                       %s::jsonb, %s, %s
                   )""",
                (
                    run_id, analysis_id, supplier_snapshot_id, response.provider,
                    response.request_id, response.requested_model, response.response_model,
                    run.prompt_version, run.pipeline_version, run.schema_version,
                    json.dumps(response.settings), run.input_sha256,
                    json.dumps(run.input_payload, ensure_ascii=False),
                    json.dumps(run.interpretation.model_dump(mode="json"), ensure_ascii=False),
                    run.interpretation.confidence, response.usage.prompt_tokens,
                    response.usage.completion_tokens, response.usage.total_tokens,
                    str(cost) if isinstance(cost, Decimal) else None,
                    "REPORTED" if cost is not None else "UNAVAILABLE",
                    response.latency_ms, json.dumps(response.usage.raw),
                    response.finish_reason, run.created_at,
                ),
            )
    return run_id


def get_interpretation_run(store: Store, run_id: UUID) -> dict | None:
    with store.connect() as conn:
        return conn.execute(
            "SELECT * FROM llm_review_runs WHERE id = %s",
            (run_id,),
        ).fetchone()

