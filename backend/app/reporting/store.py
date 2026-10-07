"""Durable report persistence and final COMPLETED handoff."""
from __future__ import annotations

import json
from uuid import UUID, uuid4

from backend.app.storage import LeaseLost, ResultConflict, Store

from .contracts import REPORT_SCHEMA_VERSION, ReportPayload


def load_report_source(
    store: Store,
    analysis_id: UUID,
    token: UUID,
) -> dict:
    with store.connect() as conn:
        row = conn.execute(
            """SELECT a.status, a.processing_claim_token, a.attempt_count,
                      a.source_url, a.supplier_snapshot_id,
                      aa.id AS assessment_id, aa.scoring_version,
                      aa.supplier_interpretation, aa.review_analysis,
                      aa.identity_assessment, aa.risk_assessment,
                      s.normalized_data, s.missing_fields
               FROM analyses a
               JOIN analysis_assessments aa ON aa.analysis_id = a.id
               JOIN supplier_snapshots s ON s.id = a.supplier_snapshot_id
               WHERE a.id = %s""",
            (analysis_id,),
        ).fetchone()
        if row is None:
            raise LookupError("Report source assessment not found")
        if row["status"] != "REPORTING" or row["processing_claim_token"] != token:
            raise LeaseLost("Reporting lease is no longer current")

        findings = conn.execute(
            """SELECT finding_key, finding_type, dimension, severity, confidence, payload
               FROM analysis_findings
               WHERE assessment_id = %s
               ORDER BY finding_key""",
            (row["assessment_id"],),
        ).fetchall()
        evidence = conn.execute(
            """SELECT evidence_id, source_kind, source_field, payload
               FROM analysis_evidence
               WHERE assessment_id = %s
               ORDER BY evidence_id""",
            (row["assessment_id"],),
        ).fetchall()
        reviews = conn.execute(
            """SELECT ordinal, payload
               FROM supplier_reviews
               WHERE snapshot_id = %s
               ORDER BY ordinal""",
            (row["supplier_snapshot_id"],),
        ).fetchall()

    return {
        "analysis_id": analysis_id,
        "source_url": row["source_url"],
        "assessment": {
            "id": row["assessment_id"],
            "scoring_version": row["scoring_version"],
            "supplier_interpretation": row["supplier_interpretation"],
            "review_analysis": row["review_analysis"],
            "identity_assessment": row["identity_assessment"],
            "risk_assessment": row["risk_assessment"],
        },
        "snapshot": {
            "normalized_data": row["normalized_data"],
            "missing_fields": row["missing_fields"],
        },
        "findings": findings,
        "evidence": evidence,
        "raw_reviews": reviews,
    }


def persist_report_and_complete(
    store: Store,
    *,
    analysis_id: UUID,
    token: UUID,
    assessment_id: UUID,
    scoring_version: str,
    report: ReportPayload,
) -> UUID:
    payload = report.model_dump(mode="json")
    payload_json = json.dumps(payload, ensure_ascii=False)
    report_id = uuid4()

    with store.connect() as conn:
        with conn.transaction():
            row = conn.execute(
                """SELECT status, processing_claim_token, attempt_count
                   FROM analyses WHERE id = %s FOR UPDATE""",
                (analysis_id,),
            ).fetchone()
            if row is None:
                raise LookupError("Analysis not found")

            if row["status"] == "COMPLETED":
                existing = conn.execute(
                    """SELECT id, assessment_id, schema_version, language, payload
                       FROM reports WHERE analysis_id = %s""",
                    (analysis_id,),
                ).fetchone()
                if existing is None:
                    raise RuntimeError("COMPLETED analysis is missing report")
                if (
                    existing["assessment_id"] != assessment_id
                    or existing["schema_version"] != REPORT_SCHEMA_VERSION
                    or existing["language"] != "vi"
                    or existing["payload"] != payload
                ):
                    raise ResultConflict("Completed analysis has a different immutable report")
                return existing["id"]

            if row["status"] != "REPORTING" or row["processing_claim_token"] != token:
                raise LeaseLost("Reporting lease is no longer current")

            inserted = conn.execute(
                """INSERT INTO reports (
                       id, analysis_id, assessment_id, schema_version, language, payload
                   ) VALUES (%s, %s, %s, %s, 'vi', %s::jsonb)
                   ON CONFLICT (analysis_id) DO NOTHING
                   RETURNING id""",
                (
                    report_id,
                    analysis_id,
                    assessment_id,
                    REPORT_SCHEMA_VERSION,
                    payload_json,
                ),
            ).fetchone()
            if inserted is None:
                existing = conn.execute(
                    """SELECT id, assessment_id, schema_version, language, payload
                       FROM reports WHERE analysis_id = %s""",
                    (analysis_id,),
                ).fetchone()
                if (
                    existing is None
                    or existing["assessment_id"] != assessment_id
                    or existing["schema_version"] != REPORT_SCHEMA_VERSION
                    or existing["language"] != "vi"
                    or existing["payload"] != payload
                ):
                    raise ResultConflict("Stored report conflicts with generated report")
                report_id = existing["id"]

            updated = conn.execute(
                """UPDATE analyses
                   SET status = 'COMPLETED',
                       completed_at = COALESCE(completed_at, now()),
                       scoring_version = %s,
                       failure_code = NULL,
                       next_retry_at = NULL,
                       final_disposition = NULL,
                       processing_claim_token = NULL,
                       processing_claimed_until = NULL
                   WHERE id = %s AND processing_claim_token = %s
                   RETURNING id""",
                (scoring_version, analysis_id, token),
            ).fetchone()
            if updated is None:
                raise LeaseLost("Reporting lease is no longer current")
            Store._event(
                conn,
                analysis_id,
                "COMPLETED",
                row["attempt_count"],
            )
    return report_id
