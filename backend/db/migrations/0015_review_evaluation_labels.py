from yoyo import step

__depends__ = {"0014_watchlist"}

steps = [
    step(
        """
        CREATE TABLE review_evaluation_labels (
          id UUID PRIMARY KEY,
          run_id UUID NOT NULL REFERENCES llm_review_runs(id) ON DELETE CASCADE,
          review_ordinal INTEGER NOT NULL CHECK (review_ordinal >= 0),
          reviewer_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          sentiment TEXT NOT NULL CHECK (sentiment IN ('POSITIVE', 'NEGATIVE', 'NEUTRAL', 'MIXED', 'UNCERTAIN')),
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE (run_id, review_ordinal, reviewer_id)
        );
        CREATE INDEX review_evaluation_labels_reviewer_idx
          ON review_evaluation_labels (reviewer_id, created_at DESC);
        """,
        """
        DROP INDEX review_evaluation_labels_reviewer_idx;
        DROP TABLE review_evaluation_labels;
        """,
    )
]
