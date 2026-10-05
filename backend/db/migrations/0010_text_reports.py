from yoyo import step

__depends__ = {"0009_allow_snapshot_replay"}

steps = [step("""
CREATE TABLE text_report_jobs (
  analysis_id uuid PRIMARY KEY REFERENCES analyses(id) ON DELETE CASCADE,
  snapshot_id uuid REFERENCES supplier_snapshots(id),
  state text NOT NULL CHECK (state IN ('QUEUED','PROCESSING','READY','UNAVAILABLE','INSUFFICIENT','FAILED','UNCERTAIN')),
  failure_code text,
  lease_token uuid,
  leased_until timestamptz,
  report jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  generated_at timestamptz,
  CHECK ((state = 'READY') = (report IS NOT NULL))
);
CREATE INDEX text_report_jobs_pending_idx ON text_report_jobs(created_at) WHERE state IN ('QUEUED','PROCESSING');
CREATE TABLE text_report_dispatches (
  dispatch_id uuid PRIMARY KEY,
  analysis_id uuid UNIQUE REFERENCES text_report_jobs(analysis_id) ON DELETE SET NULL,
  reserved_usd numeric NOT NULL CHECK (reserved_usd > 0),
  actual_usd numeric CHECK (actual_usd >= 0),
  metadata jsonb NOT NULL,
  dispatched_at timestamptz NOT NULL DEFAULT now(),
  settled_at timestamptz
);
INSERT INTO text_report_jobs(analysis_id, snapshot_id, state, failure_code)
SELECT a.id, a.supplier_snapshot_id,
       CASE WHEN a.supplier_snapshot_id IS NULL THEN 'INSUFFICIENT' ELSE 'QUEUED' END,
       CASE WHEN a.supplier_snapshot_id IS NULL THEN 'NO_SNAPSHOT' ELSE NULL END
FROM analyses a WHERE a.status = 'COMPLETED' AND a.user_id IS NOT NULL AND a.actor_type <> 'GUEST';
""", "DROP TABLE text_report_dispatches; DROP TABLE text_report_jobs;")]
