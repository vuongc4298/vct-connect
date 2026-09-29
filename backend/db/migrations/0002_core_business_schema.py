from yoyo import step


__depends__ = {"0001_tracer_baseline"}


# This revision was applied locally before the section 19 naming review. Keep it
# immutable; 0003 upgrades it to the canonical schema without rewriting history.
steps = [
    step(
        """
        CREATE TABLE users (
          id UUID PRIMARY KEY,
          clerk_user_id TEXT NOT NULL UNIQUE,
          role TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT users_role_check CHECK (role IN ('CUSTOMER', 'INTERNAL_REVIEWER', 'ADMIN'))
        );
        CREATE TABLE entitlements (
          id UUID PRIMARY KEY,
          user_id UUID NOT NULL REFERENCES users(id),
          plan_code TEXT NOT NULL,
          valid_from TIMESTAMPTZ NOT NULL,
          valid_until TIMESTAMPTZ,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT entitlements_valid_range_check CHECK (valid_until IS NULL OR valid_until > valid_from),
          CONSTRAINT entitlements_user_plan_start_key UNIQUE (user_id, plan_code, valid_from)
        );
        CREATE TABLE suppliers (
          id UUID PRIMARY KEY,
          platform TEXT NOT NULL,
          external_id TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT suppliers_platform_check CHECK (platform IN ('1688', 'TAOBAO', 'ALIBABA')),
          CONSTRAINT suppliers_platform_external_id_key UNIQUE (platform, external_id)
        );
        CREATE TABLE supplier_snapshots (
          id UUID PRIMARY KEY,
          supplier_id UUID NOT NULL REFERENCES suppliers(id),
          captured_at TIMESTAMPTZ NOT NULL,
          raw_document JSONB NOT NULL,
          normalized_document JSONB NOT NULL,
          completeness NUMERIC(5, 4) NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT supplier_snapshots_raw_object_check CHECK (jsonb_typeof(raw_document) = 'object'),
          CONSTRAINT supplier_snapshots_normalized_object_check CHECK (jsonb_typeof(normalized_document) = 'object'),
          CONSTRAINT supplier_snapshots_completeness_check CHECK (completeness >= 0 AND completeness <= 1),
          CONSTRAINT supplier_snapshots_supplier_capture_key UNIQUE (supplier_id, captured_at)
        );
        ALTER TABLE analyses
          ADD COLUMN user_id UUID REFERENCES users(id),
          ADD COLUMN supplier_snapshot_id UUID REFERENCES supplier_snapshots(id),
          ADD COLUMN mode TEXT,
          ADD COLUMN scoring_version TEXT;
        CREATE INDEX entitlements_user_validity_idx ON entitlements (user_id, valid_from, valid_until);
        CREATE INDEX supplier_snapshots_supplier_captured_idx ON supplier_snapshots (supplier_id, captured_at DESC);
        CREATE INDEX analyses_user_created_idx ON analyses (user_id, created_at DESC) WHERE user_id IS NOT NULL;
        CREATE INDEX analyses_supplier_snapshot_idx ON analyses (supplier_snapshot_id) WHERE supplier_snapshot_id IS NOT NULL;
        """,
        """
        DROP INDEX analyses_supplier_snapshot_idx;
        DROP INDEX analyses_user_created_idx;
        DROP INDEX supplier_snapshots_supplier_captured_idx;
        DROP INDEX entitlements_user_validity_idx;
        ALTER TABLE analyses
          DROP COLUMN scoring_version,
          DROP COLUMN mode,
          DROP COLUMN supplier_snapshot_id,
          DROP COLUMN user_id;
        DROP TABLE supplier_snapshots;
        DROP TABLE suppliers;
        DROP TABLE entitlements;
        DROP TABLE users;
        """,
    )
]
