"""Independent Linux ownership/fault qualification; opt in inside controlled image.

No skipped case establishes qualification. Faults modify only test-launched
trusted helpers, never the production runner/security policy or its environment.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

import pytest

from backend.app.extraction import browser
from backend.tests.test_browser_fallback import extracted

LINUX = pytest.mark.skipif(
    sys.platform != "linux" or os.getenv("VCT_TEST_BROWSER") != "true",
    reason="Explicit controlled nonroot Linux namespace qualification required",
)


def install_supervisor(monkeypatch, *, runner=None, setup=""):
    """Inject independent faults in the single-threaded test bootstrap."""
    path = str(Path(browser.__file__).with_name("browser_supervisor.py"))
    source = ("import sys, importlib.util\n"
              f"spec=importlib.util.spec_from_file_location('s', {path!r})\n"
              "s=importlib.util.module_from_spec(spec)\nspec.loader.exec_module(s)\n" + setup + "\n")
    if runner is not None:
        source += f"s._runner_command = lambda: [sys.executable, '-c', {runner!r}]\n"
    source += "sys.exit(s.main())\n"
    monkeypatch.setattr(browser, "_bootstrap_command", lambda fd, directory:
                        [sys.executable, "-c", source, str(fd), directory])


def attempt():
    result, html = extracted()
    return browser.render_cached(html, result["source_url"], "1688", "ACCOUNT_PUBLIC", [])


def preserve_attempt(caplog):
    original, html = extracted()
    frozen = deepcopy(original)
    with caplog.at_level("INFO", logger=browser.__name__):
        started = time.monotonic()
        selected = browser.maybe_render(original, html, html.encode(), enabled=True)
        elapsed = time.monotonic() - started
    assert selected is original and original == frozen, caplog.text
    assert elapsed < 11
    return elapsed


def alive(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] not in {"Z", "X"}
    except FileNotFoundError:
        return False


def wait_gone(pids, seconds=1):
    deadline = time.monotonic() + seconds
    while any(alive(pid) for pid in pids) and time.monotonic() < deadline:
        time.sleep(.01)
    assert not any(alive(pid) for pid in pids), pids


@LINUX
def test_cleanup_memory_error_never_retains_attempt_lock(monkeypatch):
    original_spawn = browser._spawn
    original_drain = browser._drain_cleanup
    original_lock = browser._attempt_lock
    drains = 0
    def fail_finally_drain(deadline):
        nonlocal drains
        drains += 1
        if drains == 1:
            return True
        raise MemoryError()
    monkeypatch.setattr(browser, '_restart_reclaim_pending', False)
    # Preserve any earlier deferred slot; the failed spawn creates no real
    # profile/process, so this test's synthetic slot needs no external cleanup.
    monkeypatch.setattr(browser, '_pending_cleanup', None)
    monkeypatch.setattr(browser, '_spawn', lambda *args, **kwargs: (_ for _ in ()).throw(OSError('spawn failed')))
    monkeypatch.setattr(browser, '_drain_cleanup', fail_finally_drain)
    with pytest.raises(MemoryError):
        attempt()
    assert drains == 2
    assert browser._attempt_lock is original_lock
    assert original_lock.acquire(blocking=False)
    original_lock.release()
    monkeypatch.setattr(browser, '_spawn', original_spawn)
    monkeypatch.setattr(browser, '_drain_cleanup', original_drain)


@LINUX
def test_restart_reclamation_removes_dead_worker_profile(tmp_path, monkeypatch):
    from backend.app.extraction import browser_supervisor
    dead = Path('/tmp') / f'vct-browser-999999-1-{("a" * 32)}'
    live = Path('/tmp') / f'vct-browser-{os.getpid()}-{browser_supervisor._process_start_time(os.getpid())}-{"b" * 32}'
    dead.mkdir(exist_ok=False)
    (dead / 'sentinel').write_text('stale')
    live.mkdir(exist_ok=False)
    (live / 'sentinel').write_text('live')
    try:
        assert browser_supervisor._reclaim_profiles() == 0
        assert not dead.exists()
        assert (live / 'sentinel').read_text() == 'live'
    finally:
        if dead.exists():
            import shutil
            shutil.rmtree(dead)
        import shutil
        shutil.rmtree(live)


@LINUX
def test_incremental_ipc_delivers_evidence_beyond_first_64k(caplog):
    from hashlib import sha256
    original, html = extracted()
    html = html.replace('<body>', '<body><!--' + ('x' * 70000) + '-->', 1)
    assert len(html.encode()) > 65536
    assert html.find('shop-company-name') > 65536
    frozen = deepcopy(original)
    started = time.monotonic()
    selected = browser.maybe_render(original, html, html.encode(), enabled=True)
    elapsed = time.monotonic() - started
    assert elapsed < 11
    assert original == frozen
    assert selected['supplier_data']['extraction_method'] == 'PUBLIC_BROWSER', caplog.text
    assert browser.field_count(selected['supplier_data']) > browser.field_count(original['supplier_data'])
    assert selected['raw_payload']['html_sha256'] == sha256(html.encode()).hexdigest()


def lifetime_runner(marker):
    return f"""
