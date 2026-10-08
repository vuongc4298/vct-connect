import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

import backend.app.migrations as migrations_module
from backend.app.fixture import FIXTURE_URL, fixture_result
from backend.app.migrations import (
    BaselineSchemaMismatch,
    apply_migrations,
    migration_status,
    rollback_core_migration,
)
from backend.app.storage import Store
from backend.worker.main import process_local_once


LEGACY_SCHEMA = """
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
"""


def _schema_url(database_url: str, schema: str) -> str:
    parsed = urlsplit(database_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    existing = query.get("options", "")
    query["options"] = f"{existing} -c search_path={schema}".strip()
    return urlunsplit(parsed._replace(query=urlencode(query, quote_via=quote)))


@pytest.fixture
def isolated_database_url():
    database_url = os.getenv("VCT_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set VCT_TEST_DATABASE_URL for PostgreSQL migration checks")
    schema = f"migration_test_{uuid4().hex}"
    with psycopg.connect(database_url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    try:
        yield _schema_url(database_url, schema)
    finally:
        with psycopg.connect(database_url, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def _create_legacy_schema(database_url: str) -> None:
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(LEGACY_SCHEMA)


def _apply_through(database_url: str, migration_id: str) -> None:
    backend = migrations_module.get_backend(migrations_module._yoyo_url(database_url))
    try:
        migrations = migrations_module.read_migrations(str(migrations_module.MIGRATIONS_DIR))
        pending = []
        for migration in backend.to_apply(migrations):
            pending.append(migration)
            if migration.id == migration_id:
                break
        with backend.lock():
            backend.apply_migrations_only(pending)
    finally:
        migrations_module._close_backend(backend)


def _rollback_post_core_revisions(database_url: str) -> None:
    backend = migrations_module.get_backend(migrations_module._yoyo_url(database_url))
    try:
        migrations = migrations_module.read_migrations(str(migrations_module.MIGRATIONS_DIR))
        with backend.lock():
            revisions = [migration for migration in backend.to_rollback(migrations)
                         if migration.id in {"0007_1688_extraction_evidence", "0008_allow_public_extraction",
                                             "0009_allow_snapshot_replay", "0010_llm_review_runs", "0011_worker_assessments", "0012_multimodal_assessments", "0013_reports", "0014_watchlist", "0015_review_evaluation_labels"}]
            backend.rollback_migrations(revisions)
    finally:
        migrations_module._close_backend(backend)


def _table_names(database_url: str) -> set[str]:
    with psycopg.connect(database_url) as conn:
        return {
            row[0]
            for row in conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = current_schema()"
            )
        }


def test_replay_migration_refuses_rollback_that_would_discard_preserved_captures(isolated_database_url):
    apply_migrations(isolated_database_url)
    supplier_id = uuid4()
    captured = datetime(2026, 9, 1, tzinfo=timezone.utc)
    with psycopg.connect(isolated_database_url) as conn:
        conn.execute("INSERT INTO suppliers (id, platform, source_url) VALUES (%s, '1688', %s)",
                     (supplier_id, FIXTURE_URL))
        for version in ("v1", "v2"):
            conn.execute(
                """INSERT INTO supplier_snapshots
                     (id, supplier_id, raw_payload, normalized_data, extraction_method,
                      analysis_mode, extractor_version, extracted_at)
                   VALUES (%s, %s, '{}'::jsonb, '{}'::jsonb, 'PUBLIC_HTTP',
                           'ACCOUNT_PUBLIC', %s, %s)""",
                (uuid4(), supplier_id, version, captured),
            )
    with pytest.raises(psycopg.errors.RaiseException, match="rollback cannot restore"):
        _rollback_post_core_revisions(isolated_database_url)
    assert dict(migration_status(isolated_database_url))["0009_allow_snapshot_replay"] is True
    with psycopg.connect(isolated_database_url) as conn:
        assert conn.execute("SELECT count(*) FROM supplier_snapshots WHERE supplier_id = %s", (supplier_id,)).fetchone()[0] == 2


def _analysis_columns(database_url: str) -> list[str]:
    with psycopg.connect(database_url) as conn:
        return [
            row[0]
            for row in conn.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'analyses'
                ORDER BY ordinal_position
                """
            )
        ]


def _seed_tracer_rows(database_url: str):
    completed_id, queued_id = uuid4(), uuid4()
    created_at = datetime(2026, 9, 27, 8, 15, tzinfo=timezone.utc)
    completed_at = created_at + timedelta(seconds=2)
    available_at = created_at + timedelta(minutes=3)
    claimed_until = created_at + timedelta(minutes=8)
    payload = {"fixture": True, "nested": {"source": "legacy"}}
    with psycopg.connect(database_url) as conn:
        conn.execute(
            """
            INSERT INTO analyses (id, source_url, status, created_at, completed_at)
            VALUES (%s, %s, 'COMPLETED', %s, %s),
                   (%s, %s, 'QUEUED', %s, NULL)
            """,
            (
                completed_id,
                FIXTURE_URL,
                created_at,
                completed_at,
                queued_id,
                FIXTURE_URL,
                created_at + timedelta(minutes=1),
            ),
        )
        conn.execute(
            "INSERT INTO analysis_results (analysis_id, payload, created_at) "
            "VALUES (%s, %s::jsonb, %s)",
            (completed_id, json.dumps(payload), completed_at),
        )
        conn.execute(
            """
            INSERT INTO local_queue
              (analysis_id, available_at, claimed_until, attempts)
            VALUES (%s, %s, %s, 3)
            """,
            (queued_id, available_at, claimed_until),
        )
    return completed_id, queued_id


def _tracer_snapshot(database_url: str):
    with psycopg.connect(database_url) as conn:
        analyses = conn.execute(
            "SELECT id, source_url, status, created_at, completed_at "
            "FROM analyses ORDER BY id"
        ).fetchall()
        results = conn.execute(
            "SELECT analysis_id, payload, created_at FROM analysis_results ORDER BY analysis_id"
        ).fetchall()
        queue = conn.execute(
            """
            SELECT analysis_id, available_at, claimed_until, attempts
            FROM local_queue ORDER BY analysis_id
            """
        ).fetchall()
    return analyses, results, queue


def test_fresh_apply_failure_rollback_and_reapply_are_reproducible(
    isolated_database_url,
):
    with psycopg.connect(isolated_database_url, autocommit=True) as conn:
        conn.execute("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE INDEX entitlements_user_validity_idx ON unrelated (id)")

    with pytest.raises(psycopg.errors.DuplicateTable):
        apply_migrations(isolated_database_url)

    tables = _table_names(isolated_database_url)
    assert {"analyses", "analysis_results", "local_queue"} <= tables
    assert not ({"users", "entitlements", "suppliers", "supplier_snapshots"} & tables)
    assert migration_status(isolated_database_url) == [
        ("0001_tracer_baseline", True),
        ("0002_core_business_schema", False),
        ("0003_align_core_schema_to_spec", False),
        ("0004_harden_analysis_processing", False),
        ("0005_expand_processing_dispositions", False),
        ("0006_guest_admission_and_provenance", False),
        ("0007_1688_extraction_evidence", False),
        ("0008_allow_public_extraction", False),
        ("0009_allow_snapshot_replay", False),
        ("0010_llm_review_runs", False),
        ("0011_worker_assessments", False),
        ("0012_multimodal_assessments", False),
        ("0013_reports", False),
        ("0014_watchlist", False),
        ("0015_review_evaluation_labels", False),
    ]

    with psycopg.connect(isolated_database_url, autocommit=True) as conn:
        conn.execute("DROP TABLE unrelated")
    apply_migrations(isolated_database_url)
    apply_migrations(isolated_database_url)
    assert migration_status(isolated_database_url) == [
        ("0001_tracer_baseline", True),
        ("0002_core_business_schema", True),
        ("0003_align_core_schema_to_spec", True),
        ("0004_harden_analysis_processing", True),
        ("0005_expand_processing_dispositions", True),
        ("0006_guest_admission_and_provenance", True),
        ("0007_1688_extraction_evidence", True),
        ("0008_allow_public_extraction", True),
        ("0009_allow_snapshot_replay", True),
        ("0010_llm_review_runs", True),
        ("0011_worker_assessments", True),
        ("0012_multimodal_assessments", True),
        ("0013_reports", True),
        ("0014_watchlist", True),
        ("0015_review_evaluation_labels", True),
    ]


def test_populated_legacy_schema_and_active_queue_are_preserved(isolated_database_url):
    _create_legacy_schema(isolated_database_url)
    completed_id, queued_id = _seed_tracer_rows(isolated_database_url)
    before = _tracer_snapshot(isolated_database_url)

    apply_migrations(isolated_database_url)

    assert _tracer_snapshot(isolated_database_url) == before
    with psycopg.connect(isolated_database_url) as conn:
        guest_rows = conn.execute(
            """
            SELECT user_id, supplier_snapshot_id, mode, scoring_version
            FROM analyses WHERE id = ANY(%s) ORDER BY id
            """,
            ([completed_id, queued_id],),
        ).fetchall()
    assert guest_rows == [
        (None, None, "GUEST_PUBLIC", "v0.1.0"),
        (None, None, "GUEST_PUBLIC", "v0.1.0"),
    ]


def test_snapshot_linked_historical_analysis_keeps_extraction_method(isolated_database_url):
    _apply_through(isolated_database_url, "0005_expand_processing_dispositions")
    supplier_id, snapshot_id, analysis_id = uuid4(), uuid4(), uuid4()
    with psycopg.connect(isolated_database_url) as conn:
        conn.execute(
            "INSERT INTO suppliers (id, platform, source_url) VALUES (%s, '1688', %s)",
            (supplier_id, FIXTURE_URL),
        )
        conn.execute(
            """INSERT INTO supplier_snapshots
                 (id, supplier_id, raw_payload, normalized_data, extraction_method,
                  analysis_mode, extractor_version, extracted_at)
               VALUES (%s, %s, '{}'::jsonb, '{}'::jsonb, 'HTTP',
                       'ACCOUNT_PUBLIC', 'prior', now())""",
            (snapshot_id, supplier_id),
        )
        conn.execute(
            """INSERT INTO analyses (id, source_url, status, supplier_snapshot_id, mode)
               VALUES (%s, %s, 'QUEUED', %s, 'ACCOUNT_PUBLIC')""",
            (analysis_id, FIXTURE_URL, snapshot_id),
        )
    apply_migrations(isolated_database_url)
    with psycopg.connect(isolated_database_url) as conn:
        row = conn.execute(
            "SELECT extraction_method, mode FROM analyses WHERE id = %s",
            (analysis_id,),
        ).fetchone()
    assert row == ("HTTP", "ACCOUNT_PUBLIC")


def test_processing_hardening_schema_is_reversible_and_preserves_claims(isolated_database_url):
    _create_legacy_schema(isolated_database_url)
    completed_id, queued_id = _seed_tracer_rows(isolated_database_url)
    created_id = uuid4()
    with psycopg.connect(isolated_database_url) as conn:
        conn.execute(
            "INSERT INTO analyses (id, source_url, status) VALUES (%s, %s, 'CREATED')",
            (created_id, FIXTURE_URL),
        )
    apply_migrations(isolated_database_url)

    assert {"analysis_status_events", "analysis_outbox"} <= _table_names(isolated_database_url)
    assert {
        "attempt_count", "processing_claim_token", "processing_claimed_until",
        "failure_code", "next_retry_at", "final_disposition",
    } <= set(_analysis_columns(isolated_database_url))
    with psycopg.connect(isolated_database_url) as conn:
        claim = conn.execute(
            "SELECT claim_token, claimed_until, attempts FROM local_queue WHERE analysis_id = %s",
            (queued_id,),
        ).fetchone()
        events = conn.execute(
            "SELECT analysis_id, status FROM analysis_status_events ORDER BY analysis_id"
        ).fetchall()
        migrated_outbox = conn.execute(
            "SELECT message_id, state FROM analysis_outbox WHERE analysis_id = %s",
            (created_id,),
        ).fetchone()
    assert claim[0] is not None
    assert claim[1] is not None
    assert claim[2] == 3
    assert events == sorted([
        (completed_id, "COMPLETED"), (queued_id, "QUEUED"), (created_id, "QUEUED")
    ])
    assert migrated_outbox == (created_id, "PENDING")

    with pytest.raises(RuntimeError, match="0013_reports"):
        rollback_core_migration(isolated_database_url)
    _rollback_post_core_revisions(isolated_database_url)
    assert rollback_core_migration(isolated_database_url)
    assert _analysis_columns(isolated_database_url) == [
        "id", "source_url", "status", "created_at", "completed_at"
    ]
    assert not ({"analysis_status_events", "analysis_outbox"} & _table_names(isolated_database_url))


@pytest.mark.parametrize(
    "mutation, expected_message",
    [
        (
            "ALTER TABLE local_queue ALTER COLUMN attempts SET DEFAULT 1",
            "local_queue.attempts properties differ",
        ),
        (
            "ALTER TABLE local_queue ALTER COLUMN attempts DROP NOT NULL",
            "local_queue.attempts properties differ",
        ),
        (
            "ALTER TABLE local_queue ALTER COLUMN attempts TYPE BIGINT",
            "local_queue.attempts properties differ",
        ),
        (
            "ALTER TABLE local_queue DROP CONSTRAINT local_queue_pkey",
            "local_queue primary keys differ",
        ),
        (
            "ALTER TABLE local_queue DROP CONSTRAINT local_queue_analysis_id_fkey",
            "local_queue foreign keys differ",
        ),
        (
            """
            ALTER TABLE analyses DROP CONSTRAINT analyses_status_check;
            ALTER TABLE analyses ADD CONSTRAINT analyses_status_check
              CHECK (status IN ('created', 'queued', 'completed'))
            """,
            "analyses checks differ",
        ),
        (
            "CREATE UNIQUE INDEX analyses_source_url_unique ON analyses (source_url)",
            "analyses indexes differ",
        ),
        (
            """
            ALTER TABLE local_queue DROP CONSTRAINT local_queue_pkey;
            ALTER TABLE local_queue ADD CONSTRAINT local_queue_pkey
              PRIMARY KEY (analysis_id) DEFERRABLE INITIALLY DEFERRED
            """,
            "local_queue primary keys differ",
        ),
    ],
)
def test_altered_legacy_schema_is_rejected_before_core_changes(
    isolated_database_url, mutation, expected_message
):
    _create_legacy_schema(isolated_database_url)
    with psycopg.connect(isolated_database_url, autocommit=True) as conn:
        conn.execute(mutation)

    with pytest.raises(BaselineSchemaMismatch, match=expected_message):
        apply_migrations(isolated_database_url)

    assert "users" not in _table_names(isolated_database_url)
    assert _analysis_columns(isolated_database_url) == [
        "id",
        "source_url",
        "status",
        "created_at",
        "completed_at",
    ]


def test_adoption_rejects_unmanaged_core_tables_before_marking_baseline(
    isolated_database_url,
):
    _create_legacy_schema(isolated_database_url)
    with psycopg.connect(isolated_database_url, autocommit=True) as conn:
        conn.execute("CREATE TABLE users (id UUID PRIMARY KEY)")

    with pytest.raises(BaselineSchemaMismatch, match="managed tables differ"):
        apply_migrations(isolated_database_url)

    assert "_yoyo_migration" not in _table_names(isolated_database_url)


def test_alignment_refuses_populated_provisional_core_schema(isolated_database_url):
    _apply_through(isolated_database_url, "0002_core_business_schema")
    user_id, entitlement_id = uuid4(), uuid4()
    with psycopg.connect(isolated_database_url) as conn:
        conn.execute(
            "INSERT INTO users (id, clerk_user_id, role) VALUES (%s, 'provisional', 'CUSTOMER')",
            (user_id,),
        )
        conn.execute(
            """
            INSERT INTO entitlements (id, user_id, plan_code, valid_from)
            VALUES (%s, %s, 'PILOT', now())
            """,
            (entitlement_id, user_id),
        )

    with pytest.raises(psycopg.errors.RaiseException, match="map them explicitly first"):
        apply_migrations(isolated_database_url)

    assert dict(migration_status(isolated_database_url))["0003_align_core_schema_to_spec"] is False
    with psycopg.connect(isolated_database_url) as conn:
        assert conn.execute("SELECT plan_code FROM entitlements").fetchone()[0] == "PILOT"


def test_core_schema_constraints_indexes_and_representative_join(isolated_database_url):
    apply_migrations(isolated_database_url)
    user_id, entitlement_id = uuid4(), uuid4()
    supplier_id, snapshot_id, analysis_id = uuid4(), uuid4(), uuid4()
    analyzed_at = datetime(2026, 9, 27, 9, 0, tzinfo=timezone.utc)
    raw_payload = {"source": "fixture", "listing": {"id": "123456789012"}}
    normalized_data = {"supplier": {"name": "Fixture supplier"}}

    with psycopg.connect(isolated_database_url, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO users (id, clerk_user_id, email, role) "
            "VALUES (%s, 'user_fixture', 'customer@example.test', 'CUSTOMER')",
            (user_id,),
        )
        conn.execute(
            """
            INSERT INTO entitlements
              (id, user_id, entitlement, source, starts_at, expires_at, status)
            VALUES (%s, %s, 'ANALYSIS_ACCESS', 'MVP_TRIAL', %s, %s, 'ACTIVE')
            """,
            (
                entitlement_id,
                user_id,
                analyzed_at - timedelta(days=1),
                analyzed_at + timedelta(days=1),
            ),
        )
        conn.execute(
            """
            INSERT INTO suppliers
              (id, platform, platform_supplier_id, name, source_url)
            VALUES (%s, '1688', 'supplier-123', 'Fixture supplier', %s)
            """,
            (supplier_id, FIXTURE_URL),
        )
        conn.execute(
            """
            INSERT INTO supplier_snapshots
              (id, supplier_id, raw_payload, normalized_data, extraction_method,
               analysis_mode, completeness, extractor_version, extracted_at)
            VALUES (%s, %s, %s::jsonb, %s::jsonb, 'FIXTURE', 'GUEST_PUBLIC',
                    0.8750, 'v1', %s)
            """,
            (
                snapshot_id,
                supplier_id,
                json.dumps(raw_payload),
                json.dumps(normalized_data),
                analyzed_at - timedelta(minutes=5),
            ),
        )
        conn.execute(
            """
            INSERT INTO analyses
              (id, source_url, status, created_at, user_id, supplier_snapshot_id,
               mode, scoring_version)
            VALUES (%s, %s, 'QUEUED', %s, %s, %s, 'ACCOUNT_PUBLIC', 'v1')
            """,
            (analysis_id, FIXTURE_URL, analyzed_at, user_id, snapshot_id),
        )
        joined = conn.execute(
            """
            SELECT a.id, u.clerk_user_id, e.entitlement, e.source, s.platform,
                   s.platform_supplier_id, ss.raw_payload, ss.normalized_data
            FROM analyses a
            JOIN users u ON u.id = a.user_id
            JOIN entitlements e ON e.user_id = u.id
              AND e.starts_at <= a.created_at
              AND (e.expires_at IS NULL OR e.expires_at > a.created_at)
            JOIN supplier_snapshots ss ON ss.id = a.supplier_snapshot_id
            JOIN suppliers s ON s.id = ss.supplier_id
            WHERE a.id = %s
            """,
            (analysis_id,),
        ).fetchone()
        assert joined == (
            analysis_id,
            "user_fixture",
            "ANALYSIS_ACCESS",
            "MVP_TRIAL",
            "1688",
            "supplier-123",
            raw_payload,
            normalized_data,
        )

        # A revised snapshot retains the capture time and belongs to a new
        # analysis; the analysis association remains unique.
        conn.execute(
            """INSERT INTO supplier_snapshots
                 (id, supplier_id, analysis_id, raw_payload, normalized_data,
                  extraction_method, analysis_mode, extractor_version, extracted_at)
               VALUES (%s, %s, %s, '{}'::jsonb, '{}'::jsonb,
                       'PUBLIC_HTTP', 'ACCOUNT_PUBLIC', 'v2', %s)""",
            (uuid4(), supplier_id, analysis_id, analyzed_at - timedelta(minutes=5)),
        )

        invalid_statements = [
            (
                "INSERT INTO users (id, clerk_user_id, role) "
                "VALUES (%s, '   ', 'CUSTOMER')",
                (uuid4(),),
            ),
            (
                "INSERT INTO users (id, clerk_user_id, role) "
                "VALUES (%s, 'bad-role', 'OWNER')",
                (uuid4(),),
            ),
            (
                "INSERT INTO users (id, clerk_user_id, role) "
                "VALUES (%s, 'user_fixture', 'CUSTOMER')",
                (uuid4(),),
            ),
            (
                "INSERT INTO entitlements "
                "(id, user_id, entitlement, source, starts_at, status) "
                "VALUES (%s, %s, '', 'MVP_TRIAL', %s, 'ACTIVE')",
                (uuid4(), user_id, analyzed_at),
            ),
            (
                "INSERT INTO entitlements "
                "(id, user_id, entitlement, source, starts_at, status) "
                "VALUES (%s, %s, 'ACCESS', '', %s, 'ACTIVE')",
                (uuid4(), user_id, analyzed_at + timedelta(seconds=1)),
            ),
            (
                "INSERT INTO entitlements "
                "(id, user_id, entitlement, source, starts_at, status) "
                "VALUES (%s, %s, 'ACCESS', 'MVP_TRIAL', %s, '   ')",
                (uuid4(), user_id, analyzed_at + timedelta(seconds=2)),
            ),
            (
                "INSERT INTO entitlements "
                "(id, user_id, entitlement, source, starts_at, expires_at, status) "
                "VALUES (%s, %s, 'ACCESS', 'MVP_TRIAL', %s, %s, 'ACTIVE')",
                (uuid4(), user_id, analyzed_at, analyzed_at),
            ),
            (
                "INSERT INTO entitlements "
                "(id, user_id, entitlement, source, starts_at, status) "
                "VALUES (%s, %s, 'ACCESS', 'MVP_TRIAL', %s, 'ACTIVE')",
                (uuid4(), uuid4(), analyzed_at),
            ),
            (
                "INSERT INTO entitlements "
                "(id, user_id, entitlement, source, starts_at, expires_at, status) "
                "VALUES (%s, %s, 'ANALYSIS_ACCESS', 'MVP_TRIAL', %s, %s, 'ACTIVE')",
                (
                    uuid4(),
                    user_id,
                    analyzed_at - timedelta(days=1),
                    analyzed_at + timedelta(days=2),
                ),
            ),
            (
                "INSERT INTO suppliers "
                "(id, platform, platform_supplier_id, source_url) "
                "VALUES (%s, 'EBAY', 'bad', %s)",
                (uuid4(), FIXTURE_URL),
            ),
            (
                "INSERT INTO suppliers "
                "(id, platform, platform_supplier_id, source_url) "
                "VALUES (%s, '1688', 'other', '   ')",
                (uuid4(),),
            ),
            (
                "INSERT INTO suppliers "
                "(id, platform, platform_supplier_id, source_url) "
                "VALUES (%s, '1688', 'supplier-123', %s)",
                (uuid4(), FIXTURE_URL),
            ),
            (
                "INSERT INTO supplier_snapshots "
                "(id, supplier_id, raw_payload, normalized_data, extraction_method, "
                "analysis_mode, extractor_version, extracted_at) "
                "VALUES (%s, %s, '[]'::jsonb, '{}'::jsonb, 'FIXTURE', "
                "'GUEST_PUBLIC', 'v1', %s)",
                (uuid4(), supplier_id, analyzed_at),
            ),
            (
                "INSERT INTO supplier_snapshots "
                "(id, supplier_id, raw_payload, normalized_data, extraction_method, "
                "analysis_mode, extractor_version, extracted_at) "
                "VALUES (%s, %s, '{}'::jsonb, '[]'::jsonb, 'FIXTURE', "
                "'GUEST_PUBLIC', 'v1', %s)",
                (uuid4(), supplier_id, analyzed_at + timedelta(seconds=2)),
            ),
            (
                "INSERT INTO supplier_snapshots "
                "(id, supplier_id, raw_payload, normalized_data, extraction_method, "
                "analysis_mode, extractor_version, extracted_at) "
                "VALUES (%s, %s, '{}'::jsonb, '{}'::jsonb, '', "
                "'GUEST_PUBLIC', 'v1', %s)",
                (uuid4(), supplier_id, analyzed_at + timedelta(seconds=3)),
            ),
            (
                "INSERT INTO supplier_snapshots "
                "(id, supplier_id, raw_payload, normalized_data, extraction_method, "
                "analysis_mode, extractor_version, extracted_at) "
                "VALUES (%s, %s, '{}'::jsonb, '{}'::jsonb, 'FIXTURE', "
                "' ', 'v1', %s)",
                (uuid4(), supplier_id, analyzed_at + timedelta(seconds=4)),
            ),
            (
                "INSERT INTO supplier_snapshots "
                "(id, supplier_id, raw_payload, normalized_data, extraction_method, "
                "analysis_mode, extractor_version, extracted_at) "
                "VALUES (%s, %s, '{}'::jsonb, '{}'::jsonb, 'FIXTURE', "
                "'GUEST_PUBLIC', '', %s)",
                (uuid4(), supplier_id, analyzed_at + timedelta(seconds=5)),
            ),
            (
                "INSERT INTO supplier_snapshots "
                "(id, supplier_id, raw_payload, normalized_data, extraction_method, "
                "analysis_mode, completeness, extractor_version, extracted_at) "
                "VALUES (%s, %s, '{}'::jsonb, '{}'::jsonb, 'FIXTURE', "
                "'GUEST_PUBLIC', 1.1, 'v1', %s)",
                (uuid4(), supplier_id, analyzed_at + timedelta(seconds=1)),
            ),
            (
                "INSERT INTO supplier_snapshots "
                "(id, supplier_id, raw_payload, normalized_data, extraction_method, "
                "analysis_mode, extractor_version, extracted_at) "
                "VALUES (%s, %s, '{}'::jsonb, '{}'::jsonb, 'FIXTURE', "
                "'GUEST_PUBLIC', 'v1', %s)",
                (uuid4(), uuid4(), analyzed_at + timedelta(seconds=6)),
            ),
            (
                "INSERT INTO supplier_snapshots "
                "(id, supplier_id, analysis_id, raw_payload, normalized_data, extraction_method, "
                "analysis_mode, extractor_version, extracted_at) "
                "VALUES (%s, %s, %s, '{}'::jsonb, '{}'::jsonb, 'FIXTURE', "
                "'GUEST_PUBLIC', 'v1', %s)",
                (uuid4(), supplier_id, analysis_id, analyzed_at),
            ),
            (
                "INSERT INTO analyses (id, source_url, status, user_id) "
                "VALUES (%s, %s, 'QUEUED', %s)",
                (uuid4(), FIXTURE_URL, uuid4()),
            ),
            (
                "INSERT INTO analyses (id, source_url, status, supplier_snapshot_id) "
                "VALUES (%s, %s, 'QUEUED', %s)",
                (uuid4(), FIXTURE_URL, uuid4()),
            ),
        ]
        for statement, parameters in invalid_statements:
            with pytest.raises(psycopg.IntegrityError):
                conn.execute(statement, parameters)

        index_rows = conn.execute(
            """
            SELECT indexname, indexdef FROM pg_indexes
            WHERE schemaname = current_schema()
            """
        ).fetchall()
        index_definitions = {
            name: " ".join(definition.lower().split()) for name, definition in index_rows
        }
        assert "(user_id, starts_at, expires_at)" in index_definitions[
            "entitlements_user_validity_idx"
        ]
        assert "(supplier_id, extracted_at desc)" in index_definitions[
            "supplier_snapshots_supplier_extracted_idx"
        ]
        assert "(user_id, created_at desc) where (user_id is not null)" in index_definitions[
            "analyses_user_created_idx"
        ]
        assert "(supplier_snapshot_id) where (supplier_snapshot_id is not null)" in index_definitions[
            "analyses_supplier_snapshot_idx"
        ]

    with psycopg.connect(isolated_database_url) as conn:
        core_columns = {
            table: {
                row[0]
                for row in conn.execute(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = current_schema() AND table_name = %s
                    """,
                    (table,),
                )
            }
            for table in ("users", "entitlements", "suppliers", "supplier_snapshots")
        }
        column_contract = {
            (table, column): (data_type, nullable == "YES")
            for table, column, data_type, nullable in conn.execute(
                """
                SELECT table_name, column_name, udt_name, is_nullable
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = ANY(%s)
                """,
                (["users", "entitlements", "suppliers", "supplier_snapshots"],),
            )
        }
    assert {"id", "clerk_user_id", "email", "role", "created_at"} <= core_columns["users"]
    assert {"id", "user_id", "entitlement", "source", "starts_at", "expires_at", "status"} <= core_columns["entitlements"]
    assert {"id", "platform", "platform_supplier_id", "name", "source_url"} <= core_columns["suppliers"]
    assert {"id", "supplier_id", "raw_payload", "normalized_data", "extraction_method", "analysis_mode", "completeness", "extractor_version", "extracted_at"} <= core_columns["supplier_snapshots"]
    assert not ({"plan_code", "valid_from", "valid_until"} & core_columns["entitlements"])
    assert not ({"external_id"} & core_columns["suppliers"])
    assert not ({"raw_document", "normalized_document", "captured_at"} & core_columns["supplier_snapshots"])
    assert column_contract[("users", "email")] == ("text", True)
    assert column_contract[("suppliers", "platform_supplier_id")] == ("text", True)
    assert column_contract[("suppliers", "name")] == ("text", True)
    assert column_contract[("supplier_snapshots", "completeness")] == ("numeric", True)
    assert column_contract[("supplier_snapshots", "raw_payload")] == ("jsonb", False)
    assert column_contract[("entitlements", "starts_at")] == ("timestamptz", False)


