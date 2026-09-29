from yoyo import step


__depends__ = {"0007_1688_extraction_evidence"}


steps = [
    step(
        """
        ALTER TABLE analyses
          DROP CONSTRAINT analyses_extraction_method_check,
          ADD CONSTRAINT analyses_extraction_method_check
            CHECK (btrim(extraction_method) <> ''),
          DROP CONSTRAINT analyses_mode_check,
          ADD CONSTRAINT analyses_mode_check
            CHECK (mode IN ('GUEST_PUBLIC', 'ACCOUNT_PUBLIC', 'EXTENSION_ENHANCED'));
        """,
        """
        ALTER TABLE analyses
          DROP CONSTRAINT analyses_extraction_method_check,
          ADD CONSTRAINT analyses_extraction_method_check
            CHECK (btrim(extraction_method) <> ''),
          DROP CONSTRAINT analyses_mode_check,
          ADD CONSTRAINT analyses_mode_check
            CHECK (mode IN ('GUEST_PUBLIC', 'ACCOUNT_PUBLIC', 'EXTENSION_ENHANCED'));
        """,
    )
]