import json, os, signal, subprocess, sys, time
from pathlib import Path
def outer():
 return int(next(x for x in Path('/proc/self/status').read_text().splitlines() if x.startswith('NSpid:')).split()[1])
def parent(pid):
 return int(Path(f'/proc/{{pid}}/stat').read_text().rsplit(')',1)[1].split()[1])
pid=outer(); init=parent(pid); bootstrap=parent(init)
child_source="from pathlib import Path; import os,signal,time; p=int(next(x for x in Path('/proc/self/status').read_text().splitlines() if x.startswith('NSpid:')).split()[1]); Path(" + repr({str(marker) + '.child'!r}) + ").write_text(str(p)); os.kill(os.getpid(),signal.SIGSTOP); time.sleep(60)"
child=subprocess.Popen([sys.executable,'-c',child_source],start_new_session=True)
end=time.monotonic()+2
while not Path({str(marker) + '.child'!r}).exists() and time.monotonic()<end: time.sleep(.01)
descendant=int(Path({str(marker) + '.child'!r}).read_text())
Path({str(marker)!r}).write_text(json.dumps(dict(runner=pid,init=init,bootstrap=bootstrap,
 worker=parent(bootstrap),descendant=descendant,directory=os.environ['HOME'])))
time.sleep(60)
"""


@LINUX
def test_actual_bootstrap_death_before_init_arming_never_launches(monkeypatch, tmp_path, caplog, cleanup_slot):
    marker = tmp_path / 'pre-arm'
    launched = tmp_path / 'runner-launched'
    setup = f"""
import json, os, time
from pathlib import Path
marker=Path({str(marker)!r})
arm=Path(str(marker)+'.arm')
boundary=Path(str(marker)+'.boundary')
resume=Path(str(marker)+'.resume')
prctl=s._prctl
def delayed_arm(option,value):
 if os.getpid()==1 and option==1:
  arm.touch()
  cutoff=time.monotonic()+2
  while not resume.exists() and time.monotonic()<cutoff: time.sleep(.005)
 return prctl(option,value)
s._prctl=delayed_arm
send=s._send
def record_owner(control,**message):
 send(control,**message)
 if message.get('kind')=='OWNER':
  marker.write_text(json.dumps(dict(bootstrap=os.getpid(),init=message['pid'])))
s._send=record_owner
recv=s.socket.socket.recv
def record_wait(channel,*args):
 if os.getpid()!=1: boundary.touch()
 return recv(channel,*args)
s.socket.socket.recv=record_wait
# Also reaches the old one-way gate after its buffered release. This makes
# the injection reproduce the pre-fix launch rather than killing before it.
write=s.os.write
def record_release(fd,data):
 result=write(fd,data)
 if data==b'1': boundary.touch()
 return result
