from yoyo import step


__depends__ = {"0011_worker_assessments"}


steps = [
    step(
        """
        ALTER TABLE llm_review_runs
          DROP CONSTRAINT llm_review_runs_run_kind_check,
          ADD CONSTRAINT llm_review_runs_run_kind_check CHECK (
            run_kind IN (
              'SUPPLIER_INTERPRETATION',
              'REVIEW_INTERPRETATION',
              'MEDIA_INTERPRETATION'
            )
          );

        ALTER TABLE analysis_assessments
          ADD COLUMN media_analysis JSONB,
          ADD CONSTRAINT analysis_assessments_media_object_check CHECK (
            media_analysis IS NULL OR jsonb_typeof(media_analysis) = 'object'
          );
        """,
        """
        ALTER TABLE analysis_assessments
          DROP CONSTRAINT analysis_assessments_media_object_check,
          DROP COLUMN media_analysis;

        ALTER TABLE llm_review_runs
          DROP CONSTRAINT llm_review_runs_run_kind_check,
          ADD CONSTRAINT llm_review_runs_run_kind_check CHECK (
            run_kind IN ('SUPPLIER_INTERPRETATION', 'REVIEW_INTERPRETATION')
          );
        """,
    )
]
