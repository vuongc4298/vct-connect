import os
import json
from uuid import UUID, uuid4
from pathlib import Path

import pytest
import httpx
from fastapi.testclient import TestClient

os.environ.setdefault("DEVELOPER_MODE", "true")
os.environ.setdefault("DATABASE_URL", "postgresql://unused")
os.environ["QUEUE_TRANSPORT"] = "local"

from backend.app.auth import InvalidIdentity, VerifiedIdentity
from backend.app.config import Settings
from backend.app.fixture import FIXTURE_URL, fixture_result
from backend.app.extraction import extract_1688, parse_1688_page
from backend.app.extraction import parse_taobao_page
from backend.app.extraction.contracts import EVIDENCE_FIELDS
from backend.app.extraction.renormalize import UnsupportedRawEvidence, VERSIONS
from backend.app.extraction.extension1688 import DomCapture, normalize_capture
from backend.app.extraction.extensiontaobao import TaobaoCapture, normalize_taobao_capture
from backend.app.main import create_app
from backend.app.queue import AzureQueue
from backend.app.storage import AdmissionDenied, LeaseLost, ResultConflict, Store
from backend.worker.main import dispatch_outbox_once, process_azure_once, process_local_once


@pytest.mark.parametrize("guest", [False, True])
@pytest.mark.parametrize("platform", ["1688", "TAOBAO", "ALIBABA"])
def test_public_browser_queue_owner_atomic_provenance_and_replay(store, monkeypatch, guest, platform):
    from backend.tests.test_browser_fallback import fixture, ADAPTERS, gain
    url, html = fixture(platform)
    subject = "browser_" + uuid4().hex
    settings = Settings(store.database_url, "local", None, None, True, public_browser_fallback=True)
    api = TestClient(create_app(store=store, settings=settings, verifier=HeaderSubjectVerifier()))
    headers = {"x-vct-guest-key": uuid4().hex * 2} if guest else {"Authorization": "Bearer subject:" + subject}
    endpoint = "/api/v1/guest-analyses" if guest else "/api/v1/analyses"
    submitted = api.post(endpoint, json={"source_url": url}, headers=headers)
    assert submitted.status_code == 202
    analysis_id = UUID(submitted.json()["id"])
    adapter, parser = ADAPTERS[platform]
    def extract(source, **kwargs):
        assert kwargs["browser_fallback"] is True
        with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, headers={"content-type": "text/html"}, text=html))) as transport:
            return adapter(source, client=transport, dns_check=lambda _: True,
                           browser_renderer=None if os.getenv("VCT_TEST_BROWSER") == "true" else lambda *_: gain(parser(html, source, analysis_mode=kwargs["analysis_mode"])), **kwargs)
    monkeypatch.setattr("backend.worker.main." + {"1688": "extract_1688", "TAOBAO": "extract_taobao", "ALIBABA": "extract_alibaba"}[platform], extract)
    try:
        assert process_local_once(store, settings)
        row = api.get(f"{endpoint}/{analysis_id}", headers=headers).json()
        assert row["extraction_method"] == row["supplier_data"]["extraction_method"] == "PUBLIC_BROWSER"
        assert row["supplier_data"]["analysis_mode"] == ("GUEST_PUBLIC" if guest else "ACCOUNT_PUBLIC")
        assert len(row["raw_evidence"]["rendered_html_sha256"]) == 64
        assert row["supplier_data"]["completeness"] > parser(html, url)["supplier_data"]["completeness"]
        wrong = {"x-vct-guest-key": "f" * 64} if guest else {"Authorization": "Bearer subject:browser_other"}
        assert api.get(f"{endpoint}/{analysis_id}", headers=wrong).status_code == 404
        payload = {**row["result"], "supplier_data": row["supplier_data"], "raw_payload": row["raw_evidence"], "reviews": row["reviews"]}
        assert store.complete_processing(analysis_id, uuid4(), payload) == "replay"
        changed = json.loads(json.dumps(payload))
        changed["raw_payload"]["rendered_html_sha256"] = "b" * 64
        with pytest.raises(ResultConflict):
            store.complete_processing(analysis_id, uuid4(), changed)
        assert store.get(analysis_id)["supplier_snapshot_id"] == UUID(row["supplier_snapshot_id"])
    finally:
        remove(store, analysis_id)
        remove_user(store, subject)
        remove_user(store, "browser_other")


def test_public_browser_transition_requires_current_claim(store):
    from backend.tests.test_browser_fallback import fixture, extracted, gain
    url, _ = fixture()
    analysis_id = store.submit_local(url)
    claim = store.claim_processing(analysis_id, 300, 5)
    result, _ = extracted()
    payload = gain(result)["outcome"]
    payload["supplier_data"]["analysis_mode"] = "GUEST_PUBLIC"
    payload["supplier_data"]["extraction_method"] = "PUBLIC_BROWSER"
    try:
        with pytest.raises((ValueError, LeaseLost)):
            store.complete_processing(analysis_id, uuid4(), payload)
        assert store.get(analysis_id)["extraction_method"] == "PUBLIC_HTTP"
        assert store.get(analysis_id)["supplier_snapshot_id"] is None
        assert store.complete_processing(analysis_id, claim["token"], payload) == "completed"
    finally:
        remove(store, analysis_id)


@pytest.mark.skipif(os.getenv("VCT_TEST_BROWSER") != "true", reason="Actual namespace fault completion requires the controlled Linux image")
@pytest.mark.parametrize("fault", ["refusal", "death", "output", "cleanup"])
def test_public_browser_fault_preserves_http_owner_claim_and_next_job(store, monkeypatch, tmp_path, fault):
    from copy import deepcopy
    from backend.tests.test_browser_fallback import fixture, ADAPTERS
    from backend.tests.test_browser_supervision import install_supervisor, allocation_runner
    from backend.app.extraction import browser

    marker = tmp_path / "allocation-refused"
    runner = {"refusal": allocation_runner(marker),
              "death": "import os,signal; os.kill(os.getpid(),signal.SIGKILL)",
              "output": "import os; os.write(1,b'x'*2100000)",
              "cleanup": "print('{\"code\":\"NO_GAIN\"}')"}[fault]
    install_supervisor(monkeypatch, runner=runner,
                       setup="import time\ns._cleanup_profile=lambda p: time.sleep(12)" if fault == "cleanup" else "")
    url, html = fixture()
    owner = store.resolve_user("browser_fault_owner_" + uuid4().hex)
    other = store.resolve_user("browser_fault_other_" + uuid4().hex)
    settings = Settings(store.database_url, "local", None, None, True, public_browser_fallback=True)
    ids, originals, claims = [], [], []
    _, parser = ADAPTERS["1688"]
    complete = store.complete_processing

    def current_claim(analysis_id, token, payload):
        with pytest.raises(LeaseLost):
            complete(analysis_id, uuid4(), payload)
        claims.append(token)
        return complete(analysis_id, token, payload)

    monkeypatch.setattr(store, "complete_processing", current_claim)

    def extract(source, **kwargs):
        expected = parser(html, source, analysis_mode=kwargs["analysis_mode"])
        # Freeze the exact fetched HTTP object before the actual failing attempt.
        originals.append(deepcopy(expected))
        selected = browser.maybe_render(expected, html, html.encode(), enabled=kwargs["browser_fallback"])
        assert selected is expected and selected == originals[-1]
        return selected

    monkeypatch.setattr("backend.worker.main.extract_1688", extract)
    try:
        first = store.submit_local(url, owner["id"])
        ids.append(first)
        assert process_local_once(store, settings)
        row = store.get_for_user(first, owner["id"])
        assert row["status"] == "COMPLETED" and row["attempt_count"] == 1
        assert row["failure_code"] is None
        assert row["extraction_method"] == "PUBLIC_HTTP"
        assert row["supplier_data"] == originals[0]["supplier_data"]
        assert row["raw_evidence"] == originals[0]["raw_payload"]
        assert "rendered_html_sha256" not in row["raw_evidence"]
        assert store.get_for_user(first, other["id"]) is None
        assert len(claims) == 1
        assert complete(first, uuid4(), originals[0]) == "replay"
        if fault == "refusal":
            assert marker.read_text() == "MemoryError"
        # Same live worker completes another real failure without a retry or a
        # changed method. Actual subsequent Chromium gain is a separate G6 gate.
        second = store.submit_local(url, owner["id"])
        ids.append(second)
        assert process_local_once(store, settings)
        next_row = store.get_for_user(second, owner["id"])
        assert next_row["status"] == "COMPLETED" and next_row["attempt_count"] == 1
        assert next_row["supplier_data"] == originals[1]["supplier_data"]
        assert next_row["raw_evidence"] == originals[1]["raw_payload"]
        assert len(claims) == 2 and claims[0] != claims[1]
        assert store.get(first)["supplier_snapshot_id"] == row["supplier_snapshot_id"]
    finally:
        for analysis_id in reversed(ids):
            remove(store, analysis_id)
        remove_user(store, owner["clerk_user_id"])
        remove_user(store, other["clerk_user_id"])


