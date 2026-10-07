"""Durable Story 3.7 assessment persistence and REPORTING handoff."""
from __future__ import annotations

from decimal import Decimal
import json
from uuid import UUID, uuid4

from backend.app.storage import LeaseLost, Store

from .assessment import AssessmentBundle
from .media import MediaInterpretationRun
from .semantic_reviews import SemanticReviewRun


def load_assessment_snapshot(
    store: Store,
    analysis_id: UUID,
    token: UUID,
) -> tuple[UUID, dict]:
    with store.connect() as conn:
        row = conn.execute(
            """SELECT a.status, a.processing_claim_token,
                      s.id AS supplier_snapshot_id, s.normalized_data
               FROM analyses a
               JOIN supplier_snapshots s ON s.id = a.supplier_snapshot_id
               WHERE a.id = %s AND s.analysis_id = a.id""",
            (analysis_id,),
        ).fetchone()
    if row is None:
        raise LookupError("Assessment snapshot not found")
    if row["status"] != "ASSESSING" or row["processing_claim_token"] != token:
        raise LeaseLost("Assessment lease is no longer current")
    return row["supplier_snapshot_id"], row["normalized_data"]


def assessment_exists(store: Store, analysis_id: UUID) -> bool:
    with store.connect() as conn:
        return conn.execute(
            "SELECT 1 FROM analysis_assessments WHERE analysis_id = %s",
            (analysis_id,),
        ).fetchone() is not None


def _cost_value(cost: Decimal | None) -> str | None:
    return str(cost) if isinstance(cost, Decimal) else None


def _supplier_model_run(bundle: AssessmentBundle) -> dict:
    run = bundle.supplier_run
    response = run.provider_response
    cost = response.usage.cost_usd
    return {
        "run_kind": "SUPPLIER_INTERPRETATION",
        "provider": response.provider,
        "provider_request_id": response.request_id,
        "model": response.requested_model,
        "model_version": response.response_model,
        "prompt_version": run.prompt_version,
        "pipeline_version": run.pipeline_version,
        "schema_version": run.schema_version,
        "settings": response.settings,
        "input_sha256": run.input_sha256,
        "input_payload": run.input_payload,
        "output": run.interpretation.model_dump(mode="json"),
        "confidence": run.interpretation.confidence,
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
        "cost_usd": _cost_value(cost),
        "cost_status": "REPORTED" if cost is not None else "UNAVAILABLE",
        "latency_ms": response.latency_ms,
        "raw_usage": response.usage.raw,
        "finish_reason": response.finish_reason,
        "created_at": run.created_at,
    }


def _review_model_run(bundle: AssessmentBundle) -> dict | None:
    if not isinstance(bundle.review_analysis, SemanticReviewRun):
        return None
    run = bundle.review_analysis
    chat = run.provider_response
    embedding = run.embedding_response
    chat_cost = chat.usage.cost_usd
    embedding_cost = embedding.usage.cost_usd
    combined_cost = (
        chat_cost + embedding_cost
        if chat_cost is not None and embedding_cost is not None
        else None
    )
    return {
        "run_kind": "REVIEW_INTERPRETATION",
        "provider": chat.provider,
        "provider_request_id": chat.request_id,
        "model": chat.requested_model,
        "model_version": chat.response_model,
        "prompt_version": run.prompt_version,
        "pipeline_version": run.pipeline_version,
        "schema_version": run.schema_version,
        "settings": {
            "chat": chat.settings,
            "embedding": {
                "provider": embedding.provider,
                "request_id": embedding.request_id,
                "requested_model": embedding.requested_model,
                "response_model": embedding.response_model,
                "settings": embedding.settings,
                "latency_ms": embedding.latency_ms,
            },
            "semantic_threshold": run.semantic_threshold,
        },
        "input_sha256": run.input_sha256,
        "input_payload": run.input_payload,
        "output": run.assessment.model_dump(mode="json"),
        "confidence": run.assessment.confidence,
        "prompt_tokens": chat.usage.prompt_tokens + embedding.usage.prompt_tokens,
        "completion_tokens": chat.usage.completion_tokens,
        "total_tokens": chat.usage.total_tokens + embedding.usage.total_tokens,
        "cost_usd": _cost_value(combined_cost),
        "cost_status": "REPORTED" if combined_cost is not None else "UNAVAILABLE",
        "latency_ms": chat.latency_ms + embedding.latency_ms,
        "raw_usage": {
            "chat": chat.usage.raw,
            "embedding": embedding.usage.raw,
        },
        "finish_reason": chat.finish_reason,
        "created_at": run.created_at,
    }


