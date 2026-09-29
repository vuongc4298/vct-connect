from yoyo import step


__depends__ = set()


steps = [
    step(
        """
        CREATE TABLE analyses (
          id UUID PRIMARY KEY,
          source_url TEXT NOT NULL,
          status TEXT NOT NULL CHECK (status IN ('CREATED', 'QUEUED', 'COMPLETED')),
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          completed_at TIMESTAMPTZ
        );

        CREATE TABLE analysis_results (
          analysis_id UUID PRIMARY KEY REFERENCES analyses(id),
          payload JSONB NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE local_queue (
          analysis_id UUID PRIMARY KEY REFERENCES analyses(id),
          available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          claimed_until TIMESTAMPTZ,
          attempts INTEGER NOT NULL DEFAULT 0
        );
        """,
        """
        DROP TABLE local_queue;
        DROP TABLE analysis_results;
        DROP TABLE analyses;
        """,
    )
]