@pytest.mark.parametrize("guest", [False, True])
@pytest.mark.parametrize("profile", [False, True])
def test_alibaba_mocked_public_queue_owner_and_immutable_replay(store, monkeypatch, guest, profile):
    from backend.app.extraction.alibaba import extract_alibaba
    source = "https://dgxuandele.en.alibaba.com/company_profile.html" if profile else "https://www.alibaba.com/product-detail/100-Cotton-180gsm-T-shirts-Men_1600147809763.html"
    filename = "alibaba_profile_dgxuandele.html" if profile else "alibaba_product_1600147809763.html"
    content = (Path(__file__).parent / "fixtures" / filename).read_bytes()
    subject = "alibaba_" + uuid4().hex
    settings = Settings(store.database_url, "local", None, None, True)
    client = TestClient(create_app(store=store, settings=settings, verifier=HeaderSubjectVerifier()))
    headers = {"x-vct-guest-key": uuid4().hex * 2} if guest else {"Authorization": "Bearer subject:" + subject}
    endpoint = "/api/v1/guest-analyses" if guest else "/api/v1/analyses"
    submitted = client.post(endpoint, json={"source_url": source + "?spm=tracking"}, headers=headers)
    assert submitted.status_code == 202
    analysis_id = UUID(submitted.json()["id"])
    def public_adapter(url, **kwargs):
        with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, headers={"content-type": "text/html"}, content=content))) as transport:
            return extract_alibaba(url, client=transport, dns_check=lambda host: True, **kwargs)
    monkeypatch.setattr("backend.worker.main.extract_alibaba", public_adapter)
    try:
        assert process_local_once(store)
        row = client.get(f"{endpoint}/{analysis_id}", headers=headers).json()
        assert row["status"] == "COMPLETED" and row["supplier_data"]["platform"] == "ALIBABA"
        assert row["supplier_data"]["analysis_mode"] == ("GUEST_PUBLIC" if guest else "ACCOUNT_PUBLIC")
        assert row["supplier_data"]["platform_supplier_id"] == ("dgxuandele.en.alibaba.com" if profile else "beautiy.en.alibaba.com")
        assert len(row["reviews"]) == (0 if profile else 1)
        assert client.get(f"{endpoint}/{analysis_id}", headers={"x-vct-guest-key": "b"*64} if guest else {"Authorization": "Bearer subject:alibaba_other"}).status_code == 404
        payload = {**row["result"], "supplier_data": row["supplier_data"], "raw_payload": row["raw_evidence"], "reviews": row["reviews"]}
        assert store.complete_processing(analysis_id, uuid4(), payload) == "replay"
        changed = json.loads(json.dumps(payload)); changed["raw_payload"]["public_fields"]["changed"] = True
        with pytest.raises(ResultConflict): store.complete_processing(analysis_id, uuid4(), changed)
        assert store.get(analysis_id)["supplier_snapshot_id"] == UUID(row["supplier_snapshot_id"])
    finally:
        remove(store, analysis_id); remove_user(store, subject); remove_user(store, "alibaba_other")


def test_alibaba_access_wall_settles_without_snapshot(store, monkeypatch):
    from backend.app.extraction.alibaba import parse_alibaba_page
    source = "https://dgxuandele.en.alibaba.com/company_profile.html"
    analysis_id = store.submit_local(source)
    monkeypatch.setattr("backend.worker.main.extract_alibaba", lambda url, **kwargs: parse_alibaba_page('<punish-component></punish-component>', url, **kwargs))
    try:
        assert process_local_once(store)
        row = store.get(analysis_id)
        assert row["status"] == "COMPLETED" and row["result"]["extraction_status"] == "BLOCKED"
        assert row["supplier_snapshot_id"] is None and row["supplier_data"] is None and row["reviews"] == []
        assert store.complete_processing(analysis_id, uuid4(), row["result"]) == "replay"
    finally:
        remove(store, analysis_id)


def test_alibaba_supplier_platform_isolation_and_spoof_rollback(store):
    from backend.app.extraction.alibaba import parse_alibaba_page
    source = "https://dgxuandele.en.alibaba.com/company_profile.html"
    html = (Path(__file__).parent / "fixtures" / "alibaba_profile_dgxuandele.html").read_text(encoding="utf-8")
    alibaba = parse_alibaba_page(html, source, analysis_mode="GUEST_PUBLIC")
    taobao_source = "https://item.taobao.com/item.htm?id=1076425861755"
    taobao = parse_taobao_page((Path(__file__).parent / "fixtures" / "taobao_item_1076425861755.html").read_text(encoding="utf-8"), taobao_source, analysis_mode="GUEST_PUBLIC")
    key = "public_supplier_" + uuid4().hex
    ids = [store.submit_local(source), store.submit_local(taobao_source)]
    try:
        for analysis_id, payload in zip(ids, [alibaba, taobao]):
            claim = store.claim_processing(analysis_id, 60, 3)
            payload["supplier_data"]["platform_supplier_id"] = key
            if payload is alibaba:
                spoof = json.loads(json.dumps(payload)); spoof["supplier_data"]["platform"] = "TAOBAO"
                with pytest.raises(ValueError): store.complete_processing(analysis_id, claim["token"], spoof)
                assert store.get(analysis_id)["supplier_snapshot_id"] is None
            store.complete_processing(analysis_id, claim["token"], payload)
        with store.connect() as conn:
            rows = conn.execute("SELECT id, platform FROM suppliers WHERE platform_supplier_id = %s", (key,)).fetchall()
        assert {row["platform"] for row in rows} == {"ALIBABA", "TAOBAO"} and len({row["id"] for row in rows}) == 2
    finally:
        for analysis_id in ids: remove(store, analysis_id)


@pytest.mark.parametrize("guest", [False, True])
@pytest.mark.parametrize("shop", [False, True])
def test_taobao_queue_persistence_owner_modes_and_immutable_replay(store, monkeypatch, guest, shop):
    url = "https://shop159450000.world.taobao.com/category.htm" if shop else "https://item.taobao.com/item.htm?id=1076425861755"
    filename = "taobao_shop_159450000.html" if shop else "taobao_item_1076425861755.html"
    html = (Path(__file__).parent / "fixtures" / filename).read_text(encoding="utf-8")
    guest_key = uuid4().hex * 2
    subject = f"taobao_{uuid4().hex}"
    settings = Settings(store.database_url, "local", None, None, True)
    client = TestClient(create_app(store=store, settings=settings, verifier=HeaderSubjectVerifier()))
    headers = {"x-vct-guest-key": guest_key} if guest else {"Authorization": f"Bearer subject:{subject}"}
    endpoint = "/api/v1/guest-analyses" if guest else "/api/v1/analyses"
    submitted = client.post(endpoint, headers=headers, json={"source_url": url + ("?spm=track" if shop else "&spm=track")})
    assert submitted.status_code == 202
    analysis_id = UUID(submitted.json()["id"])
    try:
        assert client.get(f"{endpoint}/{analysis_id}", headers={"x-vct-guest-key": "b" * 64} if guest else {"Authorization": "Bearer subject:other"}).status_code == 404
        monkeypatch.setattr("backend.worker.main.extract_taobao", lambda source_url, **kwargs: parse_taobao_page(html, source_url, **kwargs))
        assert process_local_once(store)
        row = client.get(f"{endpoint}/{analysis_id}", headers=headers).json()
        assert row["status"] == "COMPLETED" and row["supplier_data"]["platform"] == "TAOBAO"
        assert row["supplier_data"]["analysis_mode"] == ("GUEST_PUBLIC" if guest else "ACCOUNT_PUBLIC")
        assert row["supplier_data"]["completeness_denominator"] == list(EVIDENCE_FIELDS)
        payload = {**row["result"], "supplier_data": row["supplier_data"], "raw_payload": row["raw_evidence"], "reviews": row["reviews"]}
        assert store.complete_processing(analysis_id, uuid4(), payload) == "replay"
        changed = json.loads(json.dumps(payload))
        changed["raw_payload"]["public_fields"]["changed"] = True
        with pytest.raises(ResultConflict):
            store.complete_processing(analysis_id, uuid4(), changed)
        assert store.get(analysis_id)["supplier_snapshot_id"] == UUID(row["supplier_snapshot_id"])
    finally:
        remove(store, analysis_id)
        remove_user(store, subject)
        remove_user(store, "other")


