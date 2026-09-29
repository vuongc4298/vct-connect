from yoyo import step


__depends__ = {"0006_guest_admission_and_provenance"}


steps = [
    step(
        """
        ALTER TABLE supplier_snapshots
          ADD COLUMN analysis_id UUID UNIQUE REFERENCES analyses(id),
          ADD COLUMN missing_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
          ADD CONSTRAINT supplier_snapshots_missing_fields_array_check
            CHECK (jsonb_typeof(missing_fields) = 'array');
        CREATE TABLE supplier_reviews (
          id UUID PRIMARY KEY,
          snapshot_id UUID NOT NULL REFERENCES supplier_snapshots(id) ON DELETE CASCADE,
          ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
          payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
          UNIQUE (snapshot_id, ordinal)
        );
        """,
        """
        DROP TABLE supplier_reviews;
        ALTER TABLE supplier_snapshots
          DROP CONSTRAINT supplier_snapshots_missing_fields_array_check,
          DROP COLUMN missing_fields,
          DROP COLUMN analysis_id;
        """,
    )
]
