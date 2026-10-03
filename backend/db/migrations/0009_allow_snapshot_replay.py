from yoyo import step


__depends__ = {"0008_allow_public_extraction"}


steps = [
    step(
        # A snapshot belongs to one analysis, not one capture timestamp. Replay
        # preserves that timestamp and writes evidence for a new analysis.
        """ALTER TABLE supplier_snapshots
             DROP CONSTRAINT supplier_snapshots_supplier_extracted_key;""",
        """DO $$ BEGIN
             IF EXISTS (SELECT 1 FROM supplier_snapshots
                        GROUP BY supplier_id, extracted_at HAVING count(*) > 1) THEN
               RAISE EXCEPTION 'Snapshot replay rows must be retained; rollback cannot restore capture-time uniqueness';
             END IF;
           END $$;
           ALTER TABLE supplier_snapshots
             ADD CONSTRAINT supplier_snapshots_supplier_extracted_key
             UNIQUE (supplier_id, extracted_at);""",
    )
]
