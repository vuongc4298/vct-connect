from yoyo import step


__depends__ = {"0003_align_core_schema_to_spec"}


steps = [
    step(
        """
        ALTER TABLE analyses DROP CONSTRAINT analyses_status_check;
        ALTER TABLE analyses
          ADD CONSTRAINT analyses_status_check CHECK (
            status IN ('CREATED', 'QUEUED', 'PROCESSING', 'FAILED_RETRYABLE', 'FAILED_FINAL', 'COMPLETED')
          ),
          ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0,
          ADD COLUMN processing_claim_token UUID,
          ADD COLUMN processing_claimed_until TIMESTAMPTZ,
          ADD COLUMN processing_started_at TIMESTAMPTZ,
          ADD COLUMN failure_code TEXT,
          ADD COLUMN next_retry_at TIMESTAMPTZ,
          ADD COLUMN final_disposition TEXT,
          ADD CONSTRAINT analyses_attempt_count_check CHECK (attempt_count >= 0),
          ADD CONSTRAINT analyses_failure_code_check CHECK (
            failure_code IS NULL OR (char_length(failure_code) BETWEEN 1 AND 80 AND failure_code ~ '^[A-Z0-9_]+$')
          ),
          ADD CONSTRAINT analyses_final_disposition_check CHECK (
            final_disposition IS NULL OR final_disposition IN ('DLQ_PENDING', 'DEAD_LETTERED')
          );

        ALTER TABLE local_queue ADD COLUMN claim_token UUID;
        UPDATE local_queue
        SET claim_token = md5(analysis_id::text || claimed_until::text)::uuid
        WHERE claimed_until IS NOT NULL;
        ALTER TABLE local_queue
          ADD CONSTRAINT local_queue_claim_pair_check CHECK (
            (claim_token IS NULL AND claimed_until IS NULL)
            OR (claim_token IS NOT NULL AND claimed_until IS NOT NULL)
          );
        CREATE UNIQUE INDEX local_queue_claim_token_key
          ON local_queue (claim_token) WHERE claim_token IS NOT NULL;

        CREATE TABLE analysis_status_events (
          id BIGSERIAL PRIMARY KEY,
          analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
          status TEXT NOT NULL CHECK (
            status IN ('QUEUED', 'PROCESSING', 'FAILED_RETRYABLE', 'FAILED_FINAL', 'COMPLETED')
          ),
          attempt INTEGER NOT NULL DEFAULT 0 CHECK (attempt >= 0),
          failure_code TEXT,
          next_retry_at TIMESTAMPTZ,
          disposition TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT analysis_status_events_failure_code_check CHECK (
            failure_code IS NULL OR (char_length(failure_code) BETWEEN 1 AND 80 AND failure_code ~ '^[A-Z0-9_]+$')
          ),
          CONSTRAINT analysis_status_events_disposition_check CHECK (
            disposition IS NULL OR disposition IN ('DLQ_PENDING', 'DEAD_LETTERED')
          )
        );
        CREATE INDEX analysis_status_events_analysis_order_idx
          ON analysis_status_events (analysis_id, id);

        CREATE TABLE analysis_outbox (
          analysis_id UUID PRIMARY KEY REFERENCES analyses(id) ON DELETE CASCADE,
          message_id UUID NOT NULL UNIQUE,
          state TEXT NOT NULL DEFAULT 'PENDING'
            CHECK (state IN ('PENDING', 'PUBLISHED', 'FAILED_FINAL')),
          attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
          next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          lease_token UUID,
          leased_until TIMESTAMPTZ,
          published_at TIMESTAMPTZ,
          last_error_code TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT analysis_outbox_identity_check CHECK (message_id = analysis_id),
          CONSTRAINT analysis_outbox_lease_pair_check CHECK (
            (lease_token IS NULL AND leased_until IS NULL)
            OR (lease_token IS NOT NULL AND leased_until IS NOT NULL)
          ),
          CONSTRAINT analysis_outbox_error_code_check CHECK (
            last_error_code IS NULL OR (char_length(last_error_code) BETWEEN 1 AND 80 AND last_error_code ~ '^[A-Z0-9_]+$')
          )
        );
        CREATE INDEX analysis_outbox_dispatch_idx
          ON analysis_outbox (next_attempt_at, analysis_id) WHERE state = 'PENDING';
        CREATE UNIQUE INDEX analysis_outbox_lease_token_key
          ON analysis_outbox (lease_token) WHERE lease_token IS NOT NULL;

        INSERT INTO analysis_outbox (analysis_id, message_id)
        SELECT id, id FROM analyses WHERE status = 'CREATED';
        UPDATE analyses SET status = 'QUEUED' WHERE status = 'CREATED';
        ALTER TABLE analyses DROP CONSTRAINT analyses_status_check;
        ALTER TABLE analyses ADD CONSTRAINT analyses_status_check CHECK (
          status IN ('QUEUED', 'PROCESSING', 'FAILED_RETRYABLE', 'FAILED_FINAL', 'COMPLETED')
        );

        INSERT INTO analysis_status_events (analysis_id, status, attempt, created_at)
        SELECT id, status, 0, COALESCE(completed_at, created_at)
        FROM analyses;
        """,
        """
        DROP TABLE analysis_outbox;
        DROP INDEX analysis_status_events_analysis_order_idx;
        DROP TABLE analysis_status_events;
        DROP INDEX local_queue_claim_token_key;
        ALTER TABLE local_queue
          DROP CONSTRAINT local_queue_claim_pair_check,
          DROP COLUMN claim_token;
        UPDATE analyses
        SET status = 'QUEUED', completed_at = NULL
        WHERE status IN ('PROCESSING', 'FAILED_RETRYABLE', 'FAILED_FINAL');
        ALTER TABLE analyses
          DROP CONSTRAINT analyses_final_disposition_check,
          DROP CONSTRAINT analyses_failure_code_check,
          DROP CONSTRAINT analyses_attempt_count_check,
          DROP COLUMN final_disposition,
          DROP COLUMN next_retry_at,
          DROP COLUMN failure_code,
          DROP COLUMN processing_started_at,
          DROP COLUMN processing_claimed_until,
          DROP COLUMN processing_claim_token,
          DROP COLUMN attempt_count,
          DROP CONSTRAINT analyses_status_check,
          ADD CONSTRAINT analyses_status_check CHECK (
            status IN ('CREATED', 'QUEUED', 'COMPLETED')
          );
        """,
    )
]
