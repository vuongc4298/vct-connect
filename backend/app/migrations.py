from __future__ import annotations

import argparse
import os
import re
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
from yoyo import get_backend, read_migrations


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "db" / "migrations"
BASELINE_ID = "0001_tracer_baseline"
CORE_IDS = {
    "0002_core_business_schema",
    "0003_align_core_schema_to_spec",
    "0004_harden_analysis_processing",
    "0005_expand_processing_dispositions",
    "0006_guest_admission_and_provenance",
}


class BaselineSchemaMismatch(RuntimeError):
    """The pre-migration tracer schema does not match the adopted baseline."""


_EXPECTED_COLUMNS = {
    "analyses": {
        "id": ("uuid", False, None),
        "source_url": ("text", False, None),
        "status": ("text", False, None),
        "created_at": ("timestamptz", False, "now"),
        "completed_at": ("timestamptz", True, None),
    },
    "analysis_results": {
        "analysis_id": ("uuid", False, None),
        "payload": ("jsonb", False, None),
        "created_at": ("timestamptz", False, "now"),
    },
    "local_queue": {
        "analysis_id": ("uuid", False, None),
        "available_at": ("timestamptz", False, "now"),
        "claimed_until": ("timestamptz", True, None),
        "attempts": ("int4", False, "zero"),
    },
}

_EXPECTED_CONSTRAINTS = {
    "analyses": {
        "primary_keys": {(('id',), False, False)},
        "foreign_keys": set(),
        "checks": {
            "CHECK(status=ANY(ARRAY['CREATED'::text,'QUEUED'::text,'COMPLETED'::text]))"
        },
    },
    "analysis_results": {
        "primary_keys": {(('analysis_id',), False, False)},
        "foreign_keys": {
            (("analysis_id",), "analyses", ("id",), "a", "a", "s", False, False)
        },
        "checks": set(),
    },
    "local_queue": {
        "primary_keys": {(('analysis_id',), False, False)},
        "foreign_keys": {
            (("analysis_id",), "analyses", ("id",), "a", "a", "s", False, False)
        },
        "checks": set(),
    },
}

_EXPECTED_INDEXES = {
    "analyses": {("analyses_pkey", True, True, ("id",), None)},
    "analysis_results": {
        ("analysis_results_pkey", True, True, ("analysis_id",), None)
    },
    "local_queue": {("local_queue_pkey", True, True, ("analysis_id",), None)},
}


def _yoyo_url(database_url: str) -> str:
    parsed = urlsplit(database_url)
    if parsed.scheme in {"postgres", "postgresql"}:
        parsed = parsed._replace(scheme="postgresql+psycopg")
    if parsed.scheme != "postgresql+psycopg":
        raise ValueError("Migrations require a PostgreSQL psycopg database URL")
    return urlunsplit(parsed)


def psycopg_url(database_url: str) -> str:
    parsed = urlsplit(database_url)
    if parsed.scheme in {"postgres", "postgresql+psycopg"}:
        parsed = parsed._replace(scheme="postgresql")
    if parsed.scheme != "postgresql":
        raise ValueError("Migrations require a PostgreSQL psycopg database URL")
    return urlunsplit(parsed)