def test_core_schema_accepts_nullable_canonical_fields(isolated_database_url):
    apply_migrations(isolated_database_url)
    user_id, supplier_id, snapshot_id = uuid4(), uuid4(), uuid4()
    with psycopg.connect(isolated_database_url) as conn:
        conn.execute(
            "INSERT INTO users (id, clerk_user_id, role) "
            "VALUES (%s, 'nullable-user', 'CUSTOMER')",
            (user_id,),
        )
        conn.execute(
            "INSERT INTO suppliers (id, platform, source_url) "
            "VALUES (%s, '1688', %s)",
            (supplier_id, FIXTURE_URL),
        )
        conn.execute(
            """
            INSERT INTO supplier_snapshots
              (id, supplier_id, raw_payload, normalized_data, extraction_method,
               analysis_mode, extractor_version, extracted_at)
            VALUES (%s, %s, '{}'::jsonb, '{}'::jsonb, 'FIXTURE',
                    'GUEST_PUBLIC', 'v1', now())
            """,
            (snapshot_id, supplier_id),
        )
        assert conn.execute(
            "SELECT email FROM users WHERE id = %s", (user_id,)
        ).fetchone() == (None,)
        assert conn.execute(
            "SELECT platform_supplier_id, name FROM suppliers WHERE id = %s",
            (supplier_id,),
        ).fetchone() == (None, None)
        assert conn.execute(
            "SELECT completeness FROM supplier_snapshots WHERE id = %s",
            (snapshot_id,),
        ).fetchone() == (None,)