s.os.write=record_release
"""
    install_supervisor(monkeypatch, setup=setup,
                       runner=f"from pathlib import Path;Path({str(launched)!r}).touch();print('{{\"code\":\"NO_GAIN\"}}')")
    data, errors = [], []
    def kill_before_arm():
        try:
            cutoff = time.monotonic() + 8
            while (not marker.exists() or not Path(str(marker) + '.arm').exists()
                   or not Path(str(marker) + '.boundary').exists()) and time.monotonic() < cutoff:
                time.sleep(.005)
            observed = json.loads(marker.read_text())
            data.append(observed)
            handle = os.pidfd_open(observed['bootstrap'])
            try:
                signal.pidfd_send_signal(handle, signal.SIGKILL)
            finally:
                os.close(handle)
            Path(str(marker) + '.resume').touch()
        except BaseException as error:
            errors.append(error)
    killer = threading.Thread(target=kill_before_arm)
    sentinel = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(60)'])
    try:
        killer.start()
        elapsed = preserve_attempt(caplog)
        killer.join(timeout=1)
        assert not killer.is_alive() and not errors, errors
        assert data
        wait_gone(list(data[0].values()))
        assert not launched.exists()
        assert sentinel.poll() is None
        print(json.dumps(dict(probe='pre-arm-bootstrap-death', elapsed=elapsed,
                              owned=data[0], owned_alive=False, runner_launched=False, sentinel_alive=True)))
    finally:
        sentinel.kill()
        sentinel.wait(timeout=1)
        killer.join(timeout=1)


@LINUX
@pytest.mark.parametrize("target", ["init", "bootstrap"])
def test_actual_owner_and_bootstrap_death_chain(monkeypatch, tmp_path, target, caplog, cleanup_slot):
    marker = tmp_path / "lifetime"
    install_supervisor(monkeypatch, runner=lifetime_runner(marker))
    data, errors = [], []
    def kill_owner():
        try:
            cutoff = time.monotonic() + 8
            while not marker.exists() and time.monotonic() < cutoff:
                time.sleep(.01)
            observed = json.loads(marker.read_text())
            data.append(observed)
            fd = os.pidfd_open(observed[target])
            try:
                signal.pidfd_send_signal(fd, signal.SIGKILL)
            finally:
                os.close(fd)
        except BaseException as error:
            errors.append(error)
    killer = threading.Thread(target=kill_owner)
    sentinel = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        killer.start()
        elapsed = preserve_attempt(caplog)
        killer.join(timeout=1)
        assert not killer.is_alive() and not errors, errors
        assert data
        wait_gone([data[0][name] for name in ("runner", "init", "bootstrap", "descendant")])
        assert sentinel.poll() is None
        assert "code=RUNTIME_FAILED" in caplog.text
        if browser._pending_cleanup is not None:
            assert browser._drain_cleanup(time.monotonic() + 3)
        assert not Path(data[0]["directory"]).exists()
        print(json.dumps(dict(probe="death-chain", target=target, elapsed=elapsed,
                              owned=data[0], owned_alive=False, sentinel_alive=True, profiles_clean=True)))
    finally:
        sentinel.kill()
        sentinel.wait(timeout=1)
        killer.join(timeout=1)


@LINUX
def test_actual_outer_parent_death_terminates_namespace(monkeypatch, tmp_path):
    marker = tmp_path / "parent-death"
    install_supervisor(monkeypatch, runner=lifetime_runner(marker))
    command = browser._bootstrap_command(999, "unused")
    source = ("from backend.app.extraction import browser as b\n"
              f"b._bootstrap_command=lambda fd,d: {command[:3]!r}+[str(fd),d]\n"
              "b.render_cached('<html></html>','https://detail.1688.com/offer/123.html','1688','ACCOUNT_PUBLIC',[])\n")
    worker = subprocess.Popen([sys.executable, "-c", source], cwd=Path(browser.__file__).resolve().parents[3],
                              env=browser._environment("/tmp"), stdin=subprocess.DEVNULL,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sentinel = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    observed = None
    try:
        cutoff = time.monotonic() + 8
        while not marker.exists() and time.monotonic() < cutoff and worker.poll() is None:
            time.sleep(.01)
        observed = json.loads(marker.read_text())
        handle = os.pidfd_open(worker.pid)
        try:
            signal.pidfd_send_signal(handle, signal.SIGKILL)
        finally:
            os.close(handle)
        worker.wait(timeout=1)
        wait_gone([observed[name] for name in ("runner", "init", "bootstrap", "descendant")])
        assert sentinel.poll() is None
        # Production recovery must occur in a fresh worker through the public
        # entry point, without draining the old worker's private cleanup slot.
        assert Path(observed['directory']).exists()
        recovery = """
