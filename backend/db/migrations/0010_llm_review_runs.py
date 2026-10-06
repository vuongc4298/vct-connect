from yoyo import step


__depends__ = {"0009_allow_snapshot_replay"}


steps = [
    step(
        """
        CREATE TABLE llm_review_runs (
          id UUID PRIMARY KEY,
          analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
          supplier_snapshot_id UUID NOT NULL REFERENCES supplier_snapshots(id) ON DELETE CASCADE,
          provider TEXT NOT NULL,
          provider_request_id TEXT,
          model TEXT NOT NULL,
          model_version TEXT NOT NULL,
          prompt_version TEXT NOT NULL,
          pipeline_version TEXT NOT NULL,
          schema_version TEXT NOT NULL,
          settings JSONB NOT NULL,
          input_sha256 TEXT NOT NULL,
          input_payload JSONB NOT NULL,
          output JSONB NOT NULL,
          confidence NUMERIC(5, 4) NOT NULL,
          prompt_tokens INTEGER NOT NULL,
          completion_tokens INTEGER NOT NULL,
          total_tokens INTEGER NOT NULL,
          cost_usd NUMERIC(16, 8),
          cost_status TEXT NOT NULL,
          latency_ms INTEGER NOT NULL,
          raw_usage JSONB NOT NULL DEFAULT '{}'::jsonb,
          finish_reason TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT llm_review_runs_provider_nonblank CHECK (btrim(provider) <> ''),
          CONSTRAINT llm_review_runs_model_nonblank CHECK (btrim(model) <> '' AND btrim(model_version) <> ''),
          CONSTRAINT llm_review_runs_versions_nonblank CHECK (
            btrim(prompt_version) <> '' AND btrim(pipeline_version) <> '' AND btrim(schema_version) <> ''
          ),
          CONSTRAINT llm_review_runs_settings_object CHECK (jsonb_typeof(settings) = 'object'),
          CONSTRAINT llm_review_runs_input_payload_object CHECK (jsonb_typeof(input_payload) = 'object'),
          CONSTRAINT llm_review_runs_output_object CHECK (jsonb_typeof(output) = 'object'),
          CONSTRAINT llm_review_runs_raw_usage_object CHECK (jsonb_typeof(raw_usage) = 'object'),
          CONSTRAINT llm_review_runs_input_sha256 CHECK (input_sha256 ~ '^[0-9a-f]{64}$'),
          CONSTRAINT llm_review_runs_confidence CHECK (confidence >= 0 AND confidence <= 1),
          CONSTRAINT llm_review_runs_tokens CHECK (
            prompt_tokens >= 0 AND completion_tokens >= 0 AND total_tokens >= 0
            AND total_tokens >= prompt_tokens AND total_tokens >= completion_tokens
          ),
          CONSTRAINT llm_review_runs_cost CHECK (cost_usd IS NULL OR cost_usd >= 0),
          CONSTRAINT llm_review_runs_cost_status CHECK (
            (cost_status = 'REPORTED' AND cost_usd IS NOT NULL)
            OR (cost_status = 'UNAVAILABLE' AND cost_usd IS NULL)
          ),
          CONSTRAINT llm_review_runs_latency CHECK (latency_ms >= 0)
        );
        CREATE INDEX llm_review_runs_analysis_created_idx
          ON llm_review_runs (analysis_id, created_at DESC);
        CREATE INDEX llm_review_runs_snapshot_created_idx
          ON llm_review_runs (supplier_snapshot_id, created_at DESC);
        CREATE UNIQUE INDEX llm_review_runs_provider_request_id_key
          ON llm_review_runs (provider, provider_request_id)
          WHERE provider_request_id IS NOT NULL;
        """,
        """
        DROP INDEX llm_review_runs_provider_request_id_key;
        DROP INDEX llm_review_runs_snapshot_created_idx;
        DROP INDEX llm_review_runs_analysis_created_idx;
        DROP TABLE llm_review_runs;
        """,
    )
]

