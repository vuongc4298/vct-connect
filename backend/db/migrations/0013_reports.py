from yoyo import step


__depends__ = {"0012_multimodal_assessments"}


steps = [
    step(
        """
        CREATE TABLE reports (
          id UUID PRIMARY KEY,
          analysis_id UUID NOT NULL UNIQUE REFERENCES analyses(id) ON DELETE CASCADE,
          assessment_id UUID NOT NULL UNIQUE REFERENCES analysis_assessments(id) ON DELETE CASCADE,
          schema_version TEXT NOT NULL,
          language TEXT NOT NULL,
          payload JSONB NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT reports_schema_nonblank CHECK (btrim(schema_version) <> ''),
          CONSTRAINT reports_language_check CHECK (language = 'vi'),
          CONSTRAINT reports_payload_object_check CHECK (jsonb_typeof(payload) = 'object')
        );

        CREATE INDEX reports_created_idx ON reports (created_at DESC);
        """,
        """
        DROP INDEX reports_created_idx;
        DROP TABLE reports;
        """,
    )
]