def test_taobao_supplier_ids_are_platform_scoped_and_platform_spoofing_rolls_back(store):
    url = "https://item.taobao.com/item.htm?id=1076425861755"
    html = (Path(__file__).parent / "fixtures" / "taobao_item_1076425861755.html").read_text(encoding="utf-8")
    taobao = parse_taobao_page(html, url, analysis_mode="GUEST_PUBLIC")
    offer_url = "https://detail.1688.com/offer/996518024136.html"
    offer = parse_1688_page((Path(__file__).parent / "fixtures" / "1688_offer_996518024136.html").read_text(encoding="utf-8"), offer_url, analysis_mode="GUEST_PUBLIC")
    shared_id = str(uuid4().int)[:15]
    taobao["supplier_data"]["platform_supplier_id"] = shared_id
    offer["supplier_data"]["platform_supplier_id"] = shared_id
    ids = [store.submit_local(offer_url), store.submit_local(url)]
    try:
        for analysis_id, payload in zip(ids, (offer, taobao)):
            claim = store.claim_processing(analysis_id, 60, 3)
            if payload is taobao:
                changed = json.loads(json.dumps(payload)); changed["supplier_data"]["platform"] = "1688"
                with pytest.raises(ValueError):
                    store.complete_processing(analysis_id, claim["token"], changed)
                assert store.get(analysis_id)["supplier_snapshot_id"] is None
            store.complete_processing(analysis_id, claim["token"], payload)
        with store.connect() as conn:
            suppliers = conn.execute("SELECT id, platform FROM suppliers WHERE platform_supplier_id = %s", (shared_id,)).fetchall()
        assert {row["platform"] for row in suppliers} == {"1688", "TAOBAO"}
        assert len({row["id"] for row in suppliers}) == 2
    finally:
        for analysis_id in ids:
            remove(store, analysis_id)


class StaticVerifier:
    def __init__(self, subject=None):
        self.subject = subject or f"user_postgres_{uuid4().hex}"

    def verify(self, _request):
        return VerifiedIdentity(self.subject)


class HeaderSubjectVerifier:
    def verify(self, request):
        value = request.headers.get("authorization", "")
        if not value.startswith("Bearer subject:"):
            raise InvalidIdentity
        return VerifiedIdentity(value.removeprefix("Bearer subject:"))


@pytest.fixture
def store():
    url = os.getenv("VCT_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set VCT_TEST_DATABASE_URL for PostgreSQL integration checks")
    instance = Store(url)
    instance.initialize()
    yield instance


def remove(store: Store, analysis_id: UUID):
    with store.connect() as conn:
        linked = conn.execute(
            "SELECT supplier_id FROM supplier_snapshots WHERE analysis_id = %s", (analysis_id,)
        ).fetchone()
        conn.execute("DELETE FROM local_queue WHERE analysis_id = %s", (analysis_id,))
        conn.execute("DELETE FROM analysis_results WHERE analysis_id = %s", (analysis_id,))
        conn.execute("DELETE FROM text_report_jobs WHERE analysis_id = %s", (analysis_id,))
        conn.execute("UPDATE analyses SET supplier_snapshot_id = NULL WHERE id = %s", (analysis_id,))
        conn.execute("DELETE FROM supplier_snapshots WHERE analysis_id = %s", (analysis_id,))
        conn.execute("DELETE FROM analyses WHERE id = %s", (analysis_id,))
        if linked:
            conn.execute(
                "DELETE FROM suppliers WHERE id = %s AND NOT EXISTS "
                "(SELECT 1 FROM supplier_snapshots WHERE supplier_id = %s)",
                (linked["supplier_id"], linked["supplier_id"]),
            )


def remove_user(store: Store, clerk_user_id: str):
    with store.connect() as conn:
        conn.execute(
            """DELETE FROM users u WHERE u.clerk_user_id = %s
               AND NOT EXISTS (SELECT 1 FROM analyses a WHERE a.user_id = u.id)""",
            (clerk_user_id,),
        )


@pytest.mark.parametrize("method", ["PUBLIC_HTTP", "PUBLIC_BROWSER"])
@pytest.mark.parametrize("platform,layout", [
    ("1688", "offer"), ("TAOBAO", "item"), ("TAOBAO", "shop"),
    ("ALIBABA", "product"), ("ALIBABA", "profile"),
])
def test_owned_public_raw_replay_creates_immutable_versioned_evidence_without_fetch(
    store, monkeypatch, platform, layout, method,
):
    from backend.app.extraction import parse_alibaba_page
    fixtures = {
        ("1688", "offer"): ("1688_offer_996518024136.html", "https://detail.1688.com/offer/996518024136.html", parse_1688_page),
        ("TAOBAO", "item"): ("taobao_item_1076425861755.html", "https://item.taobao.com/item.htm?id=1076425861755", parse_taobao_page),
        ("TAOBAO", "shop"): ("taobao_shop_159450000.html", "https://shop159450000.world.taobao.com/category.htm", parse_taobao_page),
        ("ALIBABA", "product"): ("alibaba_product_1600147809763.html", "https://www.alibaba.com/product-detail/100-Cotton-180gsm-T-shirts-Men_1600147809763.html", parse_alibaba_page),
        ("ALIBABA", "profile"): ("alibaba_profile_dgxuandele.html", "https://dgxuandele.en.alibaba.com/company_profile.html", parse_alibaba_page),
    }
    filename, url, parser = fixtures[(platform, layout)]
    payload = parser((Path(__file__).parent / "fixtures" / filename).read_text(encoding="utf-8"), url)
    assert payload["extraction_status"] == "PARTIAL"
    if method == "PUBLIC_BROWSER":
        payload["supplier_data"].update(extraction_method=method, extractor_version="public-browser.v1")
        payload["raw_payload"].update(extraction_method=method, extractor_version="public-browser.v1",
                                      rendered_at=payload["supplier_data"]["extracted_at"],
                                      rendered_html_sha256="b" * 64)
    original_name = payload["supplier_data"]["supplier_name"]
    payload["supplier_data"]["supplier_name"] = None  # Simulate a superseded v1 mapping.
    if "supplier_name" not in payload["supplier_data"]["missing_fields"]:
        payload["supplier_data"]["missing_fields"].insert(0, "supplier_name")
        payload["supplier_data"]["completeness"] = round((12 - len(payload["supplier_data"]["missing_fields"])) / 12, 4)
    subject = "raw_replay_" + uuid4().hex
    owner = store.resolve_user(subject)
    other = store.resolve_user(subject + "_other")
    source_id = store.submit_customer(url, owner["id"], azure=False, customer_limit=10, window_seconds=86400)
    replay_id = None
    try:
        claim = store.claim_processing(source_id, 60, 3)
        store.complete_processing(source_id, claim["token"], payload)
        before = store.get_for_user(source_id, owner["id"])
        assert before["supplier_data"]["supplier_name"] is None
        with store.connect() as conn:
            supplier_id = conn.execute("SELECT supplier_id FROM supplier_snapshots WHERE analysis_id = %s", (source_id,)).fetchone()["supplier_id"]
            conn.execute("UPDATE suppliers SET name = 'Newer supplier display' WHERE id = %s", (supplier_id,))
            supplier_before = conn.execute("SELECT * FROM suppliers WHERE id = %s", (supplier_id,)).fetchone()
        assert store.get_for_user(source_id, other["id"]) is None
        with pytest.raises(LookupError):
            store.renormalize_customer_snapshot(source_id, other["id"], customer_limit=10, window_seconds=86400)
        with pytest.raises(AdmissionDenied):
            store.renormalize_customer_snapshot(source_id, owner["id"], customer_limit=1, window_seconds=86400)
        assert store.get_for_user(source_id, owner["id"]) == before
        monkeypatch.setattr(httpx, "Client", lambda *args, **kwargs: pytest.fail("Replay attempted HTTP"))
        monkeypatch.setattr("backend.app.extraction.browser.subprocess.Popen",
                            lambda *args, **kwargs: pytest.fail("Replay attempted browser"))
        replay_id = store.renormalize_customer_snapshot(source_id, owner["id"], customer_limit=10, window_seconds=86400)
        after = store.get_for_user(source_id, owner["id"])
        replay = store.get_for_user(replay_id, owner["id"])
        assert after == before
        assert replay["status"] == "COMPLETED" and replay["supplier_snapshot_id"] != before["supplier_snapshot_id"]
        assert replay["supplier_data"]["supplier_name"] == original_name
        assert replay["supplier_data"]["extractor_version"] == VERSIONS[platform]
        assert replay["supplier_data"]["extracted_at"] == before["supplier_data"]["extracted_at"]
        assert replay["supplier_data"]["extraction_method"] == before["supplier_data"]["extraction_method"]
        assert replay["supplier_data"]["completeness"] > before["supplier_data"]["completeness"]
        assert replay["supplier_data"]["missing_fields"] == [field for field in EVIDENCE_FIELDS if replay["supplier_data"][field] is None]
        assert replay["result"]["renormalized_from_snapshot_id"] == str(before["supplier_snapshot_id"])
        assert replay["raw_evidence"]["renormalized_from_snapshot_id"] == str(before["supplier_snapshot_id"])
        assert replay["raw_evidence"]["replay_limitation"] == "retained_public_fields_only"
        provenance = {key: replay["result"][key] for key in (
            "renormalized_from_snapshot_id", "source_extractor_version", "renormalized_at", "replay_limitation"
        )}
        assert replay["raw_evidence"] == before["raw_evidence"] | provenance
        assert replay["events"][0]["status"] == "QUEUED" and replay["events"][-1]["status"] == "COMPLETED"
        assert replay["reviews"] == payload["reviews"]
        with store.connect() as conn:
            assert conn.execute("SELECT * FROM suppliers WHERE id = %s", (supplier_id,)).fetchone() == supplier_before
            assert conn.execute("SELECT supplier_id FROM supplier_snapshots WHERE analysis_id = %s", (replay_id,)).fetchone()["supplier_id"] == supplier_id
        with pytest.raises(UnsupportedRawEvidence):
            store.renormalize_customer_snapshot(replay_id, owner["id"], customer_limit=10, window_seconds=86400)
    finally:
        if replay_id:
            remove(store, replay_id)
        remove(store, source_id)
        remove_user(store, subject)
        remove_user(store, subject + "_other")