import json
from copy import deepcopy
from hashlib import sha256
from backend.app.extraction import browser as b
from backend.tests.test_browser_fallback import extracted
original, html = extracted()
frozen = deepcopy(original)
selected = b.maybe_render(original, html, html.encode(), enabled=True)
assert original == frozen
assert selected['supplier_data']['extraction_method'] == 'PUBLIC_BROWSER'
assert b.field_count(selected['supplier_data']) > b.field_count(original['supplier_data'])
assert b.preserves(original['supplier_data'], selected['supplier_data'])
assert selected['raw_payload']['html_sha256'] == sha256(html.encode()).hexdigest()
assert len(selected['raw_payload']['rendered_html_sha256']) == 64
print(json.dumps(dict(gained=True, original_http_preserved=True)))
"""
        replacement = subprocess.run([sys.executable, '-c', recovery],
            cwd=Path(browser.__file__).resolve().parents[3], env=browser._environment('/tmp'),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        assert replacement.returncode == 0, replacement.stderr.decode()
        assert json.loads(replacement.stdout) == dict(gained=True, original_http_preserved=True)
        assert not Path(observed['directory']).exists()
        assert sentinel.poll() is None
        print(json.dumps(dict(probe="outer-parent-death", owned=observed, owned_alive=False,
                              sentinel_alive=True, interrupted_profile_reclaimed=True, subsequent_gain=True)))
    finally:
        if worker.poll() is None:
            worker.kill()
            worker.wait(timeout=1)
        sentinel.kill()
        sentinel.wait(timeout=1)
        if observed is not None:
            # Failure-only test hygiene; never counted as production recovery.
            subprocess.run(browser._cleanup_command(observed["directory"]), timeout=3, check=True)


@pytest.fixture
def cleanup_slot():
    yield
    if sys.platform == "linux" and browser._pending_cleanup is not None:
        assert browser._drain_cleanup(time.monotonic() + 2), browser._pending_cleanup


def test_non_linux_declines_without_launch(monkeypatch):
    monkeypatch.setattr(browser.sys, "platform", "win32")
    monkeypatch.setattr(browser.subprocess, "Popen", lambda *a, **kw: pytest.fail("Unsafe launch"))
    assert attempt() == {"code": "RUNTIME_UNAVAILABLE"}


@LINUX
def test_actual_owner_nonzero_ids_and_no_capabilities(monkeypatch):
    install_supervisor(monkeypatch, runner="""