def _media_model_run(bundle: AssessmentBundle) -> dict | None:
    run = bundle.media_run
    if run is None or run.provider_response is None:
        return None
    response = run.provider_response
    cost = response.usage.cost_usd
    return {
        "run_kind": "MEDIA_INTERPRETATION",
        "provider": response.provider,
        "provider_request_id": response.request_id,
        "model": response.requested_model,
        "model_version": response.response_model,
        "prompt_version": run.prompt_version,
        "pipeline_version": run.pipeline_version,
        "schema_version": run.schema_version,
        "settings": response.settings,
        "input_sha256": run.input_sha256,
        "input_payload": run.input_payload,
        "output": run.assessment.model_dump(mode="json"),
        "confidence": run.assessment.confidence,
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
        "cost_usd": _cost_value(cost),
        "cost_status": "REPORTED" if cost is not None else "UNAVAILABLE",
        "latency_ms": response.latency_ms,
        "raw_usage": response.usage.raw,
        "finish_reason": response.finish_reason,
        "created_at": run.created_at,
    }


def _media_payload(bundle: AssessmentBundle) -> dict | None:
    run = bundle.media_run
    if run is None:
        return None
    return {
        "assessment": run.assessment.model_dump(mode="json"),
        "input_sha256": run.input_sha256,
        "prompt_version": run.prompt_version,
        "pipeline_version": run.pipeline_version,
        "schema_version": run.schema_version,
    }


def _review_payload(bundle: AssessmentBundle) -> dict:
    value = bundle.review_analysis
    if isinstance(value, SemanticReviewRun):
        return {
            "mode": "semantic",
            "assessment": value.assessment.model_dump(mode="json"),
            "deterministic_analysis": value.deterministic_analysis.model_dump(mode="json"),
            "semantic_clusters": [
                cluster.model_dump(mode="json") for cluster in value.semantic_clusters
            ],
            "embedding": {
                "provider": value.embedding_response.provider,
                "request_id": value.embedding_response.request_id,
                "requested_model": value.embedding_response.requested_model,
                "response_model": value.embedding_response.response_model,
                "latency_ms": value.embedding_response.latency_ms,
                "usage": value.embedding_response.usage.raw,
            },
        }
    return {
        "mode": "deterministic",
        "assessment": value.model_dump(mode="json"),
    }


