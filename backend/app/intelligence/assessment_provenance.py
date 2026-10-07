"""Pure serialization of assessment/model provenance for persistence.

Story 3.8 extracted this from assessment_store so persistence owns transactions only.
The returned dictionaries intentionally preserve the existing database JSON shape.
"""
from __future__ import annotations

from decimal import Decimal

from .assessment import AssessmentBundle
from .semantic_reviews import SemanticReviewRun


def _cost_value(cost: Decimal | None) -> str | None:
    return str(cost) if isinstance(cost, Decimal) else None


def supplier_model_run(bundle: AssessmentBundle) -> dict:
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


def review_model_run(bundle: AssessmentBundle) -> dict | None:
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


def media_model_run(bundle: AssessmentBundle) -> dict | None:
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


def media_payload(bundle: AssessmentBundle) -> dict | None:
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


def review_payload(bundle: AssessmentBundle) -> dict:
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