def test_core_rollback_preserves_tracer_drops_columns_and_reapplies(isolated_database_url):
    _create_legacy_schema(isolated_database_url)
    completed_id, _ = _seed_tracer_rows(isolated_database_url)
    before = _tracer_snapshot(isolated_database_url)
    apply_migrations(isolated_database_url)

    user_id, supplier_id, snapshot_id = uuid4(), uuid4(), uuid4()
    starts_at = datetime(2026, 9, 26, 8, 15, tzinfo=timezone.utc)
    with psycopg.connect(isolated_database_url) as conn:
        conn.execute(
            "INSERT INTO users (id, clerk_user_id, role) "
            "VALUES (%s, 'rollback-user', 'CUSTOMER')",
            (user_id,),
        )
        for source in ("MVP_TRIAL", "ADMIN_GRANT"):
            conn.execute(
                """
                INSERT INTO entitlements
                  (id, user_id, entitlement, source, starts_at, status)
                VALUES (%s, %s, 'ANALYSIS_ACCESS', %s, %s, 'ACTIVE')
                """,
                (uuid4(), user_id, source, starts_at),
            )
        conn.execute(
            "INSERT INTO suppliers (id, platform, source_url) "
            "VALUES (%s, '1688', %s)",
            (supplier_id, FIXTURE_URL),
        )
        conn.execute(
            """
            INSERT INTO supplier_snapshots
              (id, supplier_id, raw_payload, normalized_data, extraction_method,
               analysis_mode, extractor_version, extracted_at)
            VALUES (%s, %s, '{}'::jsonb, '{}'::jsonb, 'FIXTURE',
                    'GUEST_PUBLIC', 'v1', now())
            """,
            (snapshot_id, supplier_id),
        )
        conn.execute(
            "UPDATE analyses SET user_id = %s, supplier_snapshot_id = %s WHERE id = %s",
            (user_id, snapshot_id, completed_id),
        )

    with pytest.raises(RuntimeError, match="0013_reports"):
        rollback_core_migration(isolated_database_url)
    _rollback_post_core_revisions(isolated_database_url)
    assert rollback_core_migration(isolated_database_url)
    assert not rollback_core_migration(isolated_database_url)
    assert _tracer_snapshot(isolated_database_url) == before
    assert _analysis_columns(isolated_database_url) == [
        "id",
        "source_url",
        "status",
        "created_at",
        "completed_at",
    ]
    assert not (
        {"users", "entitlements", "suppliers", "supplier_snapshots"}
        & _table_names(isolated_database_url)
    )

    apply_migrations(isolated_database_url)
    store = Store(isolated_database_url)
    analysis_id = store.submit_local(FIXTURE_URL)
    for _ in range(3):
        if store.get(analysis_id)["status"] == "COMPLETED":
            break
        assert process_local_once(store)
    assert store.get(analysis_id)["result"] == fixture_result(FIXTURE_URL)

    apply_migrations(isolated_database_url)
    assert migration_status(isolated_database_url)[-1] == (
        "0014_watchlist",
        True,
    )
    assert {"user_id", "supplier_snapshot_id", "mode", "scoring_version"} <= set(
        _analysis_columns(isolated_database_url)
    )