def _default_kind(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", "", value.lower())
    if normalized in {"now()", "current_timestamp"}:
        return "now"
    if normalized in {"0", "0::integer"}:
        return "zero"
    return normalized


def _compact_sql(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _column_description(value: tuple[str, bool, str | None] | None) -> str:
    if value is None:
        return "missing"
    column_type, nullable, default = value
    return f"type={column_type}, nullable={nullable}, default={default!r}"


def validate_tracer_baseline(conn: psycopg.Connection) -> None:
    rows = conn.execute(
        """
        SELECT table_name, column_name, udt_name, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = ANY(%s)
        ORDER BY table_name, ordinal_position
        """,
        (list(_EXPECTED_COLUMNS),),
    ).fetchall()
    actual_columns: dict[str, dict[str, tuple[str, bool, str | None]]] = {
        table: {} for table in _EXPECTED_COLUMNS
    }
    for table, column, udt_name, nullable, default in rows:
        actual_columns[table][column] = (
            udt_name,
            nullable == "YES",
            _default_kind(default),
        )

    errors = []
    for table, expected in _EXPECTED_COLUMNS.items():
        actual = actual_columns[table]
        for column in sorted(expected.keys() | actual.keys()):
            if expected.get(column) != actual.get(column):
                errors.append(
                    f"{table}.{column} properties differ "
                    f"(expected {_column_description(expected.get(column))}; "
                    f"found {_column_description(actual.get(column))})"
                )

    constraint_rows = conn.execute(
        """
        SELECT relation.relname,
               constraint_row.contype,
               pg_get_constraintdef(constraint_row.oid, true),
               referenced_relation.relname,
               referenced_namespace.nspname,
               constraint_row.confupdtype,
               constraint_row.confdeltype,
               constraint_row.confmatchtype,
               constraint_row.condeferrable,
               constraint_row.condeferred,
               constraint_row.convalidated,
               ARRAY(
                 SELECT attribute.attname
                 FROM unnest(constraint_row.conkey) WITH ORDINALITY AS key(attnum, position)
                 JOIN pg_attribute AS attribute
                   ON attribute.attrelid = constraint_row.conrelid
                  AND attribute.attnum = key.attnum
                 ORDER BY key.position
               ),
               ARRAY(
                 SELECT attribute.attname
                 FROM unnest(constraint_row.confkey) WITH ORDINALITY AS key(attnum, position)
                 JOIN pg_attribute AS attribute
                   ON attribute.attrelid = constraint_row.confrelid
                  AND attribute.attnum = key.attnum
                 ORDER BY key.position
               )
        FROM pg_constraint AS constraint_row
        JOIN pg_class AS relation ON relation.oid = constraint_row.conrelid
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        LEFT JOIN pg_class AS referenced_relation
          ON referenced_relation.oid = constraint_row.confrelid
        LEFT JOIN pg_namespace AS referenced_namespace
          ON referenced_namespace.oid = referenced_relation.relnamespace
        WHERE namespace.nspname = current_schema()
          AND relation.relname = ANY(%s)
        ORDER BY relation.relname, constraint_row.contype, constraint_row.conname
        """,
        (list(_EXPECTED_COLUMNS),),
    ).fetchall()
    actual_constraints: dict[str, dict[str, set]] = {
        table: {"primary_keys": set(), "foreign_keys": set(), "checks": set()}
        for table in _EXPECTED_COLUMNS
    }
    current_schema = conn.execute("SELECT current_schema()").fetchone()[0]
    for (
        table,
        kind,
        definition,
        referenced_table,
        referenced_schema,
        update_action,
        delete_action,
        match_type,
        deferrable,
        initially_deferred,
        validated,
        columns,
        referenced_columns,
    ) in constraint_rows:
        if not validated:
            errors.append(f"{table} has a non-validated constraint: {definition}")
        if kind == "p":
            actual_constraints[table]["primary_keys"].add(
                (tuple(columns), deferrable, initially_deferred)
            )
        elif kind == "f":
            target = referenced_table if referenced_schema == current_schema else f"{referenced_schema}.{referenced_table}"
            actual_constraints[table]["foreign_keys"].add(
                (
                    tuple(columns),
                    target,
                    tuple(referenced_columns),
                    update_action,
                    delete_action,
                    match_type,
                    deferrable,
                    initially_deferred,
                )
            )
        elif kind == "c":
            actual_constraints[table]["checks"].add(_compact_sql(definition))
        else:
            errors.append(f"{table} has an unexpected {kind!r} constraint: {definition}")

    for table, expected in _EXPECTED_CONSTRAINTS.items():
        actual = actual_constraints[table]
        for constraint_kind in ("primary_keys", "foreign_keys", "checks"):
            if actual[constraint_kind] != expected[constraint_kind]:
                label = constraint_kind.replace("_", " ")
                errors.append(
                    f"{table} {label} differ "
                    f"(expected {expected[constraint_kind]!r}; found {actual[constraint_kind]!r})"
                )

    index_rows = conn.execute(
        """
        SELECT relation.relname,
               index_relation.relname,
               index_row.indisunique,
               index_row.indisprimary,
               ARRAY(
                 SELECT pg_get_indexdef(index_row.indexrelid, position, true)
                 FROM generate_series(1, index_row.indnkeyatts) AS position
                 ORDER BY position
               ),
               pg_get_expr(index_row.indpred, index_row.indrelid)
        FROM pg_index AS index_row
        JOIN pg_class AS relation ON relation.oid = index_row.indrelid
        JOIN pg_class AS index_relation ON index_relation.oid = index_row.indexrelid
        JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = current_schema()
          AND relation.relname = ANY(%s)
        ORDER BY relation.relname, index_relation.relname
        """,
        (list(_EXPECTED_COLUMNS),),
    ).fetchall()
    actual_indexes: dict[str, set[tuple]] = {
        table: set() for table in _EXPECTED_COLUMNS
    }
    for table, name, unique, primary, columns, predicate in index_rows:
        actual_indexes[table].add(
            (name, unique, primary, tuple(columns), _compact_sql(predicate) if predicate else None)
        )
    for table, expected in _EXPECTED_INDEXES.items():
        if actual_indexes[table] != expected:
            errors.append(
                f"{table} indexes differ "
                f"(expected {expected!r}; found {actual_indexes[table]!r})"
            )

    if errors:
        raise BaselineSchemaMismatch(
            "Story 1.1 baseline schema mismatch: " + "; ".join(errors)
        )


def _should_adopt_baseline(database_url: str) -> bool:
    with psycopg.connect(psycopg_url(database_url)) as conn:
        table_rows = conn.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = current_schema() AND table_type = 'BASE TABLE'
            """
        ).fetchall()
        tables = {row[0] for row in table_rows}
        migration_table_exists = "_yoyo_migration" in tables
        history_count = (
            conn.execute("SELECT count(*) FROM _yoyo_migration").fetchone()[0]
            if migration_table_exists
            else 0
        )
        managed_tables = set(_EXPECTED_COLUMNS) | {
            "users",
            "entitlements",
            "suppliers",
            "supplier_snapshots",
        }
        existing_managed = tables & managed_tables
        if history_count or not existing_managed:
            return False
        baseline_tables = set(_EXPECTED_COLUMNS)
        if existing_managed != baseline_tables:
            raise BaselineSchemaMismatch(
                "Story 1.1 baseline schema mismatch: managed tables differ "
                f"(expected {sorted(baseline_tables)!r}; "
                f"found {sorted(existing_managed)!r})"
            )
        validate_tracer_baseline(conn)
        return True


def _close_backend(backend) -> None:
    connection = getattr(backend, "connection", None)
    if connection is not None:
        connection.close()


def apply_migrations(database_url: str) -> None:
    adopt_baseline = _should_adopt_baseline(database_url)
    backend = get_backend(_yoyo_url(database_url))
    try:
        migrations = read_migrations(str(MIGRATIONS_DIR))
        baseline = next(migration for migration in migrations if migration.id == BASELINE_ID)
        with backend.lock():
            if adopt_baseline and not backend.is_applied(baseline):
                backend.mark_migrations([baseline])
            backend.apply_migrations(backend.to_apply(migrations))
    finally:
        _close_backend(backend)


def migration_status(database_url: str) -> list[tuple[str, bool]]:
    backend = get_backend(_yoyo_url(database_url))
    try:
        migrations = read_migrations(str(MIGRATIONS_DIR))
        return [(migration.id, backend.is_applied(migration)) for migration in migrations]
    finally:
        _close_backend(backend)


def rollback_core_migration(database_url: str) -> bool:
    backend = get_backend(_yoyo_url(database_url))
    try:
        migrations = read_migrations(str(MIGRATIONS_DIR))
        with backend.lock():
            applied_core = [
                migration
                for migration in migrations
                if migration.id in CORE_IDS and backend.is_applied(migration)
            ]
            if not applied_core:
                return False
            rollback_order = backend.to_rollback(migrations)
            blockers = [
                migration.id
                for migration in rollback_order
                if migration.id not in CORE_IDS | {BASELINE_ID}
            ]
            if blockers:
                raise RuntimeError(
                    "Cannot roll back the core schema while later revisions are applied: "
                    + ", ".join(blockers)
                )
            story_rollbacks = [
                migration for migration in rollback_order if migration.id in CORE_IDS
            ]
            backend.rollback_migrations(story_rollbacks)
        return True
    finally:
        _close_backend(backend)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Manage the VCT Connect database schema")
    parser.add_argument("action", choices=("apply", "status", "rollback-core"))
    parser.add_argument(
        "--confirm-isolated-database",
        action="store_true",
        help="required for the destructive Story 1.3 rollback",
    )
    args = parser.parse_args(argv)
    if args.action == "rollback-core" and not args.confirm_isolated_database:
        parser.error("rollback-core requires --confirm-isolated-database")

    database_url = os.environ["DATABASE_URL"]
    if args.action == "apply":
        apply_migrations(database_url)
    elif args.action == "status":
        for migration_id, applied in migration_status(database_url):
            print(f"{migration_id}: {'applied' if applied else 'pending'}")
    else:
        print("rolled back" if rollback_core_migration(database_url) else "already at baseline")


if __name__ == "__main__":
    main()
