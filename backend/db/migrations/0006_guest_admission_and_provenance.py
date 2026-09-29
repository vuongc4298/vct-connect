from yoyo import step


__depends__ = {"0005_expand_processing_dispositions"}


steps = [
    step(
        """
        ALTER TABLE analyses
          ADD COLUMN guest_key_hash TEXT,
          ADD COLUMN actor_type TEXT NOT NULL DEFAULT 'LEGACY',
          ADD COLUMN extraction_method TEXT NOT NULL DEFAULT 'FIXTURE';
        UPDATE analyses
        SET mode = COALESCE(mode, CASE WHEN user_id IS NULL THEN 'GUEST_PUBLIC' ELSE 'ACCOUNT_PUBLIC' END),
            scoring_version = COALESCE(scoring_version, 'v0.1.0'),
            actor_type = CASE WHEN user_id IS NULL THEN 'LEGACY' ELSE 'CUSTOMER' END,
            extraction_method = COALESCE(
              (SELECT snapshot.extraction_method
               FROM supplier_snapshots AS snapshot
               WHERE snapshot.id = analyses.supplier_snapshot_id),
              'FIXTURE'
            );
        ALTER TABLE analyses
          ADD CONSTRAINT analyses_mode_check CHECK (mode IN ('GUEST_PUBLIC', 'ACCOUNT_PUBLIC', 'EXTENSION_ENHANCED')),
          ADD CONSTRAINT analyses_actor_type_check CHECK (actor_type IN ('LEGACY', 'GUEST', 'CUSTOMER')),
          ADD CONSTRAINT analyses_extraction_method_check CHECK (btrim(extraction_method) <> ''),
          ADD CONSTRAINT analyses_guest_key_hash_check CHECK (
            guest_key_hash IS NULL OR guest_key_hash ~ '^[0-9a-f]{64}$'
          );
        CREATE INDEX analyses_guest_key_hash_idx ON analyses (guest_key_hash, id)
          WHERE guest_key_hash IS NOT NULL;

        CREATE TABLE admission_counters (
          scope TEXT NOT NULL CHECK (scope IN ('GUEST_BROWSER', 'GUEST_GLOBAL', 'CUSTOMER')),
          subject TEXT NOT NULL,
          window_number BIGINT NOT NULL,
          used INTEGER NOT NULL CHECK (used > 0),
          PRIMARY KEY (scope, subject, window_number)
        );
        """,
        """
        DROP TABLE admission_counters;
        DROP INDEX analyses_guest_key_hash_idx;
        ALTER TABLE analyses
          DROP CONSTRAINT analyses_guest_key_hash_check,
          DROP CONSTRAINT analyses_extraction_method_check,
          DROP CONSTRAINT analyses_actor_type_check,
          DROP CONSTRAINT analyses_mode_check,
          DROP COLUMN extraction_method,
          DROP COLUMN actor_type,
          DROP COLUMN guest_key_hash;
        """,
    )
]