def persist_assessment_and_handoff(
    store: Store,
    *,
    analysis_id: UUID,
    token: UUID,
    supplier_snapshot_id: UUID,
    bundle: AssessmentBundle,
) -> UUID:
    assessment_id = uuid4()
    supplier_run = _supplier_model_run(bundle)
    review_run = _review_model_run(bundle)
    media_run = _media_model_run(bundle)
    review_payload = _review_payload(bundle)
    media_payload = _media_payload(bundle)

    with store.connect() as conn:
        with conn.transaction():
            row = conn.execute(
                """SELECT status, processing_claim_token, attempt_count, supplier_snapshot_id
                   FROM analyses WHERE id = %s FOR UPDATE""",
                (analysis_id,),
            ).fetchone()
            if row is None:
                raise LookupError("Analysis not found")
            if row["status"] == "REPORTING":
                existing = conn.execute(
                    "SELECT id FROM analysis_assessments WHERE analysis_id = %s",
                    (analysis_id,),
                ).fetchone()
                if existing is None:
                    raise RuntimeError("REPORTING analysis is missing assessment")
                return existing["id"]
            if (
                row["status"] != "ASSESSING"
                or row["processing_claim_token"] != token
                or row["supplier_snapshot_id"] != supplier_snapshot_id
            ):
                raise LeaseLost("Assessment lease is no longer current")

            conn.execute(
                """INSERT INTO analysis_assessments (
                       id, analysis_id, supplier_snapshot_id, scoring_version,
                       supplier_interpretation, review_analysis, media_analysis,
                       identity_assessment, risk_assessment, confidence, data_coverage,
                       overall_risk, risk_label
                   ) VALUES (
                       %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb,
                       %s::jsonb, %s::jsonb, %s, %s, %s, %s
                   )""",
                (
                    assessment_id, analysis_id, supplier_snapshot_id,
                    bundle.risk.scoring_version,
                    json.dumps(bundle.supplier_run.interpretation.model_dump(mode="json"), ensure_ascii=False),
                    json.dumps(review_payload, ensure_ascii=False),
                    json.dumps(media_payload, ensure_ascii=False) if media_payload is not None else None,
                    json.dumps(bundle.identity.model_dump(mode="json"), ensure_ascii=False),
                    json.dumps(bundle.risk.model_dump(mode="json"), ensure_ascii=False),
                    bundle.risk.confidence,
                    bundle.risk.data_coverage,
                    bundle.risk.overall_risk,
                    bundle.risk.label,
                ),
            )

            for model_run in [supplier_run, review_run, media_run]:
                if model_run is None:
                    continue
                conn.execute(
                    """INSERT INTO llm_review_runs (
                           id, analysis_id, supplier_snapshot_id, assessment_id, run_kind,
                           provider, provider_request_id, model, model_version,
                           prompt_version, pipeline_version, schema_version, settings,
                           input_sha256, input_payload, output, confidence,
                           prompt_tokens, completion_tokens, total_tokens,
                           cost_usd, cost_status, latency_ms, raw_usage,
                           finish_reason, created_at
                       ) VALUES (
                           %s, %s, %s, %s, %s,
                           %s, %s, %s, %s,
                           %s, %s, %s, %s::jsonb,
                           %s, %s::jsonb, %s::jsonb, %s,
                           %s, %s, %s,
                           %s, %s, %s, %s::jsonb,
                           %s, %s
                       )""",
                    (
                        uuid4(), analysis_id, supplier_snapshot_id, assessment_id,
                        model_run["run_kind"], model_run["provider"],
                        model_run["provider_request_id"], model_run["model"],
                        model_run["model_version"], model_run["prompt_version"],
                        model_run["pipeline_version"], model_run["schema_version"],
                        json.dumps(model_run["settings"]), model_run["input_sha256"],
                        json.dumps(model_run["input_payload"], ensure_ascii=False),
                        json.dumps(model_run["output"], ensure_ascii=False),
                        model_run["confidence"], model_run["prompt_tokens"],
                        model_run["completion_tokens"], model_run["total_tokens"],
                        model_run["cost_usd"], model_run["cost_status"],
                        model_run["latency_ms"], json.dumps(model_run["raw_usage"]),
                        model_run["finish_reason"], model_run["created_at"],
                    ),
                )

            for finding in bundle.findings:
                conn.execute(
                    """INSERT INTO analysis_findings (
                           id, assessment_id, finding_key, finding_type, dimension,
                           severity, confidence, payload
                       ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)""",
                    (
                        uuid4(), assessment_id, finding["finding_key"],
                        finding["finding_type"], finding["dimension"],
                        finding["severity"], finding["confidence"],
                        json.dumps(finding["payload"], ensure_ascii=False),
                    ),
                )
            for evidence in bundle.evidence:
                conn.execute(
                    """INSERT INTO analysis_evidence (
                           id, assessment_id, evidence_id, source_kind, source_field, payload
                       ) VALUES (%s, %s, %s, %s, %s, %s::jsonb)""",
                    (
                        uuid4(), assessment_id, evidence["evidence_id"],
                        evidence["source_kind"], evidence["source_field"],
                        json.dumps(evidence["payload"], ensure_ascii=False),
                    ),
                )

            updated = conn.execute(
                """UPDATE analyses
                   SET status = 'REPORTING', assessed_at = now(),
                       failure_code = NULL, next_retry_at = NULL,
                       final_disposition = NULL,
                       processing_claim_token = NULL,
                       processing_claimed_until = NULL
                   WHERE id = %s AND processing_claim_token = %s
                   RETURNING id""",
                (analysis_id, token),
            ).fetchone()
            if updated is None:
                raise LeaseLost("Assessment lease is no longer current")
            Store._event(conn, analysis_id, "REPORTING", row["attempt_count"])
    return assessment_id