import json, os
from pathlib import Path
assert os.geteuid() == os.getegid() == 10001
assert os.getpid() > 1
assert 'CapEff:\\t0000000000000000' in Path('/proc/self/status').read_text()
print(json.dumps({'code':'NO_GAIN'}))
""")
    profiles = set(Path("/tmp").glob("vct-browser-*"))
    assert attempt() == {"code": "NO_GAIN"}
    assert set(Path("/tmp").glob("vct-browser-*")) == profiles


@LINUX
@pytest.mark.parametrize("failure", ["unshare", "maps", "caps", "ready", "pidfd", "signal",
                                    "owner_pidfd", "owner_signal", "ack", "control_limit"])
def test_actual_denied_prerequisite_never_launches(monkeypatch, tmp_path, failure, cleanup_slot):
    marker = tmp_path / "runner-launched"
    setup = ""
    if failure in {"unshare", "maps", "caps"}:
        name = {"unshare": "_unshare", "maps": "_map_ids", "caps": "_drop_capabilities"}[failure]
        setup = f"def deny(*a): raise PermissionError('injected')\ns.{name}=deny"
    elif failure == "ready":
        setup = "s._send_original=s._send\ndef send(c, **m):\n if m.get('kind')=='READY': m['uid']=0\n s._send_original(c, **m)\ns._send=send"
    elif failure == "control_limit":
        setup = "s._send_original=s._send\ndef send(c, **m):\n if m.get('kind')=='READY': m['pad']='x'*1000\n s._send_original(c, **m)\ns._send=send"
    install_supervisor(monkeypatch, setup=setup,
                       runner=f"from pathlib import Path; Path({str(marker)!r}).touch()")
    if failure in {"pidfd", "signal", "owner_pidfd", "owner_signal"}:
        module, attribute = (os, "pidfd_open") if failure.endswith("pidfd") else (signal, "pidfd_send_signal")
        original = getattr(module, attribute)
        calls = 0
        def deny(*args, **kwargs):
            nonlocal calls
            calls += 1
            if ((failure.startswith("owner_") and calls == 3)
                    or failure == "pidfd" or (failure == "signal" and args[1] == 0)):
                raise PermissionError("injected")
            return original(*args, **kwargs)
        monkeypatch.setattr(module, attribute, deny)
    elif failure == "ack":
        original = browser.socket.socket.send
        def deny_ack(channel, data, *args):
            if data == b"ACK":
                raise PermissionError("injected")
            return original(channel, data, *args)
        monkeypatch.setattr(browser.socket.socket, "send", deny_ack)
    profiles = set(Path("/tmp").glob("vct-browser-*"))
    assert attempt() == {"code": "RUNTIME_UNAVAILABLE"}
    assert not marker.exists()
    assert set(Path("/tmp").glob("vct-browser-*")) == profiles


@LINUX
@pytest.mark.parametrize("frozen", [False, True])
def test_actual_abrupt_runner_death_owns_reparented_sessions(monkeypatch, tmp_path, frozen, caplog, cleanup_slot):
    marker = tmp_path / "descendants"
    runner = f"""
import os, signal, time
from pathlib import Path
def outer_pid():
 return int(next(x for x in Path('/proc/self/status').read_text().splitlines() if x.startswith('NSpid:')).split()[1])
if os.fork() == 0:
 os.setsid()
 if os.fork() != 0: os._exit(0)
 Path({str(marker)!r}).write_text(str(outer_pid()))
 if {frozen!r}: os.kill(os.getpid(), signal.SIGSTOP)
 time.sleep(60)
 os._exit(0)