def test_late_replay_failure_rolls_back_admission_and_all_evidence(store, monkeypatch):
    url = "https://item.taobao.com/item.htm?id=1076425861755"
    html = (Path(__file__).parent / "fixtures" / "taobao_item_1076425861755.html").read_text(encoding="utf-8")
    payload = parse_taobao_page(html, url)
    assert payload["reviews"]
    subject = "raw_late_failure_" + uuid4().hex
    owner = store.resolve_user(subject)
    source_id = store.submit_customer(url, owner["id"], azure=False, customer_limit=2, window_seconds=86400)
    tables = ("analyses", "analysis_status_events", "analysis_results", "supplier_snapshots", "supplier_reviews")

    def state():
        with store.connect() as conn:
            counts = {table: conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"] for table in tables}
            quota = conn.execute("SELECT * FROM admission_counters WHERE scope = 'CUSTOMER' AND subject = %s",
                                 (str(owner["id"]),)).fetchall()
        return counts, quota

    try:
        claim = store.claim_processing(source_id, 60, 3)
        store.complete_processing(source_id, claim["token"], payload)
        before = state()
        source_before = store.get_for_user(source_id, owner["id"])
        complete = Store._complete_processing
        calls = []

        def fail_after_completion(self, conn, analysis_id, token, result, **kwargs):
            complete(self, conn, analysis_id, token, result, **kwargs)
            calls.append(analysis_id)
            assert conn.execute("SELECT count(*) AS n FROM supplier_reviews r JOIN supplier_snapshots s "
                                "ON s.id = r.snapshot_id WHERE s.analysis_id = %s", (analysis_id,)).fetchone()["n"] == len(payload["reviews"])
            raise RuntimeError("Injected failure after replay persistence")

        monkeypatch.setattr(Store, "_complete_processing", fail_after_completion)
        with pytest.raises(RuntimeError, match="Injected failure"):
            store.renormalize_customer_snapshot(source_id, owner["id"], customer_limit=2, window_seconds=86400)
        assert len(calls) == 1
        assert state() == before
        assert store.get_for_user(source_id, owner["id"]) == source_before
    finally:
        remove(store, source_id)
        remove_user(store, subject)


def test_unsupported_raw_replay_rolls_back_without_spending_quota(store):
    url = "https://detail.1688.com/offer/996518024136.html"
    html = (Path(__file__).parent / "fixtures" / "1688_offer_996518024136.html").read_text(encoding="utf-8")
    payload = parse_1688_page(html, url)
    payload["raw_payload"]["public_fields"].pop("offer_base")
    subject = "raw_reject_" + uuid4().hex
    owner = store.resolve_user(subject)
    source_id = store.submit_customer(url, owner["id"], azure=False, customer_limit=2, window_seconds=86400)
    try:
        claim = store.claim_processing(source_id, 60, 3)
        store.complete_processing(source_id, claim["token"], payload)
        before = store.get(source_id)
        with store.connect() as conn:
            used = conn.execute("SELECT used FROM admission_counters WHERE scope = 'CUSTOMER' AND subject = %s ORDER BY window_number DESC LIMIT 1", (str(owner["id"]),)).fetchone()["used"]
        for _ in range(2):
            with pytest.raises(UnsupportedRawEvidence):
                store.renormalize_customer_snapshot(source_id, owner["id"], customer_limit=2, window_seconds=86400)
        with store.connect() as conn:
            assert conn.execute("SELECT count(*) AS n FROM analyses WHERE user_id = %s", (owner["id"],)).fetchone()["n"] == 1
            assert conn.execute("SELECT used FROM admission_counters WHERE scope = 'CUSTOMER' AND subject = %s ORDER BY window_number DESC LIMIT 1", (str(owner["id"]),)).fetchone()["used"] == used
        assert store.get(source_id) == before
    finally:
        remove(store, source_id)
        remove_user(store, subject)


@pytest.mark.parametrize("platform,url", [
    ("1688", "https://detail.1688.com/offer/996518024136.html"),
    ("TAOBAO", "https://item.taobao.com/item.htm?id=1076425861755"),
    ("ALIBABA", "https://www.alibaba.com/product-detail/100-Cotton-180gsm-T-shirts-Men_1600147809763.html"),
])
@pytest.mark.parametrize("case,status", [
    ("login", "AUTH_REQUIRED"), ("blocked", "BLOCKED"),
    ("changed", "PARSE_FAILED"), ("timeout", "TIMEOUT"),
])
def test_three_platform_failure_matrix_settles_without_snapshot(store, monkeypatch, platform, url, case, status):
    from backend.app.extraction import extract_taobao, extract_alibaba
    adapter = {"1688": extract_1688, "TAOBAO": extract_taobao, "ALIBABA": extract_alibaba}[platform]
    attempts = []

    def transport(request):
        attempts.append(request.url)
        if case == "timeout":
            raise httpx.ReadTimeout("fixture timeout", request=request)
        if case in {"login", "blocked"}:
            return httpx.Response(401 if case == "login" else 403)
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<html><h1>Changed layout</h1></html>")

    def extract(source, **kwargs):
        with httpx.Client(transport=httpx.MockTransport(transport)) as client:
            return adapter(source, client=client, dns_check=lambda _: True, sleep=lambda _: None, **kwargs)

    monkeypatch.setattr("backend.worker.main." + {"1688": "extract_1688", "TAOBAO": "extract_taobao", "ALIBABA": "extract_alibaba"}[platform], extract)
    analysis_id = store.submit_local(url)
    try:
        assert process_local_once(store)
        row = store.get(analysis_id)
        assert row["status"] == "COMPLETED" and row["result"]["extraction_status"] == status
        assert row["supplier_snapshot_id"] is None and row["supplier_data"] is None
        assert row["raw_evidence"] is None and row["reviews"] == []
        assert len(attempts) == (3 if case == "timeout" else 1)
    finally:
        remove(store, analysis_id)


def test_azure_submission_atomically_creates_initial_event_and_outbox(store):
    analysis_id = store.submit_azure(FIXTURE_URL)
    try:
        row = store.get(analysis_id)
        assert row["status"] == "QUEUED"
        assert [event["status"] for event in row["events"]] == ["QUEUED"]
        with store.connect() as conn:
            outbox = conn.execute(
                "SELECT message_id, state, attempts FROM analysis_outbox WHERE analysis_id = %s",
                (analysis_id,),
            ).fetchone()
        assert outbox == {"message_id": analysis_id, "state": "PENDING", "attempts": 0}
    finally:
        remove(store, analysis_id)


@pytest.mark.parametrize("shop", [False, True])
@pytest.mark.parametrize("browser", [False, True])
def test_taobao_user_evidence_atomic_ownership_replay_quota_and_shared_metadata(store, shop, browser):
    url = "https://shop159450000.world.taobao.com/category.htm" if shop else "https://item.taobao.com/item.htm?id=1076425861755"
    filename = "taobao_shop_159450000.html" if shop else "taobao_item_1076425861755.html"
    html = (Path(__file__).parent / "fixtures" / filename).read_text(encoding="utf-8")
    owner = store.resolve_user("recovery_owner_" + uuid4().hex)
    other = store.resolve_user("recovery_other_" + uuid4().hex)
    public_id = store.submit_local(url, owner["id"])
    analysis_id = None
    try:
        public = parse_taobao_page(html.replace("心相印维达生活馆", "Shared supplier"), url)
        claim = store.claim_processing(public_id, 60, 5)
        store.complete_processing(public_id, claim["token"], public)
        if browser:
            fields = {"supplier_name": "User-selected supplier"}
            if not shop:
                fields["product_title"] = "User-selected product"
                fields["reviews"] = [{"text": "  Original captured review  ", "original_length": 28}]
            payload = normalize_taobao_capture(TaobaoCapture.model_validate({
                "source_url": url, "source_kind": "shop" if shop else "item",
                "source_id": "159450000" if shop else "1076425861755", "fields": fields,
            }))
            persist = store.capture_customer_page
        else:
            original = html.replace("心相印维达生活馆", "Uploaded supplier").encode()
            payload = parse_taobao_page(original.decode(), url, extraction_method="USER_UPLOAD", uploaded_bytes=original)
            persist = store.import_customer_page
        analysis_id = persist(url, owner["id"], payload, customer_limit=1, window_seconds=86400)
        row = store.get_for_user(analysis_id, owner["id"])
        assert row["status"] == "COMPLETED" and row["supplier_data"]["platform"] == "TAOBAO"
        if browser and not shop:
            expected = [{"text": "Original captured review", "source_url": url}]
            assert row["supplier_data"]["reviews"] == expected
            assert row["reviews"] == expected
            assert row["raw_evidence"]["selected_fields"]["reviews"] == [{"text": "  Original captured review  ", "original_length": 28}]
        assert store.get_for_user(analysis_id, other["id"]) is None
        assert store.complete_processing(analysis_id, uuid4(), payload) == "replay"
        changed = json.loads(json.dumps(payload))
        changed["raw_payload"]["different"] = True
        with pytest.raises(ResultConflict):
            store.complete_processing(analysis_id, uuid4(), changed)
        with pytest.raises(AdmissionDenied):
            persist(url, owner["id"], payload, customer_limit=1, window_seconds=86400)
        with store.connect() as conn:
            supplier = conn.execute("SELECT name FROM suppliers WHERE platform = 'TAOBAO' AND platform_supplier_id = '2895982467'").fetchone()
            assert supplier["name"] == "Shared supplier"
            assert conn.execute("SELECT count(*) AS total FROM analyses WHERE user_id = %s", (owner["id"],)).fetchone()["total"] == 2
            assert not conn.execute("SELECT 1 FROM local_queue WHERE analysis_id = %s", (analysis_id,)).fetchone()
            assert not conn.execute("SELECT 1 FROM analysis_outbox WHERE analysis_id = %s", (analysis_id,)).fetchone()
    finally:
        if analysis_id:
            remove(store, analysis_id)
        remove(store, public_id)
        remove_user(store, owner["clerk_user_id"])
        remove_user(store, other["clerk_user_id"])


def test_queued_taobao_cannot_complete_with_upload_method(store):
    url = "https://item.taobao.com/item.htm?id=1076425861755"
    html = (Path(__file__).parent / "fixtures" / "taobao_item_1076425861755.html").read_text(encoding="utf-8")
    owner = store.resolve_user("method_owner_" + uuid4().hex)
    analysis_id = store.submit_local(url, owner["id"])
    try:
        claim = store.claim_processing(analysis_id, 60, 5)
        payload = parse_taobao_page(html, url, extraction_method="USER_UPLOAD", uploaded_bytes=html.encode())
        with pytest.raises(ValueError, match="missing matching"):
            store.complete_processing(analysis_id, claim["token"], payload)
        assert store.get(analysis_id)["supplier_snapshot_id"] is None
    finally:
        remove(store, analysis_id)
        remove_user(store, owner["clerk_user_id"])


def test_postgres_exact_replay_preserves_first_result(store):
    analysis_id = store.submit_local(FIXTURE_URL)
    try:
        assert process_local_once(store)
        first = store.get(analysis_id)
        assert first["status"] == "COMPLETED"
        assert first["result"] == fixture_result(FIXTURE_URL)
        assert store.complete_processing(analysis_id, uuid4(), fixture_result(FIXTURE_URL)) == "replay"
        with pytest.raises(ResultConflict):
            store.complete_processing(analysis_id, uuid4(), {"fixture": True, "source_url": "conflict"})
        store.record_result_conflict(analysis_id)
        with store.connect() as conn:
            count = conn.execute(
                "SELECT count(*) AS total FROM analysis_results WHERE analysis_id = %s",
                (analysis_id,),
            ).fetchone()["total"]
        assert count == 1
        assert store.get(analysis_id)["result"] == first["result"]
        assert store.get(analysis_id)["status"] == "COMPLETED"
        assert store.get(analysis_id)["events"][-1]["failure_code"] == "RESULT_CONFLICT"
    finally:
        remove(store, analysis_id)


def test_live_snapshot_transaction_linkage_owner_scope_and_replay(store):
    url = "https://detail.1688.com/offer/996518024136.html"
    owner = store.resolve_user(f"owner_{uuid4().hex}")
    other = store.resolve_user(f"other_{uuid4().hex}")
    analysis_id = store.submit_local(url, owner["id"])
    html = '<html><head><link rel="canonical" href="' + url + '"></head><body>' \
           '<div class="title-content"><h1>Dress</h1></div>' \
           '<div class="review-item">Accessible review</div></body></html>'
    payload = parse_1688_page(html, url)
    try:
        assert process_local_once(store, compute=lambda _: payload)
        client = TestClient(create_app(
            store=store,
            settings=Settings(store.database_url, "local", None, None, True),
            verifier=HeaderSubjectVerifier(),
        ))
        endpoint = f"/api/v1/analyses/{analysis_id}"
        first_response = client.get(endpoint, headers={"authorization": f"Bearer subject:{owner['clerk_user_id']}"})
        assert first_response.status_code == 200
        first = first_response.json()
        assert first["status"] == "COMPLETED"
        assert first["result"]["extraction_status"] == "PARTIAL"
        assert first["supplier_snapshot_id"]
        assert first["supplier_data"]["products"][0]["title"] == "Dress"
        assert first["supplier_data"]["source_url"] == url
        assert first["supplier_data"]["extraction_method"] == "PUBLIC_HTTP"
        assert first["supplier_data"]["analysis_mode"] == "ACCOUNT_PUBLIC"
        assert first["supplier_data"]["extractor_version"]
        assert first["supplier_data"]["extracted_at"]
        assert 0 < first["supplier_data"]["completeness"] < 1
        assert "supplier_name" in first["supplier_data"]["missing_fields"]
        assert first["raw_evidence"]["public_fields"]["title"] == "Dress"
        assert first["reviews"] == [{"text": "Accessible review", "source_url": url}]
        assert client.get(endpoint, headers={"authorization": f"Bearer subject:{other['clerk_user_id']}"}).status_code == 404
        assert store.complete_processing(analysis_id, uuid4(), payload) == "replay"
        changed_evidence = {**payload, "supplier_data": {**payload["supplier_data"], "supplier_name": "Changed"}}
        with pytest.raises(ResultConflict):
            store.complete_processing(analysis_id, uuid4(), changed_evidence)
        with store.connect() as conn:
            snapshot_count = conn.execute(
                "SELECT count(*) AS total FROM supplier_snapshots WHERE analysis_id = %s", (analysis_id,)
            ).fetchone()["total"]
            review_count = conn.execute(
                "SELECT count(*) AS total FROM supplier_reviews WHERE snapshot_id = %s",
                (first["supplier_snapshot_id"],),
            ).fetchone()["total"]
        assert (snapshot_count, review_count) == (1, 1)
        assert not process_local_once(store)
    finally:
        remove(store, analysis_id)
        remove_user(store, owner["clerk_user_id"])
        remove_user(store, other["clerk_user_id"])


def test_saved_page_import_is_atomic_owner_scoped_and_quota_limited(store):
    url = "https://detail.1688.com/offer/996518024136.html"
    owner = store.resolve_user(f"import_owner_{uuid4().hex}")
    other = store.resolve_user(f"import_other_{uuid4().hex}")
    html = (f'<link rel="canonical" href="{url}">'
            '<div class="title-content"><h1>Dress</h1></div>'
            '<div class="review-item">Accessible review</div>')
    payload = parse_1688_page(html, url, extraction_method="USER_UPLOAD")
    seller_id = f"seller_{uuid4().hex}"
    supplier_id = uuid4()
    original_url = "https://detail.1688.com/offer/111111111111.html"
    payload["supplier_data"]["platform_supplier_id"] = seller_id
    payload["supplier_data"]["supplier_name"] = "Uploaded name"
    with store.connect() as conn:
        conn.execute(
            """INSERT INTO suppliers (id, platform, platform_supplier_id, name, source_url)
               VALUES (%s, '1688', %s, %s, %s)""",
            (supplier_id, seller_id, "Existing name", original_url),
        )
    analysis_id = None
    try:
        invalid = {**payload, "supplier_data": {**payload["supplier_data"], "source_url": "wrong"}}
        with pytest.raises(ValueError):
            store.import_customer_page(url, owner["id"], invalid,
                                       customer_limit=1, window_seconds=86400)
        with store.connect() as conn:
            assert conn.execute(
                "SELECT used FROM admission_counters WHERE scope = 'CUSTOMER' AND subject = %s",
                (str(owner["id"]),),
            ).fetchone() is None
        analysis_id = store.import_customer_page(url, owner["id"], payload,
                                                 customer_limit=1, window_seconds=86400)
        row = store.get_for_user(analysis_id, owner["id"])
        assert row["status"] == "COMPLETED"
        assert row["extraction_method"] == "USER_UPLOAD"
        assert row["supplier_data"]["extraction_method"] == "USER_UPLOAD"
        assert row["supplier_data"]["supplier_name"] == "Uploaded name"
        assert row["reviews"] == [{"text": "Accessible review", "source_url": url}]
        assert html not in str(row["raw_evidence"])
        assert store.get_for_user(analysis_id, other["id"]) is None
        assert [event["status"] for event in row["events"]] == ["QUEUED", "PROCESSING", "COMPLETED"]
        with store.connect() as conn:
            shared = conn.execute(
                "SELECT name, source_url FROM suppliers WHERE id = %s", (supplier_id,),
            ).fetchone()
            assert shared == {"name": "Existing name", "source_url": original_url}
            assert conn.execute("SELECT 1 FROM local_queue WHERE analysis_id = %s", (analysis_id,)).fetchone() is None
            assert conn.execute("SELECT 1 FROM analysis_outbox WHERE analysis_id = %s", (analysis_id,)).fetchone() is None
        with pytest.raises(AdmissionDenied):
            store.import_customer_page(url, owner["id"], payload,
                                       customer_limit=1, window_seconds=86400)
    finally:
        if analysis_id:
            remove(store, analysis_id)
        with store.connect() as conn:
            conn.execute("DELETE FROM suppliers WHERE id = %s", (supplier_id,))
            conn.execute("DELETE FROM admission_counters WHERE scope = 'CUSTOMER' AND subject = %s",
                         (str(owner["id"]),))
        remove_user(store, owner["clerk_user_id"])
        remove_user(store, other["clerk_user_id"])


def test_extension_capture_persists_owner_scoped_snapshot_without_queue(store):
    owner = store.resolve_user(f"extension_owner_{uuid4().hex}")
    other = store.resolve_user(f"extension_other_{uuid4().hex}")
    url = "https://detail.1688.com/offer/996518024136.html"
    payload = normalize_capture(DomCapture.model_validate({
        "source_url": url, "offer_id": "996518024136",
        "fields": {"supplier_name": "Visible supplier", "product_title": "Visible dress"},
    }))
    analysis_id = None
    try:
        analysis_id = store.capture_customer_page(
            url, owner["id"], payload, customer_limit=1, window_seconds=86400,
        )
        row = store.get_for_user(analysis_id, owner["id"])
        assert row["status"] == "COMPLETED"
        assert row["mode"] == "EXTENSION_ENHANCED"
        assert row["extraction_method"] == "EXTENSION_DOM"
        assert row["supplier_data"]["products"][0]["title"] == "Visible dress"
        assert row["raw_evidence"]["provenance"] == "USER_PROVIDED_BROWSER_EVIDENCE"
        assert store.get_for_user(analysis_id, other["id"]) is None
        with store.connect() as conn:
            assert conn.execute("SELECT 1 FROM local_queue WHERE analysis_id = %s", (analysis_id,)).fetchone() is None
            assert conn.execute("SELECT 1 FROM analysis_outbox WHERE analysis_id = %s", (analysis_id,)).fetchone() is None
        with pytest.raises(AdmissionDenied):
            store.capture_customer_page(url, owner["id"], payload,
                                        customer_limit=1, window_seconds=86400)
    finally:
        if analysis_id:
            remove(store, analysis_id)
        with store.connect() as conn:
            conn.execute("DELETE FROM admission_counters WHERE scope = 'CUSTOMER' AND subject = %s",
                         (str(owner["id"]),))
        remove_user(store, owner["clerk_user_id"])
        remove_user(store, other["clerk_user_id"])


def test_extension_capture_merges_only_same_owner_page_and_rejects_secrets(store):
    owner = store.resolve_user(f"extension_merge_{uuid4().hex}")
    other = store.resolve_user(f"extension_merge_other_{uuid4().hex}")
    url = "https://detail.1688.com/offer/996518024136.html"
    original = normalize_capture(DomCapture.model_validate({
        "source_url": url, "offer_id": "996518024136",
        "fields": {"supplier_name": "Public supplier", "product_title": "Dress"},
    }))
    original["supplier_data"]["extraction_method"] = "PUBLIC_HTTP"
    original["supplier_data"]["analysis_mode"] = "ACCOUNT_PUBLIC"
    original["supplier_data"]["company_information"] = {"location": "Guangzhou"}
    original["supplier_data"]["reviews"] = [{"text": "Good quality", "source_url": url, "rating": 5}]
    original["reviews"] = original["supplier_data"]["reviews"]
    ids = []
    subject = str(owner["id"])
    client = TestClient(create_app(
        store=store, settings=Settings(store.database_url, "local", None, None, True),
        verifier=HeaderSubjectVerifier(),
    ))
    headers = {"authorization": f"Bearer subject:{owner['clerk_user_id']}"}
    try:
        public_id = store.submit_customer(url, owner["id"], azure=False,
                                          customer_limit=10, window_seconds=86400)
        ids.append(public_id)
        claim = store.claim_processing(public_id, 60, 3)
        store.complete_processing(public_id, claim["token"], original)
        prior = store.get(public_id)
        other_id = store.submit_customer(url, other["id"], azure=False,
                                         customer_limit=10, window_seconds=86400)
        ids.append(other_id)
        other_claim = store.claim_processing(other_id, 60, 3)
        other_payload = json.loads(json.dumps(original))
        other_payload["supplier_data"]["supplier_name"] = "Other owner's supplier"
        other_payload["supplier_data"]["years_active"] = 99
        store.complete_processing(other_id, other_claim["token"], other_payload)
        capture = {"source_url": url, "offer_id": "996518024136",
                   "fields": {"supplier_name": "Current supplier", "price_text": "¥20"}}
        for title in ["password=secret", "Bearer abcdefghijklmnop", "sid=abc123; auth=xyz",
                      "csrftoken=abc123", "ASP.NET_SessionId=abc123"]:
            rejected = client.post("/api/v1/analyses/capture", headers=headers,
                                   json={**capture, "fields": {"product_title": title}})
            assert rejected.status_code == 422
        rejected = client.post("/api/v1/analyses/capture", headers=headers,
                               json={**capture, "cookie": "session=secret"})
        assert rejected.status_code == 422
        unsafe_payload = normalize_capture(DomCapture.model_validate({
            **capture, "fields": {"product_title": "session_token=secret"},
        }))
        with pytest.raises(ValueError, match="sensitive page state"):
            store.capture_customer_page(url, owner["id"], unsafe_payload,
                                        customer_limit=10, window_seconds=86400)
        response = client.post("/api/v1/analyses/capture", headers=headers, json=capture)
        assert response.status_code == 201
        merged_id = UUID(response.json()["id"])
        ids.append(merged_id)
        merged = client.get(f"/api/v1/analyses/{merged_id}", headers=headers).json()
        assert merged["supplier_data"]["supplier_name"] == "Current supplier"
        assert merged["supplier_data"]["company_information"] == {"location": "Guangzhou"}
        assert merged["supplier_data"]["years_active"] is None
        assert merged["supplier_data"]["price_information"] == {"display_text": "¥20"}
        assert len(merged["reviews"]) == 1
        assert merged["raw_evidence"]["merged_from_snapshot_id"] == str(prior["supplier_snapshot_id"])
        assert store.get(public_id)["supplier_data"] == prior["supplier_data"]
        assert store.get_for_user(merged_id, other["id"]) is None
        repeated = client.post("/api/v1/analyses/capture", headers=headers, json=capture)
        assert repeated.status_code == 201
        repeated_id = UUID(repeated.json()["id"])
        ids.append(repeated_id)
        repeated_row = client.get(f"/api/v1/analyses/{repeated_id}", headers=headers).json()
        assert len(repeated_row["reviews"]) == 1
        assert len(repeated_row["supplier_data"]["products"]) == 1
        assert repeated_row["raw_evidence"]["merged_from_snapshot_id"] == merged["supplier_snapshot_id"]
        with store.connect() as conn:
            used = conn.execute("SELECT used FROM admission_counters WHERE scope = 'CUSTOMER' AND subject = %s",
                                (subject,)).fetchone()["used"]
            assert used == 3  # public submission and two accepted captures only
    finally:
        for analysis_id in reversed(ids):
            remove(store, analysis_id)
        with store.connect() as conn:
            conn.execute("DELETE FROM admission_counters WHERE scope = 'CUSTOMER' AND subject IN (%s, %s)",
                         (str(owner["id"]), str(other["id"])))
        remove_user(store, owner["clerk_user_id"])
        remove_user(store, other["clerk_user_id"])


def test_blocked_offer_completes_without_a_snapshot(store):
    url = "https://detail.1688.com/offer/996518024136.html"
    analysis_id = store.submit_local(url)
    blocked = {"source_url": url, "extraction_status": "BLOCKED", "reason": "ACCESS_CHALLENGE"}
    try:
        assert process_local_once(store, compute=lambda _: blocked)
        result = store.get(analysis_id)
        assert result["status"] == "COMPLETED"
        assert result["result"] == blocked
        assert result["supplier_snapshot_id"] is None
        assert result["supplier_data"] is None
        assert result["raw_evidence"] is None
        assert result["reviews"] == []
    finally:
        remove(store, analysis_id)


@pytest.mark.parametrize(("source_failure", "status", "reason", "requests"), [
    (401, "AUTH_REQUIRED", "LOGIN_REQUIRED", 1),
    (403, "BLOCKED", "ACCESS_CHALLENGE", 1),
    (404, "UNSUPPORTED_PAGE", "HTTP_ERROR", 1),
    (503, "PARSE_FAILED", "UPSTREAM_UNAVAILABLE", 3),
    ("timeout", "TIMEOUT", "HTTP_TIMEOUT", 3),
    ("malformed", "PARSE_FAILED", "MALFORMED_PAGE", 1),
    ("raw-nan", "PARSE_FAILED", "MALFORMED_PAGE", 1),
    ("surrogate", "PARSE_FAILED", "MALFORMED_PAGE", 1),
])
def test_owner_polls_one_terminal_source_failure_without_processing_retry(
    store, monkeypatch, source_failure, status, reason, requests,
):
    url = "https://detail.1688.com/offer/996518024136.html"
    owner = store.resolve_user(f"source_failure_owner_{uuid4().hex}")
    other = store.resolve_user(f"source_failure_other_{uuid4().hex}")
    client = TestClient(create_app(
        store=store, settings=Settings(store.database_url, "local", None, None, True),
        verifier=HeaderSubjectVerifier(),
    ))
    headers = {"authorization": f"Bearer subject:{owner['clerk_user_id']}"}
    submitted = client.post("/api/v1/analyses", headers=headers, json={"source_url": url})
    assert submitted.status_code == 202
    analysis_id = UUID(submitted.json()["id"])
    calls, delays = [], []

    def respond(request):
        calls.append(request)
        if source_failure == "timeout":
            raise httpx.ReadTimeout("private exception details")
        if source_failure == "malformed":
            return httpx.Response(200, headers={"content-type": "text/html"}, text=(
                f'<link rel="canonical" href="{url}"><script>}})(window.contextPath,'
                '{"result":{"data":{"productTitle":{"fields":{"rateInfo":{"commonTagNodeList":7}}}}}})</script>'
            ))
        if source_failure in {"raw-nan", "surrogate"}:
            fields = ('{"rateInfo":{"commonTagNodeList":[{"name":"all","count":NaN}]}}'
                      if source_failure == "raw-nan" else '{"title":"\\ud800"}')
            return httpx.Response(200, headers={"content-type": "text/html"}, text=(
                f'<link rel="canonical" href="{url}"><div class="title-content"><h1>Dress</h1></div>'
                '<script>})(window.contextPath,{"result":{"data":{"productTitle":{"fields":'
                + fields + '}}}})</script>'
            ))
        return httpx.Response(source_failure)

    with httpx.Client(transport=httpx.MockTransport(respond)) as source_client:
        monkeypatch.setattr("backend.worker.main.extract_1688", lambda source_url, analysis_mode:
                            extract_1688(source_url, analysis_mode=analysis_mode, client=source_client,
                                         dns_check=lambda _: True, sleep=delays.append))
        try:
            endpoint = f"/api/v1/analyses/{analysis_id}"
            assert client.get(endpoint, headers=headers).json()["status"] == "QUEUED"
            assert process_local_once(store)
            first = client.get(endpoint, headers=headers).json()
            assert first["status"] == "COMPLETED" and first["attempt_count"] == 1
            assert first["result"] == {"source_url": url, "extraction_status": status, "reason": reason}
            assert first["failure_code"] is None and first["next_retry_at"] is None
            assert first["supplier_data"] is None and first["raw_evidence"] is None
            assert first["supplier_snapshot_id"] is None and first["reviews"] == []
            assert [event["status"] for event in first["events"]] == ["QUEUED", "PROCESSING", "COMPLETED"]
            assert len(calls) == requests and delays == ([0.5, 1.0] if requests == 3 else [])
            assert client.get(endpoint, headers=headers).json() == first
            assert client.get(endpoint, headers={
                "authorization": f"Bearer subject:{other['clerk_user_id']}",
            }).status_code == 404
            assert store.complete_processing(analysis_id, uuid4(), first["result"]) == "replay"
            with store.connect() as conn:
                assert conn.execute("SELECT 1 FROM supplier_snapshots WHERE analysis_id = %s", (analysis_id,)).fetchone() is None
                assert conn.execute("SELECT 1 FROM local_queue WHERE analysis_id = %s", (analysis_id,)).fetchone() is None
        finally:
            remove(store, analysis_id)
            remove_user(store, owner["clerk_user_id"])
            remove_user(store, other["clerk_user_id"])


def test_recovered_http_retries_remain_one_processing_attempt(store, monkeypatch):
    url = "https://detail.1688.com/offer/996518024136.html"
    analysis_id = store.submit_local(url)
    calls, delays = [], []

    def respond(request):
        calls.append(request)
        if len(calls) < 3:
            return httpx.Response(503)
        return httpx.Response(200, headers={"content-type": "text/html"}, text=(
            f'<link rel="canonical" href="{url}"><div class="title-content"><h1>Dress</h1></div>'
        ))

    with httpx.Client(transport=httpx.MockTransport(respond)) as source_client:
        monkeypatch.setattr("backend.worker.main.extract_1688", lambda source_url, analysis_mode:
                            extract_1688(source_url, analysis_mode=analysis_mode, client=source_client,
                                         dns_check=lambda _: True, sleep=delays.append))
        try:
            assert process_local_once(store)
            result = store.get(analysis_id)
            assert result["status"] == "COMPLETED" and result["attempt_count"] == 1
            assert result["result"]["extraction_status"] == "PARTIAL"
            assert result["supplier_snapshot_id"]
            assert result["supplier_data"]["products"][0]["title"] == "Dress"
            assert result["supplier_data"]["supplier_name"] is None
            assert result["supplier_data"]["completeness"] == round(1 / 12, 4)
            assert len(calls) == 3 and delays == [0.5, 1.0]
            assert [event["status"] for event in result["events"]] == ["QUEUED", "PROCESSING", "COMPLETED"]
        finally:
            remove(store, analysis_id)


def test_success_without_supplier_evidence_cannot_complete(store):
    url = "https://detail.1688.com/offer/996518024136.html"
    analysis_id = store.submit_local(url)
    try:
        claim = store.claim_processing(analysis_id, 300, 5)
        with pytest.raises(ValueError, match="missing matching supplier evidence"):
            store.complete_processing(
                analysis_id, claim["token"],
                {"source_url": url, "extraction_status": "SUCCESS"},
            )
        assert store.get(analysis_id)["result"] is None
        with store.connect() as conn:
            count = conn.execute(
                "SELECT count(*) AS total FROM supplier_snapshots WHERE analysis_id = %s",
                (analysis_id,),
            ).fetchone()["total"]
        assert count == 0
    finally:
        remove(store, analysis_id)


def test_stale_local_claim_cannot_mutate_newer_lease(store):
    analysis_id = store.submit_local(FIXTURE_URL)
    try:
        old = store.claim_local(10)
        with store.connect() as conn:
            conn.execute(
                "UPDATE local_queue SET claimed_until = now() - interval '1 second' WHERE analysis_id = %s",
                (analysis_id,),
            )
        newer = store.claim_local(10)
        with pytest.raises(LeaseLost):
            store.release_local(analysis_id, old["claim_token"])
        with store.connect() as conn:
            current = conn.execute(
                "SELECT claim_token FROM local_queue WHERE analysis_id = %s", (analysis_id,)
            ).fetchone()["claim_token"]
        assert current == newer["claim_token"]
    finally:
        remove(store, analysis_id)


def test_retry_and_final_transitions_are_ordered_and_sanitized(store):
    analysis_id = store.submit_azure(FIXTURE_URL)
    try:
        first = store.claim_processing(analysis_id, 60, 2)
        assert not store.record_processing_failure(
            analysis_id, first["token"], failure_code="PROCESSING_ERROR",
            max_attempts=2, retry_delay_seconds=0,
        )
        second = store.claim_processing(analysis_id, 60, 2)
        assert store.record_processing_failure(
            analysis_id, second["token"], failure_code="PROCESSING_ERROR",
            max_attempts=2, retry_delay_seconds=0,
        )
        row = store.get(analysis_id)
        assert row["status"] == "FAILED_FINAL"
        assert row["final_disposition"] == "DLQ_PENDING"
        assert [event["status"] for event in row["events"]] == [
            "QUEUED", "PROCESSING", "FAILED_RETRYABLE", "PROCESSING", "FAILED_FINAL"
        ]
        assert all(event["failure_code"] in {None, "PROCESSING_ERROR"} for event in row["events"])
    finally:
        remove(store, analysis_id)


def test_postgres_outbox_backoff_exhaustion_and_observed_delivery_recovery(store):
    analysis_id = store.submit_azure(FIXTURE_URL)
    try:
        first = store.claim_outbox(60, 2)
        assert first["attempts"] == 1
        assert not store.record_outbox_failure(
            analysis_id,
            first["lease_token"],
            max_attempts=2,
            base_backoff_seconds=2,
            max_backoff_seconds=60,
        )
        with store.connect() as conn:
            retry = conn.execute(
                """SELECT state, attempts, lease_token, leased_until,
                          last_error_code, next_attempt_at > now() AS backed_off
                   FROM analysis_outbox WHERE analysis_id = %s""",
                (analysis_id,),
            ).fetchone()
            conn.execute(
                "UPDATE analysis_outbox SET next_attempt_at = now() WHERE analysis_id = %s",
                (analysis_id,),
            )
        assert retry == {
            "state": "PENDING", "attempts": 1, "lease_token": None,
            "leased_until": None, "last_error_code": "OUTBOX_PUBLISH_RETRY",
            "backed_off": True,
        }

        second = store.claim_outbox(60, 2)
        assert second["attempts"] == 2
        assert store.record_outbox_failure(
            analysis_id,
            second["lease_token"],
            max_attempts=2,
            base_backoff_seconds=2,
            max_backoff_seconds=60,
        )
        row = store.get(analysis_id)
        assert row["status"] == "FAILED_FINAL"
        assert row["failure_code"] == "OUTBOX_PUBLISH_EXHAUSTED"
        assert row["final_disposition"] == "PUBLICATION_FAILED"

        store.observe_delivery(analysis_id)
        recovered = store.get(analysis_id)
        assert recovered["status"] == "QUEUED"
        assert recovered["failure_code"] is None
        assert recovered["final_disposition"] is None
        with store.connect() as conn:
            outbox = conn.execute(
                "SELECT state, last_error_code FROM analysis_outbox WHERE analysis_id = %s",
                (analysis_id,),
            ).fetchone()
        assert outbox == {"state": "PUBLISHED", "last_error_code": None}
    finally:
        remove(store, analysis_id)


def test_postgres_subject_mapping_role_reload_and_customer_ownership(store):
    settings = Settings(store.database_url, "local", None, None, True)
    client = TestClient(create_app(store=store, settings=settings, verifier=HeaderSubjectVerifier()))
    subject_one = f"user_{uuid4().hex}"
    subject_two = f"user_{uuid4().hex}"
    one = {"Authorization": f"Bearer subject:{subject_one}"}
    two = {"Authorization": f"Bearer subject:{subject_two}"}
    submitted = client.post("/api/v1/analyses", headers=one, json={"source_url": FIXTURE_URL})
    analysis_id = UUID(submitted.json()["id"])
    try:
        assert client.get(f"/api/v1/analyses/{analysis_id}", headers=two).status_code == 404
        with store.connect() as conn:
            second = conn.execute(
                "SELECT id FROM users WHERE clerk_user_id = %s", (subject_two,)
            ).fetchone()
            conn.execute("UPDATE users SET role = 'INTERNAL_REVIEWER' WHERE id = %s", (second["id"],))
        assert client.get(f"/api/v1/analyses/{analysis_id}", headers=two).status_code == 200
        assert client.post("/api/v1/analyses", headers=two, json={"source_url": FIXTURE_URL}).status_code == 403
    finally:
        remove(store, analysis_id)
        with store.connect() as conn:
            conn.execute("DELETE FROM users WHERE clerk_user_id IN (%s, %s)", (subject_one, subject_two))


def test_configured_azure_service_bus_round_trip(store):
    if os.getenv("VCT_TEST_AZURE") != "true":
        pytest.skip("Set VCT_TEST_AZURE=true and Service Bus settings for live Azure check")
    connection = os.environ["AZURE_SERVICE_BUS_CONNECTION_STRING"]
    name = os.environ["AZURE_SERVICE_BUS_QUEUE"]
    queue = AzureQueue(connection, name)
    settings = Settings(store.database_url, "azure", connection, name, True)
    verifier = StaticVerifier()
    client = TestClient(create_app(store=store, settings=settings, verifier=verifier))
    response = client.post("/api/v1/analyses", json={"source_url": FIXTURE_URL})
    analysis_id = UUID(response.json()["id"])
    try:
        dispatch_outbox_once(store, queue, settings)
        for _ in range(10):
            process_azure_once(store, queue, settings)
            if store.get(analysis_id)["status"] == "COMPLETED":
                break
        assert store.get(analysis_id)["status"] == "COMPLETED"
        assert client.get(f"/api/v1/analyses/{analysis_id}").json()["result"] == fixture_result(FIXTURE_URL)
    finally:
        remove(store, analysis_id)
        remove_user(store, verifier.subject)
