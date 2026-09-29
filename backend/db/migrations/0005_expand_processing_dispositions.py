from yoyo import step


__depends__ = {"0004_harden_analysis_processing"}


steps = [
    step(
        """
        ALTER TABLE analyses
          DROP CONSTRAINT analyses_final_disposition_check,
          ADD CONSTRAINT analyses_final_disposition_check CHECK (
            final_disposition IS NULL OR final_disposition IN (
              'DLQ_PENDING', 'DEAD_LETTERED', 'PUBLICATION_FAILED'
            )
          );
        ALTER TABLE analysis_status_events
          DROP CONSTRAINT analysis_status_events_disposition_check,
          ADD CONSTRAINT analysis_status_events_disposition_check CHECK (
            disposition IS NULL OR disposition IN (
              'DLQ_PENDING', 'DEAD_LETTERED', 'PUBLICATION_FAILED'
            )
          );
        """,
        """
        UPDATE analyses
        SET final_disposition = 'DLQ_PENDING'
        WHERE final_disposition = 'PUBLICATION_FAILED';
        UPDATE analysis_status_events
        SET disposition = 'DLQ_PENDING'
        WHERE disposition = 'PUBLICATION_FAILED';
        ALTER TABLE analysis_status_events
          DROP CONSTRAINT analysis_status_events_disposition_check,
          ADD CONSTRAINT analysis_status_events_disposition_check CHECK (
            disposition IS NULL OR disposition IN ('DLQ_PENDING', 'DEAD_LETTERED')
          );
        ALTER TABLE analyses
          DROP CONSTRAINT analyses_final_disposition_check,
          ADD CONSTRAINT analyses_final_disposition_check CHECK (
            final_disposition IS NULL OR final_disposition IN ('DLQ_PENDING', 'DEAD_LETTERED')
          );
        """,
    )
]
