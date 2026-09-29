from yoyo import step


__depends__ = {"0002_core_business_schema"}


steps = [
    step(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM entitlements)
             OR EXISTS (SELECT 1 FROM suppliers)
             OR EXISTS (SELECT 1 FROM supplier_snapshots) THEN
            RAISE EXCEPTION
              'Cannot align the provisional Story 1.3 schema while domain rows exist; map them explicitly first';
          END IF;
        END
        $$;

        ALTER TABLE users
          ADD COLUMN email TEXT,
          ADD CONSTRAINT users_clerk_user_id_nonblank_check
            CHECK (btrim(clerk_user_id) <> '');

        DROP INDEX entitlements_user_validity_idx;
        ALTER TABLE entitlements
          DROP CONSTRAINT entitlements_user_plan_start_key,
          DROP CONSTRAINT entitlements_valid_range_check;
        ALTER TABLE entitlements RENAME COLUMN plan_code TO entitlement;
        ALTER TABLE entitlements RENAME COLUMN valid_from TO starts_at;
        ALTER TABLE entitlements RENAME COLUMN valid_until TO expires_at;
        ALTER TABLE entitlements
          ADD COLUMN source TEXT NOT NULL,
          ADD COLUMN status TEXT NOT NULL,
          ADD CONSTRAINT entitlements_entitlement_nonblank_check
            CHECK (btrim(entitlement) <> ''),
          ADD CONSTRAINT entitlements_source_nonblank_check
            CHECK (btrim(source) <> ''),
          ADD CONSTRAINT entitlements_status_nonblank_check
            CHECK (btrim(status) <> ''),
          ADD CONSTRAINT entitlements_time_range_check
            CHECK (expires_at IS NULL OR expires_at > starts_at),
          ADD CONSTRAINT entitlements_user_record_key
            UNIQUE (user_id, entitlement, source, starts_at);
        CREATE INDEX entitlements_user_validity_idx
          ON entitlements (user_id, starts_at, expires_at);

        ALTER TABLE suppliers
          DROP CONSTRAINT suppliers_platform_external_id_key;
        ALTER TABLE suppliers RENAME COLUMN external_id TO platform_supplier_id;
        ALTER TABLE suppliers
          ALTER COLUMN platform_supplier_id DROP NOT NULL,
          ADD COLUMN name TEXT,
          ADD COLUMN source_url TEXT NOT NULL,
          ADD CONSTRAINT suppliers_source_url_nonblank_check
            CHECK (btrim(source_url) <> ''),
          ADD CONSTRAINT suppliers_platform_supplier_id_key
            UNIQUE (platform, platform_supplier_id);

        DROP INDEX supplier_snapshots_supplier_captured_idx;
        ALTER TABLE supplier_snapshots
          DROP CONSTRAINT supplier_snapshots_raw_object_check,
          DROP CONSTRAINT supplier_snapshots_normalized_object_check,
          DROP CONSTRAINT supplier_snapshots_completeness_check,
          DROP CONSTRAINT supplier_snapshots_supplier_capture_key;
        ALTER TABLE supplier_snapshots RENAME COLUMN captured_at TO extracted_at;
        ALTER TABLE supplier_snapshots RENAME COLUMN raw_document TO raw_payload;
        ALTER TABLE supplier_snapshots RENAME COLUMN normalized_document TO normalized_data;
        ALTER TABLE supplier_snapshots
          ALTER COLUMN completeness DROP NOT NULL,
          ADD COLUMN extraction_method TEXT NOT NULL,
          ADD COLUMN analysis_mode TEXT NOT NULL,
          ADD COLUMN extractor_version TEXT NOT NULL,
          ADD CONSTRAINT supplier_snapshots_raw_payload_object_check
            CHECK (jsonb_typeof(raw_payload) = 'object'),
          ADD CONSTRAINT supplier_snapshots_normalized_data_object_check
            CHECK (jsonb_typeof(normalized_data) = 'object'),
          ADD CONSTRAINT supplier_snapshots_extraction_method_nonblank_check
            CHECK (btrim(extraction_method) <> ''),
          ADD CONSTRAINT supplier_snapshots_analysis_mode_nonblank_check
            CHECK (btrim(analysis_mode) <> ''),
          ADD CONSTRAINT supplier_snapshots_extractor_version_nonblank_check
            CHECK (btrim(extractor_version) <> ''),
          ADD CONSTRAINT supplier_snapshots_completeness_check
            CHECK (completeness IS NULL OR (completeness >= 0 AND completeness <= 1)),
          ADD CONSTRAINT supplier_snapshots_supplier_extracted_key
            UNIQUE (supplier_id, extracted_at);
        CREATE INDEX supplier_snapshots_supplier_extracted_idx
          ON supplier_snapshots (supplier_id, extracted_at DESC);
        """,
        """
        UPDATE analyses
        SET user_id = NULL,
            supplier_snapshot_id = NULL;
        DELETE FROM supplier_snapshots;
        DELETE FROM entitlements;
        DELETE FROM suppliers;
        DELETE FROM users;

        DROP INDEX supplier_snapshots_supplier_extracted_idx;
        ALTER TABLE supplier_snapshots
          DROP CONSTRAINT supplier_snapshots_supplier_extracted_key,
          DROP CONSTRAINT supplier_snapshots_completeness_check,
          DROP CONSTRAINT supplier_snapshots_extractor_version_nonblank_check,
          DROP CONSTRAINT supplier_snapshots_analysis_mode_nonblank_check,
          DROP CONSTRAINT supplier_snapshots_extraction_method_nonblank_check,
          DROP CONSTRAINT supplier_snapshots_normalized_data_object_check,
          DROP CONSTRAINT supplier_snapshots_raw_payload_object_check,
          DROP COLUMN extractor_version,
          DROP COLUMN analysis_mode,
          DROP COLUMN extraction_method,
          ALTER COLUMN completeness SET NOT NULL;
        ALTER TABLE supplier_snapshots RENAME COLUMN normalized_data TO normalized_document;
        ALTER TABLE supplier_snapshots RENAME COLUMN raw_payload TO raw_document;
        ALTER TABLE supplier_snapshots RENAME COLUMN extracted_at TO captured_at;
        ALTER TABLE supplier_snapshots
          ADD CONSTRAINT supplier_snapshots_raw_object_check
            CHECK (jsonb_typeof(raw_document) = 'object'),
          ADD CONSTRAINT supplier_snapshots_normalized_object_check
            CHECK (jsonb_typeof(normalized_document) = 'object'),
          ADD CONSTRAINT supplier_snapshots_completeness_check
            CHECK (completeness >= 0 AND completeness <= 1),
          ADD CONSTRAINT supplier_snapshots_supplier_capture_key
            UNIQUE (supplier_id, captured_at);
        CREATE INDEX supplier_snapshots_supplier_captured_idx
          ON supplier_snapshots (supplier_id, captured_at DESC);

        ALTER TABLE suppliers
          DROP CONSTRAINT suppliers_platform_supplier_id_key,
          DROP CONSTRAINT suppliers_source_url_nonblank_check,
          DROP COLUMN source_url,
          DROP COLUMN name,
          ALTER COLUMN platform_supplier_id SET NOT NULL;
        ALTER TABLE suppliers RENAME COLUMN platform_supplier_id TO external_id;
        ALTER TABLE suppliers
          ADD CONSTRAINT suppliers_platform_external_id_key UNIQUE (platform, external_id);

        DROP INDEX entitlements_user_validity_idx;
        ALTER TABLE entitlements
          DROP CONSTRAINT entitlements_user_record_key,
          DROP CONSTRAINT entitlements_time_range_check,
          DROP CONSTRAINT entitlements_status_nonblank_check,
          DROP CONSTRAINT entitlements_source_nonblank_check,
          DROP CONSTRAINT entitlements_entitlement_nonblank_check,
          DROP COLUMN status,
          DROP COLUMN source;
        ALTER TABLE entitlements RENAME COLUMN expires_at TO valid_until;
        ALTER TABLE entitlements RENAME COLUMN starts_at TO valid_from;
        ALTER TABLE entitlements RENAME COLUMN entitlement TO plan_code;
        ALTER TABLE entitlements
          ADD CONSTRAINT entitlements_valid_range_check
            CHECK (valid_until IS NULL OR valid_until > valid_from),
          ADD CONSTRAINT entitlements_user_plan_start_key
            UNIQUE (user_id, plan_code, valid_from);
        CREATE INDEX entitlements_user_validity_idx
          ON entitlements (user_id, valid_from, valid_until);

        ALTER TABLE users
          DROP CONSTRAINT users_clerk_user_id_nonblank_check,
          DROP COLUMN email;
        """,
    )
]
