from yoyo import step

__depends__ = {"0015_review_evaluation_labels"}

steps = [
    step(
        """
        ALTER TABLE review_evaluation_labels
          ADD COLUMN complaint_category TEXT NOT NULL DEFAULT 'OTHER'
            CHECK (complaint_category IN ('QUALITY','DELIVERY','AFTER_SALES','PRODUCT_MISMATCH','PACKAGING','OTHER','NONE','UNCERTAIN')),
          ADD COLUMN severity TEXT NOT NULL DEFAULT 'NONE'
            CHECK (severity IN ('NONE','LOW','MEDIUM','HIGH','UNCERTAIN')),
          ADD COLUMN suspicious_indicators TEXT[] NOT NULL DEFAULT ARRAY[]::text[],
          ADD COLUMN correctness TEXT NOT NULL DEFAULT 'UNCERTAIN'
            CHECK (correctness IN ('CORRECT','PARTIALLY_CORRECT','INCORRECT','UNCERTAIN')),
          ADD COLUMN human_confidence NUMERIC(5,4) NOT NULL DEFAULT 0.5
            CHECK (human_confidence >= 0 AND human_confidence <= 1),
          ADD COLUMN notes TEXT NOT NULL DEFAULT '' CHECK (char_length(notes) <= 2000);
        ALTER TABLE review_evaluation_labels
          ADD CONSTRAINT review_label_suspicious_allowed CHECK (
            suspicious_indicators <@ ARRAY[
              'EXACT_DUPLICATE_TEXT','TIMING_BURST','RATING_TEXT_MISMATCH',
              'REVIEW_VOLUME_INCONSISTENCY','SEMANTIC_NEAR_DUPLICATE','OTHER'
            ]::text[] AND array_position(suspicious_indicators, NULL) IS NULL
          );
        """,
        """
        ALTER TABLE review_evaluation_labels DROP CONSTRAINT review_label_suspicious_allowed;
        ALTER TABLE review_evaluation_labels
          DROP COLUMN notes, DROP COLUMN human_confidence,
          DROP COLUMN correctness, DROP COLUMN suspicious_indicators,
          DROP COLUMN severity, DROP COLUMN complaint_category;
        """,
    )
]