def test_core_rollback_refuses_applied_dependent_revision(monkeypatch):
    baseline = SimpleNamespace(id="0001_tracer_baseline")
    core = SimpleNamespace(id="0002_core_business_schema")
    alignment = SimpleNamespace(id="0003_align_core_schema_to_spec")
    later = SimpleNamespace(id="0004_later_story")

    class FakeBackend:
        connection = None

        @contextmanager
        def lock(self):
            yield

        def is_applied(self, migration):
            return migration is core or migration is alignment

        def to_rollback(self, migrations):
            return [later, alignment, core, baseline]

        def rollback_migrations(self, migrations):
            raise AssertionError("rollback must not run with an applied dependent revision")

    monkeypatch.setattr(migrations_module, "get_backend", lambda _: FakeBackend())
    monkeypatch.setattr(
        migrations_module,
        "read_migrations",
        lambda _: [baseline, core, alignment, later],
    )
    with pytest.raises(RuntimeError, match="0004_later_story"):
        rollback_core_migration("postgresql://example.invalid/vct")


def test_cli_requires_explicit_rollback_confirmation(monkeypatch):
    called = False

    def unexpected(_):
        nonlocal called
        called = True

    monkeypatch.setattr(migrations_module, "rollback_core_migration", unexpected)
    with pytest.raises(SystemExit) as error:
        migrations_module.main(["rollback-core"])
    assert error.value.code == 2
    assert not called


def test_cli_confirmed_rollback_uses_only_database_url(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://db-only.example/vct")
    monkeypatch.delenv("DEVELOPER_MODE", raising=False)
    monkeypatch.delenv("AZURE_SERVICE_BUS_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("AZURE_SERVICE_BUS_QUEUE", raising=False)
    seen = []
    monkeypatch.setattr(
        migrations_module,
        "rollback_core_migration",
        lambda database_url: seen.append(database_url) or True,
    )

    migrations_module.main(["rollback-core", "--confirm-isolated-database"])

    assert seen == ["postgresql://db-only.example/vct"]
    assert capsys.readouterr().out.strip() == "rolled back"


def test_database_url_forms_are_normalized_for_each_driver(isolated_database_url):
    value = "postgresql+psycopg://user:pass@example.test/vct?sslmode=require"
    assert migrations_module.psycopg_url(value).startswith("postgresql://")
    assert migrations_module._yoyo_url(value) == value

    plus_url = isolated_database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    store = Store(plus_url)
    store.initialize()
    with store.connect() as conn:
        assert conn.execute("SELECT current_schema()").fetchone()["current_schema"]
