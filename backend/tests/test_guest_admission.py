import os
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from backend.app.fixture import FIXTURE_URL, fixture_result
from backend.app.storage import AdmissionDenied, Store
from backend.worker.main import process_local_once


@pytest.fixture
def store():
    database_url = os.getenv("VCT_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set VCT_TEST_DATABASE_URL for PostgreSQL admission checks")
    schema = f"admission_test_{uuid4().hex}"
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    parsed = urlsplit(database_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["options"] = f"{query.get('options', '')} -c search_path={schema}".strip()
    isolated_url = urlunsplit(parsed._replace(query=urlencode(query, quote_via=quote)))
    instance = Store(isolated_url)
    try:
        instance.initialize()
        yield instance
    finally:
        with psycopg.connect(database_url, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def counts(store):
    with store.connect() as conn:
        return tuple(conn.execute(f"SELECT count(*) FROM {table}").fetchone()["count"]
                     for table in ("analyses", "local_queue", "analysis_outbox"))


def test_guest_and_customer_admission_is_atomic_and_records_provenance(store):
    guest_key = "a" * 64
    guest_id = store.submit_guest(
        FIXTURE_URL, guest_key, azure=False,
        browser_limit=1, global_limit=2, window_seconds=86400,
    )
    guest = store.get_for_guest(guest_id, guest_key)
    assert guest is not None
    assert (guest["mode"], guest["actor_type"], guest["extraction_method"], guest["scoring_version"]) == (
        "GUEST_PUBLIC", "GUEST", "FIXTURE", "v0.1.0",
    )
    assert store.get_for_guest(guest_id, "b" * 64) is None
    with store.connect() as conn:
        conn.execute(
            "UPDATE analyses SET created_at = now() - interval '30 days' - interval '1 second' WHERE id = %s",
            (guest_id,),
        )
    assert store.get_for_guest(guest_id, guest_key) is None
    with store.connect() as conn:
        row = conn.execute("SELECT user_id, guest_key_hash FROM analyses WHERE id = %s", (guest_id,)).fetchone()
    assert row["user_id"] is None
    assert row["guest_key_hash"] != guest_key
    before = counts(store)
    with pytest.raises(AdmissionDenied):
        store.submit_guest(
            FIXTURE_URL, guest_key, azure=False,
            browser_limit=1, global_limit=2, window_seconds=86400,
        )
    assert counts(store) == before

    user = store.resolve_user(f"customer_{uuid4().hex}")
    customer_id = store.submit_customer(
        FIXTURE_URL, user["id"], azure=True, customer_limit=1, window_seconds=86400,
    )
    customer = store.get_for_user(customer_id, user["id"])
    assert customer is not None
    assert (customer["mode"], customer["actor_type"], customer["extraction_method"], customer["scoring_version"]) == (
        "ACCOUNT_PUBLIC", "CUSTOMER", "FIXTURE", "v0.1.0",
    )
    assert store.get_for_guest(customer_id, guest_key) is None
    before = counts(store)
    with pytest.raises(AdmissionDenied):
        store.submit_customer(
            FIXTURE_URL, user["id"], azure=True, customer_limit=1, window_seconds=86400,
        )
    assert counts(store) == before
    assert process_local_once(store)
    first = store.get(guest_id)
    assert first["result"] == fixture_result(FIXTURE_URL)
    assert not process_local_once(store)
    assert store.get(guest_id)["result"] == first["result"]
    assert store.get(guest_id)["actor_type"] == "GUEST"


def test_concurrent_guest_requests_cannot_exceed_shared_cap(store):
    def submit(key):
        try:
            return store.submit_guest(
                FIXTURE_URL, key, azure=True,
                browser_limit=10, global_limit=1, window_seconds=86400,
            )
        except AdmissionDenied:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, ("c" * 64, "d" * 64)))
    assert sum(value is not None for value in results) == 1
    assert counts(store) == (1, 0, 1)
    with store.connect() as conn:
        used = conn.execute(
            "SELECT used FROM admission_counters WHERE scope = 'GUEST_GLOBAL' AND subject = 'all'"
        ).fetchone()["used"]
    assert used == 1
