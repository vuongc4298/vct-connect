from dataclasses import replace
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DEVELOPER_MODE", "true")
os.environ.setdefault("DATABASE_URL", "postgresql://unused")
os.environ["QUEUE_TRANSPORT"] = "local"

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.queue import AzureQueue
from backend.worker import main as worker
from scripts.scan_frontend_secrets import scan
from scripts import scan_frontend_secrets, smoke_dev, wait_container_job
from scripts.verify_azure_target import verify


BASE = Settings("postgresql://unused", "azure", None, "vct-analyse", False,
                api_runtime="azure", azure_service_bus_namespace="vct-connect-standard")


def test_azure_runtime_accepts_internal_proxy_without_disabling_auth():
    app = create_app(store=SimpleNamespace(), settings=BASE)
    remote = TestClient(app, client=("198.51.100.7", 4321))
    assert remote.get("/healthz").status_code == 200
    assert remote.post("/api/v1/analyses", json={"source_url": "https://detail.1688.com/offer/123456789012.html"}).status_code == 401
    local_mode = replace(BASE, api_runtime="local", developer_mode=True)
    assert TestClient(create_app(store=SimpleNamespace(), settings=local_mode),
                      client=("198.51.100.7", 4321)).get("/healthz").status_code == 403


def test_azure_runtime_configuration_requires_credentials_and_identity(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    monkeypatch.setenv("API_RUNTIME", "azure")
    monkeypatch.setenv("DEVELOPER_MODE", "false")
    monkeypatch.setenv("QUEUE_TRANSPORT", "azure")
    monkeypatch.setenv("AZURE_SERVICE_BUS_QUEUE", "vct-analyse")
    monkeypatch.setenv("AZURE_SERVICE_BUS_NAMESPACE", "vct-connect-standard")
    monkeypatch.delenv("AZURE_SERVICE_BUS_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("CLERK_SECRET_KEY", raising=False)
    monkeypatch.delenv("CLERK_JWT_KEY", raising=False)
    monkeypatch.setenv("CLERK_ISSUER", "https://example.clerk.accounts.dev")
    monkeypatch.setenv("CLERK_AUTHORIZED_PARTIES", "https://web.example")
    with pytest.raises(ValueError, match="Clerk"):
        Settings.from_env()
    monkeypatch.setenv("CLERK_SECRET_KEY", "test-only-value")
    assert Settings.from_env().api_runtime == "azure"
    monkeypatch.setenv("API_RUNTIME", "worker")
    monkeypatch.delenv("CLERK_SECRET_KEY", raising=False)
    assert Settings.from_env().api_runtime == "worker"
    monkeypatch.setenv("API_RUNTIME", "azure")
    monkeypatch.setenv("DEVELOPER_MODE", "true")
    with pytest.raises(ValueError, match="must not enable"):
        Settings.from_env()


def test_service_bus_namespace_uses_managed_identity(monkeypatch):
    from azure import identity, servicebus

    credential = object()
    captured = {}
    monkeypatch.setattr(identity, "DefaultAzureCredential", lambda: credential)
    monkeypatch.setattr(servicebus, "ServiceBusClient", lambda **kwargs: captured.update(kwargs) or object())
    AzureQueue(None, "vct-analyse", namespace="vct-connect-standard")
    assert captured["credential"] is credential
    assert captured["fully_qualified_namespace"] == "vct-connect-standard.servicebus.windows.net"


def test_finite_job_receives_once_drains_reports_and_never_dispatches_outbox(monkeypatch):
    calls = []
    monkeypatch.setattr(worker.Settings, "from_env", lambda: BASE)
    monkeypatch.setattr(worker, "Store", lambda *_: object())
    monkeypatch.setattr(worker, "AzureQueue", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(worker, "process_azure_once", lambda *_: calls.append("receive") or False)
    monkeypatch.setattr(worker, "process_report_once", lambda *_: calls.append("report") or True)
    monkeypatch.setattr(worker, "dispatch_outbox_once", lambda *_: pytest.fail("Job dispatched outbox"))
    monkeypatch.setenv("WORKER_MODE", "job")
    worker.main()
    assert calls == ["receive", "report"]


def test_finite_job_propagates_failure_for_platform_retry(monkeypatch):
    monkeypatch.setattr(worker.Settings, "from_env", lambda: BASE)
    monkeypatch.setattr(worker, "Store", lambda *_: object())
    monkeypatch.setattr(worker, "AzureQueue", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(worker, "process_azure_once", lambda *_: (_ for _ in ()).throw(RuntimeError("transport")))
    monkeypatch.setenv("WORKER_MODE", "job")
    with pytest.raises(RuntimeError, match="transport"):
        worker.main()


def test_dispatcher_reconnects_after_infrastructure_failure(monkeypatch):
    class EndLoop(BaseException):
        pass

    queue = SimpleNamespace(reconnect=lambda: calls.append("reconnect"))
    calls = []
    monkeypatch.setattr(worker, "dispatch_outbox_once", lambda *_: (_ for _ in ()).throw(RuntimeError("broker")))
    monkeypatch.setattr(worker.time, "sleep", lambda _: (_ for _ in ()).throw(EndLoop()))
    with pytest.raises(EndLoop):
        worker._run_forever(object(), queue, BASE, "dispatcher")
    assert calls == ["reconnect"]


def test_secret_scanner_rejects_configured_and_pattern_leaks(tmp_path: Path):
    artifact = tmp_path / "client.js"
    artifact.write_bytes(b"const x='server-secret-value';")
    assert scan([tmp_path], {"CLERK_SECRET_KEY": b"server-secret-value"})
    artifact.write_bytes(b"Endpoint=sb://example.servicebus.windows.net/;SharedAccessKey=bad")
    assert scan([tmp_path], {})
    artifact.write_bytes(b"const x='pk_test_public';")
    assert scan([tmp_path], {}) == []


def test_secret_scanner_normalizes_quoted_env_values(tmp_path: Path, monkeypatch):
    (tmp_path / ".env").write_text("CLERK_SECRET_KEY='quoted-secret-value'\n", encoding="utf-8")
    monkeypatch.setattr(scan_frontend_secrets, "ROOT", tmp_path)
    assert scan_frontend_secrets.configured_secrets()["CLERK_SECRET_KEY"] == b"quoted-secret-value"


def test_smoke_requires_token_and_exact_fixture(monkeypatch):
    with pytest.raises(AssertionError, match="CLERK_SMOKE_TOKEN"):
        smoke_dev.run("https://web.test", "https://api.test", None, 10)

    class WebResponse:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return b"<html>Safe web page</html>"

    monkeypatch.setattr(smoke_dev, "urlopen", lambda *_args, **_kwargs: WebResponse())
    replies = iter([
        (401, {}), (404, {}), (202, {"id": str(uuid4())}),
        (200, {"status": "COMPLETED", "attempt_count": 1, "result": {"fixture": True}}),
    ])
    monkeypatch.setattr(smoke_dev, "request", lambda *_args, **_kwargs: next(replies))
    with pytest.raises(AssertionError, match="expected fixture result"):
        smoke_dev.run("https://web.test", "https://api.test", "token", 10)


def test_smoke_rejects_unblocked_api_and_web_secret_pattern(monkeypatch):
    class WebResponse:
        status = 200
        def __init__(self, body): self.body = body
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return self.body

    monkeypatch.setattr(smoke_dev, "urlopen", lambda *_args, **_kwargs: WebResponse(b"safe"))
    replies = iter([(401, {}), (503, {})])
    monkeypatch.setattr(smoke_dev, "request", lambda *_args, **_kwargs: next(replies))
    with pytest.raises(AssertionError, match="external ingress"):
        smoke_dev.run("https://web.test", "https://api.test", None, 10, ingress_only=True)
    monkeypatch.setattr(smoke_dev, "urlopen", lambda *_args, **_kwargs: WebResponse(b"sk_live_abcdefghijklmnop"))
    with pytest.raises(AssertionError, match="credential pattern"):
        smoke_dev.run("https://web.test", "https://api.test", None, 10, ingress_only=True)


def test_smoke_accepts_unroutable_internal_api(monkeypatch):
    from urllib.error import URLError

    class WebResponse:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return b"safe"

    def mocked_request(url, **_kwargs):
        if url.startswith("https://api.test"):
            raise URLError("private endpoint has no public route")
        return 401, {}

    monkeypatch.setattr(smoke_dev, "urlopen", lambda *_args, **_kwargs: WebResponse())
    monkeypatch.setattr(smoke_dev, "request", mocked_request)
    smoke_dev.run("https://web.test", "https://api.test", None, 10, ingress_only=True)


def test_guest_smoke_reuses_cookie_session_and_checks_exact_provenance(monkeypatch):
    opener = object()
    monkeypatch.setattr(smoke_dev, "build_opener", lambda *_args: opener)
    calls = []
    replies = iter([
        (202, {"id": "guest-id"}),
        (200, {
            "status": "COMPLETED", "attempt_count": 1,
            "result": smoke_dev.EXPECTED_RESULT,
            "mode": "GUEST_PUBLIC", "actor_type": "GUEST",
            "extraction_method": "FIXTURE", "scoring_version": "v0.1.0",
        }),
    ])

    def mocked_request(url, **kwargs):
        calls.append((url, kwargs))
        return next(replies)

    monkeypatch.setattr(smoke_dev, "request", mocked_request)
    smoke_dev.check_guest_fixture("https://web.test", 10)
    assert [url for url, _ in calls] == [
        "https://web.test/api/v1/guest-analyses",
        "https://web.test/api/v1/guest-analyses/guest-id",
    ]
    assert all(kwargs["opener"] is opener for _, kwargs in calls)
    assert all("token" not in kwargs for _, kwargs in calls)


def test_guest_smoke_rejects_incorrect_provenance(monkeypatch):
    monkeypatch.setattr(smoke_dev, "build_opener", lambda *_args: object())
    replies = iter([
        (202, {"id": "guest-id"}),
        (200, {
            "status": "COMPLETED", "attempt_count": 1,
            "result": smoke_dev.EXPECTED_RESULT,
            "mode": "ACCOUNT_PUBLIC", "actor_type": "GUEST",
            "extraction_method": "FIXTURE", "scoring_version": "v0.1.0",
        }),
    ])
    monkeypatch.setattr(smoke_dev, "request", lambda *_args, **_kwargs: next(replies))
    with pytest.raises(AssertionError, match="fixture or provenance"):
        smoke_dev.check_guest_fixture("https://web.test", 10)


def test_wait_container_job_retries_execution_visibility(monkeypatch):
    calls = []
    def fake_az(*args):
        calls.append(args[0])
        if args[0] == "start":
            return {"name": "migration-1"}
        if calls.count("execution") == 1:
            raise wait_container_job.ExecutionNotVisible("not visible")
        return {"properties": {"status": "Succeeded"}}
    monkeypatch.setattr(wait_container_job, "az", fake_az)
    monkeypatch.setattr(wait_container_job.time, "sleep", lambda _: None)
    monkeypatch.setattr("sys.argv", ["wait_container_job.py", "--timeout", "10"])
    assert wait_container_job.main() == 0
    assert calls == ["start", "execution", "execution"]


def test_azure_worker_releases_busy_delivery_before_renewal_budget():
    analysis_id = uuid4()
    message = SimpleNamespace(message_id=str(analysis_id))
    class Receiver:
        settled = False
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def receive_messages(self, **_): return [message]
        def complete_message(self, _): self.settled = True
    receiver = Receiver()
    queue = SimpleNamespace(receive=lambda: receiver)
    store = SimpleNamespace(
        observe_delivery=lambda _: None,
        claim_processing=lambda *_: {
            "outcome": "busy", "available_at": datetime.now(timezone.utc) + timedelta(hours=1),
        },
    )
    now = [0.0]
    settings = replace(BASE, processing_lease_seconds=30, azure_lock_renewal_seconds=30)
    assert worker.process_azure_once(
        store, queue, settings, clock=lambda: now[0],
        sleep=lambda seconds: now.__setitem__(0, now[0] + seconds),
    )
    assert now[0] <= 15
    assert receiver.settled is False


def test_target_guard_rejects_changed_queue_settings():
    account = {"id": "93bd5d96-c7a2-4072-9aa3-458ab6132d92"}
    group = {"name": "VCT_Connect_Service_Bus", "location": "southeastasia"}
    namespace = {"name": "vct-connect-standard", "location": "southeastasia", "sku": {"name": "Standard"}}
    queue = {"name": "vct-analyse", "status": "Active", "lockDuration": "PT1M",
             "maxDeliveryCount": 10, "requiresDuplicateDetection": False}
    verify(account, group, namespace, queue)
    with pytest.raises(ValueError, match="queue delivery limit"):
        verify(account, group, namespace, {**queue, "maxDeliveryCount": 5})