end=time.monotonic()+1
while not Path({str(marker)!r}).exists() and time.monotonic()<end: time.sleep(.01)
os.kill(os.getpid(), signal.SIGKILL)
"""
    install_supervisor(monkeypatch, runner=runner)
    sentinel = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)
    try:
        elapsed = preserve_attempt(caplog)
        pid = int(marker.read_text())
        wait_gone([pid])
        assert sentinel.poll() is None
        assert "code=RUNTIME_FAILED" in caplog.text
        print(json.dumps(dict(probe="runner-death", frozen=frozen, elapsed=elapsed,
                              descendant_pid=pid, owned_alive=alive(pid), sentinel_alive=True)))
    finally:
        sentinel.kill()
        sentinel.wait(timeout=1)


@LINUX
@pytest.mark.parametrize("operation", ["mkdir", "delete", "ready", "stdout", "proc"])
def test_actual_independent_stalls_bound_outer_deadline(monkeypatch, operation, caplog, cleanup_slot):
    setup = "import time\n"
    runner = "import json; print(json.dumps({'code':'NO_GAIN'}))"
    if operation == "mkdir":
        setup += "s.mkdir_original=s.os.mkdir\ndef mkdir(*a, **kw):\n time.sleep(12)\n return s.mkdir_original(*a, **kw)\ns.os.mkdir=mkdir"
    elif operation == "delete":
        setup += "s.cleanup_original=s._cleanup_profile\ndef cleanup(p):\n time.sleep(12)\n s.cleanup_original(p)\ns._cleanup_profile=cleanup"
    elif operation == "ready":
        setup += "s._send_original=s._send\ndef send(c, **m):\n if m.get('kind')=='READY': time.sleep(12)\n s._send_original(c, **m)\ns._send=send"
    elif operation == "stdout":
        runner = "import sys,time; sys.stdout.write('{'); sys.stdout.flush(); time.sleep(12)"
    else:
        # Independent regression: caller must not perform the old three walks.
        def denied_walk(*args):
            pytest.fail("Worker attempted ancestry-based process inspection")
        monkeypatch.setattr(browser.Path, "iterdir", denied_walk)
        setup += "s.iter_original=s.Path.iterdir\ndef walk(p):\n time.sleep(4)\n return s.iter_original(p)\ns.Path.iterdir=walk"
        runner = "import os,signal; os.kill(os.getpid(),signal.SIGKILL)"
    install_supervisor(monkeypatch, runner=runner, setup=setup)
    profiles = set(Path("/tmp").glob("vct-browser-*"))
    elapsed = preserve_attempt(caplog)
    assert ("code=RUNTIME_UNAVAILABLE" if operation == "ready" else
            "code=RUNTIME_FAILED" if operation == "proc" else "code=DEADLINE") in caplog.text
    deferred = browser._pending_cleanup is not None
    if deferred:
        assert browser._drain_cleanup(time.monotonic() + 3)
    assert set(Path("/tmp").glob("vct-browser-*")) == profiles
    print(json.dumps(dict(probe="stall", operation=operation, elapsed=elapsed,
                          profiles_clean=True, deferred_cleanup=deferred)))


@LINUX
@pytest.mark.parametrize("output,expected", [("b'x'*(2_000_000+100_000)", "OUTPUT_LIMIT"),
                                           ("b'{bad'", "INVALID_OUTPUT"),
                                           ("b'[]'", "INVALID_OUTPUT"),
                                           ("b'{\"code\":[]}'", "INVALID_OUTPUT"),
                                           ("b'{\"code\":{}}'", "INVALID_OUTPUT")])
def test_actual_bounded_malformed_output(monkeypatch, output, expected, cleanup_slot):
    runner = f"import os,time; data={output}; os.write(1,data); time.sleep(.1)"
    install_supervisor(monkeypatch, runner=runner)
    received = []
    original = browser.os.read
    def bounded(fd, size):
        chunk = original(fd, size)
        received.append(len(chunk))
        return chunk
    monkeypatch.setattr(browser.os, "read", bounded)
    assert attempt() == {"code": expected}
    # Includes subprocess' empty exec-error-pipe receipt; no full output buffer.
    assert sum(received) <= browser.MAX_BYTES + 1


@LINUX
def test_actual_stuck_cleanup_caps_backlog(monkeypatch, caplog, cleanup_slot):
    install_supervisor(monkeypatch, setup="import time\ns._cleanup_profile=lambda p: time.sleep(12)",
                       runner="print('{\"code\":\"NO_GAIN\"}')")
    cleanup_original = browser._cleanup_command
    monkeypatch.setattr(browser, "_cleanup_command", lambda directory:
                        [sys.executable, "-c", "import time; time.sleep(12)"])
    profiles = set(Path("/tmp").glob("vct-browser-*"))
    preserve_attempt(caplog)
    pending_directory = browser._pending_cleanup["directory"]
    for _ in range(3):
        assert attempt() == {"code": "RUNTIME_UNAVAILABLE"}
        assert browser._pending_cleanup["directory"] == pending_directory
        assert len(set(Path("/tmp").glob("vct-browser-*")) - profiles) == 1
    monkeypatch.setattr(browser, "_cleanup_command", cleanup_original)
    time.sleep(.05)
    assert browser._drain_cleanup(time.monotonic() + 2)
    assert set(Path("/tmp").glob("vct-browser-*")) == profiles


@LINUX
def test_actual_deferred_cleanup_recovers_through_normal_entry_and_gains(monkeypatch, caplog, cleanup_slot):
    from hashlib import sha256
    bootstrap = browser._bootstrap_command
    cleanup = browser._cleanup_command
    profiles = set(Path('/tmp').glob('vct-browser-*'))
    # Healthy deletion needs 0.7 seconds, longer than the old repeated window.
    def delayed_cleanup(directory):
        command = cleanup(directory)
        return [sys.executable, '-c',
                "import runpy,sys,time;time.sleep(.7);sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name='__main__')",
                *command[1:]]
    monkeypatch.setattr(browser, '_cleanup_command', delayed_cleanup)
    install_supervisor(monkeypatch, setup='import time\ns._cleanup_profile=lambda p: time.sleep(12)',
                       runner='print(\'{"code":"NO_GAIN"}\')')
    preserve_attempt(caplog)
    assert browser._pending_cleanup is not None
    directory = browser._pending_cleanup['directory']
    monkeypatch.setattr(browser, '_bootstrap_command', bootstrap)
    original, html = extracted()
    frozen = deepcopy(original)
    started = time.monotonic()
    selected = browser.maybe_render(original, html, html.encode(), enabled=True)
    elapsed = time.monotonic() - started
    assert elapsed < 11
    assert selected['supplier_data']['extraction_method'] == 'PUBLIC_BROWSER', caplog.text
    assert browser.field_count(selected['supplier_data']) > browser.field_count(original['supplier_data'])
    assert browser.preserves(original['supplier_data'], selected['supplier_data'])
    assert original == frozen
    assert selected['raw_payload']['html_sha256'] == sha256(html.encode()).hexdigest()
    assert len(selected['raw_payload']['rendered_html_sha256']) == 64
    assert browser._pending_cleanup is None and not Path(directory).exists()
    assert set(Path('/tmp').glob('vct-browser-*')) == profiles
    print(json.dumps(dict(probe='automatic-cleanup-recovery', deletion_delay=.7, elapsed=elapsed,
                          gained=True, original_http_preserved=True, profiles_clean=True)))


def allocation_runner(marker, *, kernel=False):
    # Instrument actual native main exception handling, not a fake finite code.
    return f"""
