from yoyo import step


__depends__ = {"0010_llm_review_runs"}


steps = [
    step(
        """
        ALTER TABLE analyses DROP CONSTRAINT analyses_status_check;
        ALTER TABLE analyses ADD CONSTRAINT analyses_status_check CHECK (
          status IN (
            'QUEUED', 'PROCESSING', 'ASSESSING', 'REPORTING',
            'FAILED_RETRYABLE', 'FAILED_FINAL', 'COMPLETED'
          )
        );
        ALTER TABLE analyses ADD COLUMN assessed_at TIMESTAMPTZ;

        ALTER TABLE analysis_status_events DROP CONSTRAINT analysis_status_events_status_check;
        ALTER TABLE analysis_status_events ADD CONSTRAINT analysis_status_events_status_check CHECK (
          status IN (
            'QUEUED', 'PROCESSING', 'ASSESSING', 'REPORTING',
            'FAILED_RETRYABLE', 'FAILED_FINAL', 'COMPLETED'
          )
        );

        ALTER TABLE llm_review_runs
          ADD COLUMN run_kind TEXT NOT NULL DEFAULT 'SUPPLIER_INTERPRETATION',
          ADD CONSTRAINT llm_review_runs_run_kind_check CHECK (
            run_kind IN ('SUPPLIER_INTERPRETATION', 'REVIEW_INTERPRETATION')
          );
        CREATE TABLE analysis_assessments (
          id UUID PRIMARY KEY,
          analysis_id UUID NOT NULL UNIQUE REFERENCES analyses(id) ON DELETE CASCADE,
          supplier_snapshot_id UUID NOT NULL UNIQUE REFERENCES supplier_snapshots(id) ON DELETE CASCADE,
          scoring_version TEXT NOT NULL,
          supplier_interpretation JSONB NOT NULL,
          review_analysis JSONB NOT NULL,
          identity_assessment JSONB NOT NULL,
          risk_assessment JSONB NOT NULL,
          confidence NUMERIC(5,4) NOT NULL,
          data_coverage NUMERIC(5,4) NOT NULL,
          overall_risk NUMERIC(7,4),
          risk_label TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT analysis_assessments_versions_nonblank CHECK (btrim(scoring_version) <> ''),
          CONSTRAINT analysis_assessments_json_objects CHECK (
            jsonb_typeof(supplier_interpretation) = 'object'
            AND jsonb_typeof(review_analysis) = 'object'
            AND jsonb_typeof(identity_assessment) = 'object'
            AND jsonb_typeof(risk_assessment) = 'object'
          ),
          CONSTRAINT analysis_assessments_confidence CHECK (confidence >= 0 AND confidence <= 1),
          CONSTRAINT analysis_assessments_coverage CHECK (data_coverage >= 0 AND data_coverage <= 1),
          CONSTRAINT analysis_assessments_risk CHECK (
            overall_risk IS NULL OR (overall_risk >= 0 AND overall_risk <= 100)
          ),
          CONSTRAINT analysis_assessments_label CHECK (
            risk_label IN ('LOW', 'MODERATE', 'HIGH', 'INSUFFICIENT_INFORMATION')
          )
        );

        ALTER TABLE llm_review_runs
          ADD COLUMN assessment_id UUID REFERENCES analysis_assessments(id) ON DELETE CASCADE;
        CREATE UNIQUE INDEX llm_review_runs_assessment_kind_key
          ON llm_review_runs (assessment_id, run_kind)
          WHERE assessment_id IS NOT NULL;

        CREATE TABLE analysis_findings (
          id UUID PRIMARY KEY,
          assessment_id UUID NOT NULL REFERENCES analysis_assessments(id) ON DELETE CASCADE,
          finding_key TEXT NOT NULL,
          finding_type TEXT NOT NULL,
          dimension TEXT,
          severity NUMERIC(7,4),
          confidence NUMERIC(5,4),
          payload JSONB NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT analysis_findings_key_nonblank CHECK (btrim(finding_key) <> ''),
          CONSTRAINT analysis_findings_type_nonblank CHECK (btrim(finding_type) <> ''),
          CONSTRAINT analysis_findings_severity CHECK (
            severity IS NULL OR (severity >= 0 AND severity <= 100)
          ),
          CONSTRAINT analysis_findings_confidence CHECK (
            confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
          ),
          CONSTRAINT analysis_findings_payload_object CHECK (jsonb_typeof(payload) = 'object'),
          UNIQUE (assessment_id, finding_key)
        );

        CREATE TABLE analysis_evidence (
          id UUID PRIMARY KEY,
          assessment_id UUID NOT NULL REFERENCES analysis_assessments(id) ON DELETE CASCADE,
          evidence_id TEXT NOT NULL,
          source_kind TEXT NOT NULL,
          source_field TEXT,
          payload JSONB NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT analysis_evidence_id_nonblank CHECK (btrim(evidence_id) <> ''),
          CONSTRAINT analysis_evidence_source_nonblank CHECK (btrim(source_kind) <> ''),
          CONSTRAINT analysis_evidence_payload_object CHECK (jsonb_typeof(payload) = 'object'),
          UNIQUE (assessment_id, evidence_id)
        );

        CREATE INDEX analysis_findings_assessment_type_idx
          ON analysis_findings (assessment_id, finding_type);
        CREATE INDEX analysis_evidence_assessment_source_idx
          ON analysis_evidence (assessment_id, source_kind);
        """,
        """
        DROP INDEX analysis_evidence_assessment_source_idx;
        DROP INDEX analysis_findings_assessment_type_idx;
        DROP TABLE analysis_evidence;
        DROP TABLE analysis_findings;
        DROP INDEX llm_review_runs_assessment_kind_key;
        ALTER TABLE llm_review_runs DROP COLUMN assessment_id;
        DROP TABLE analysis_assessments;
        ALTER TABLE llm_review_runs
          DROP CONSTRAINT llm_review_runs_run_kind_check,
          DROP COLUMN run_kind;

        UPDATE analyses SET status = 'COMPLETED', completed_at = COALESCE(completed_at, assessed_at, now())
          WHERE status = 'REPORTING';
        UPDATE analyses SET status = 'PROCESSING'
          WHERE status = 'ASSESSING';
        UPDATE analysis_status_events SET status = 'COMPLETED'
          WHERE status = 'REPORTING';
        UPDATE analysis_status_events SET status = 'PROCESSING'
          WHERE status = 'ASSESSING';

        ALTER TABLE analysis_status_events DROP CONSTRAINT analysis_status_events_status_check;
        ALTER TABLE analysis_status_events ADD CONSTRAINT analysis_status_events_status_check CHECK (
          status IN ('QUEUED', 'PROCESSING', 'FAILED_RETRYABLE', 'FAILED_FINAL', 'COMPLETED')
        );

        ALTER TABLE analyses DROP COLUMN assessed_at;
        ALTER TABLE analyses DROP CONSTRAINT analyses_status_check;
        ALTER TABLE analyses ADD CONSTRAINT analyses_status_check CHECK (
          status IN ('QUEUED', 'PROCESSING', 'FAILED_RETRYABLE', 'FAILED_FINAL', 'COMPLETED')
        );
        """,
    )
]
