"""Blind reviewer case selection, labeling and post-submit pinned-model comparison."""
from __future__ import annotations

from uuid import UUID, uuid4

from .storage import Store


def list_blind_cases(store: Store, reviewer_id: UUID, limit: int = 20) -> list[dict]:
    """Never select model output, input payload, model name, or other labels."""
    with store.connect() as conn:
        rows = conn.execute(
            """SELECT run.id AS run_id, review.ordinal, review.payload->>'text' AS review_text,
                      review.payload->>'rating' AS rating,
                      a.source_url
               FROM llm_review_runs run
               JOIN analyses a ON a.id = run.analysis_id
               JOIN supplier_reviews review ON review.snapshot_id = run.supplier_snapshot_id
               WHERE run.run_kind = 'REVIEW_INTERPRETATION'
                 AND a.status = 'COMPLETED'
                 AND NULLIF(btrim(review.payload->>'text'), '') IS NOT NULL
                 AND NOT EXISTS (
                   SELECT 1 FROM review_evaluation_labels label
                   WHERE label.run_id = run.id AND label.review_ordinal = review.ordinal
                     AND label.reviewer_id = %s
                 )
               ORDER BY run.created_at DESC, run.id DESC, review.ordinal ASC
               LIMIT %s""",
            (reviewer_id, min(100, max(1, limit))),
        ).fetchall()
    return [dict(row) for row in rows]


def submit_blind_label(store: Store, reviewer_id: UUID, run_id: UUID, ordinal: int, sentiment: str) -> dict | None:
    if ordinal < 0:
        return None
    with store.connect() as conn:
        with conn.transaction():
            # Reject repeat submissions without releasing model information.
            existing = conn.execute(
                """SELECT 1 FROM review_evaluation_labels
                   WHERE run_id = %s AND review_ordinal = %s AND reviewer_id = %s""",
                (run_id, ordinal, reviewer_id),
            ).fetchone()
            if existing:
                raise ValueError("Case already labeled")
            case = conn.execute(
                """SELECT run.id AS run_id, review.ordinal,
                          review.payload->>'text' AS review_text, run.output AS model_output,
                          run.model, run.prompt_version, run.schema_version
                   FROM llm_review_runs run
                   JOIN analyses a ON a.id = run.analysis_id
                   JOIN supplier_reviews review ON review.snapshot_id = run.supplier_snapshot_id
                   WHERE run.id = %s AND review.ordinal = %s
                     AND run.run_kind = 'REVIEW_INTERPRETATION'
                     AND a.status = 'COMPLETED'
                     AND NULLIF(btrim(review.payload->>'text'), '') IS NOT NULL
                   FOR UPDATE OF run""",
                (run_id, ordinal),
            ).fetchone()
            if case is None:
                return None
            label_id = uuid4()
            inserted = conn.execute(
                """INSERT INTO review_evaluation_labels
                     (id, run_id, review_ordinal, reviewer_id, sentiment)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (run_id, review_ordinal, reviewer_id) DO NOTHING
                   RETURNING id""",
                (label_id, run_id, ordinal, reviewer_id, sentiment),
            ).fetchone()
            if inserted is None:
                raise ValueError("Case already labeled")
            return {
                "label_id": label_id, "run_id": run_id, "review_ordinal": ordinal,
                "sentiment": sentiment, "review_text": case["review_text"],
                "model_output": case["model_output"], "model": case["model"],
                "prompt_version": case["prompt_version"], "schema_version": case["schema_version"],
            }