import os, resource, sys
from pathlib import Path
from backend.app.extraction import browser_runner as r
async def allocate(request):
 if not {kernel!r}: resource.setrlimit(resource.RLIMIT_AS, (256*1024**2,256*1024**2))
 try:
  data=bytearray({1200 if kernel else 384}*1024**2)
  for i in range(0,len(data),4096): data[i]=1
 except MemoryError:
  Path({str(marker)!r}).write_text('MemoryError')
  raise
r.render=allocate
r.main()
"""


@LINUX
def test_actual_allocation_refusal_preserves_http(monkeypatch, tmp_path, caplog, cleanup_slot):
    marker = tmp_path / "allocation-refused"
    install_supervisor(monkeypatch, runner=allocation_runner(marker))
    elapsed = preserve_attempt(caplog)
    assert marker.read_text() == "MemoryError"
    assert "code=RUNTIME_FAILED" in caplog.text
    print(json.dumps(dict(probe="allocation-refusal", elapsed=elapsed, observed="MemoryError")))


@LINUX
@pytest.mark.skipif(os.getenv("VCT_TEST_BROWSER_OOM") != "true", reason="Destructive shared-cgroup OOM probe runs in a disposable container separately")
def test_actual_kernel_oom_preserves_http(monkeypatch, tmp_path, caplog, cleanup_slot):
    events = Path("/sys/fs/cgroup/memory.events")
    def observed():
        return dict((k, int(v)) for k, v in (line.split() for line in events.read_text().splitlines()))
    before = observed()
    install_supervisor(monkeypatch, runner=allocation_runner(tmp_path / "oom", kernel=True))
    elapsed = preserve_attempt(caplog)
    after = observed()
    assert after["oom"] > before["oom"] and after["oom_kill"] > before["oom_kill"]
    assert "code=RUNTIME_FAILED" in caplog.text or "code=DEADLINE" in caplog.text
    print(json.dumps(dict(probe="kernel-oom", elapsed=elapsed,
                          peak=Path("/sys/fs/cgroup/memory.peak").read_text().strip(),
                          events_before=before, events_after=after, caller_survived=True)))
