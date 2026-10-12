from yoyo import step

__depends__ = {"0016_review_annotation_fields"}

steps = [step("""
CREATE TABLE extension_collection_jobs (
  analysis_id UUID PRIMARY KEY REFERENCES analyses(id) ON DELETE CASCADE,
  initial_digest TEXT NOT NULL,
  initial_payload JSONB NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '60 seconds'),
  finished BOOLEAN NOT NULL DEFAULT false,
  final_digest TEXT
);
CREATE INDEX extension_collection_pending ON extension_collection_jobs(expires_at) WHERE NOT finished;
""", "DROP TABLE extension_collection_jobs;")]
