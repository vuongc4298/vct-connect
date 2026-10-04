"""Opt-in, HTTP-first selection of strictly improved public DOM evidence.

Cached HTML lives only in memory. Browser output consists of adapter-selected
fields and finite diagnostics, never page state or a retained HTML document.
"""
from copy import deepcopy
from hashlib import sha256
import json
import logging
import os
from pathlib import Path
import re
import selectors
import signal
import socket
import subprocess
import sys
import threading
import time
from uuid import uuid4

from .contracts import EVIDENCE_FIELDS, evidence_present

MAX_BYTES = 2_000_000
BUDGET_SECONDS = 10
VERSION = "public-browser.v1"
log = logging.getLogger(__name__)

# Only fields for which the existing audited adapters read DOM evidence.
DOM_FIELDS = {
    "1688": {"supplier_name": ("shop-company-name",), "products": ("title-content",),
             "reviews": ("evaluation-item", "review-item", "comment-item", "od-evaluation-item", "data-review-id")},
    "TAOBAO": {"products": ("ItemTitle--", "mainTitle--", "shopProductShelfArea--", "shop-item-card"),
               "reviews": ("Comments--", "content--"), "delivery_information": ("shopName--", "storeLabelItem--")},
    "ALIBABA": {"reviews": ("product-review", "product-review-list"),
                "company_information": ("company-card",), "categories": ("menu-link", "productgrouplist-"),
                "products": ("productCategories", "product-detail/")},
}
CODES = frozenset({"DISABLED", "INELIGIBLE_STATUS", "INELIGIBLE_MODE", "INVALID_EVIDENCE", "ENOUGH_FIELDS",
                   "NO_DOM_SIGNAL", "INPUT_LIMIT", "RUNTIME_UNAVAILABLE", "RUNTIME_FAILED", "DEADLINE",
                   "DOM_LIMIT", "OUTPUT_LIMIT", "INVALID_OUTPUT", "ACCESS_WALL", "NO_GAIN", "CONFLICT", "GAIN"})


def present(value):
    # Browser eligibility/gain excludes empty objects in addition to the v1 rule.
    return evidence_present(value) and value != {}


def field_count(data):
    return sum(present(data.get(name)) for name in EVIDENCE_FIELDS)


def eligibility(result, html, *, enabled):
    if not enabled:
        return "DISABLED"
    if result.get("extraction_status") != "PARTIAL":
        return "INELIGIBLE_STATUS"
    data = result.get("supplier_data") or {}
    if data.get("analysis_mode") not in {"GUEST_PUBLIC", "ACCOUNT_PUBLIC"}:
        return "INELIGIBLE_MODE"
    if (data.get("extraction_method") != "PUBLIC_HTTP" or data.get("source_url") != result.get("source_url")
            or data.get("platform") not in DOM_FIELDS or not isinstance(result.get("raw_payload"), dict)):
        return "INVALID_EVIDENCE"
    if len(html.encode("utf-8")) > MAX_BYTES:
        return "INPUT_LIMIT"
    if field_count(data) >= 6:
        return "ENOUGH_FIELDS"
    tokens = [token for name, values in DOM_FIELDS[data["platform"]].items() if not present(data.get(name)) for token in values]
    if not tokens:
        return "NO_DOM_SIGNAL"
    from .dom import tree as _tree, scripts as _scripts
    lexical = re.compile(r'''//[^\r\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`''')
    for script in _scripts(_tree(html)):
        content = script.text()
        strings = []
        def mask(match):
            if not match[0].startswith(("//", "/*")):
                strings.append(match[0])
            return " " * len(match[0])
        code = lexical.sub(mask, content)
        write = re.search(r"\b(?:document\s*\.\s*(?:write|writeln|createElement)|[\w.)\]]+\s*\.\s*(?:insertAdjacentHTML|appendChild|append|prepend|replaceChildren))\s*\(|\.\s*(?:innerHTML|outerHTML|textContent)\s*=(?!=)", code)
        if write and any(token in literal for literal in strings for token in tokens):
            return None
    return "NO_DOM_SIGNAL"


def preserves(before, after):
    for name in ("contract_version", "platform", "source_url", "offer_id", "platform_supplier_id", "analysis_mode"):
        if present(before.get(name)) and before.get(name) != after.get(name):
            return False
    for name in EVIDENCE_FIELDS:
        old, new = before.get(name), after.get(name)
        if not present(old):
            continue
        if name in {"reviews", "products"} and isinstance(old, list) and isinstance(new, list):
            if not all(item in new for item in old):
                return False
        elif old != new:
            return False
    return True


def access_wall(html):
    # Rendering never receives a visible access wall even if the source also
    # included sparse, identity-bound public metadata. Scripts are not text.
    from .dom import tree as _tree, prune_dom as _prune_dom, visibility_exhausted, access_text
    tree = _tree(html)
    if visibility_exhausted(tree):
        return 'PARSE_FAILED'
    _prune_dom(tree)
    title = tree.css_first("title")
    body = tree.css_first("body")
    def visible_text(node):
        if node is None:
            return ""
        # selectolax otherwise concatenates adjacent text nodes across BR/block
        # boundaries. Access phrases such as "Please<br>sign in" must keep a
        # boundary after the visibility pass has removed hidden content.
        return access_text(node)

    title_text = visible_text(title).lower()
    text = title_text + " " + visible_text(body).lower()[:2000]
    if re.search(r"captcha|verify you are human|security verification|access denied|滑动验证|安全验证|请输入验证码|访问受限", text):
        return "BLOCKED"
    if (re.search(r"login required|please log in|please sign in|登录后|请登录", text)
            or title_text.strip() in {"login", "sign in", "登录", "用户登录", "会员登录", "1688登录"}):
        return "AUTH_REQUIRED"
    return None


def _environment(directory):
    # An allowlist, not a copy of backend environment variables. The runner
    # cannot inherit database, queue, Clerk, Azure, proxy or telemetry secrets.
    env = {"PATH": os.defpath, "HOME": directory, "TMPDIR": directory,
           "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"}
    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        env["PLAYWRIGHT_BROWSERS_PATH"] = os.environ["PLAYWRIGHT_BROWSERS_PATH"]
    return env


_attempt_lock = threading.Lock()
_pending_cleanup = None
_restart_reclaim_pending = True
CONTROL_BYTES = 512
CLEANUP_RESERVE = .5


def _bootstrap_command(control_fd, directory):
    # Execute the stdlib-only file directly. Importing the extraction package
    # would load every HTTP adapter into a supposedly small trusted helper.
    return [sys.executable, str(Path(__file__).with_name("browser_supervisor.py")), str(control_fd), directory]


def _cleanup_command(directory):
    return [sys.executable, str(Path(__file__).with_name("browser_supervisor.py")), "--cleanup", directory]


def _reclaim_command():
    return [sys.executable, str(Path(__file__).with_name("browser_supervisor.py")), "--reclaim"]


def _spawn(command, directory, **kwargs):
    return subprocess.Popen(command, cwd=Path(__file__).resolve().parents[3],
                            env=_environment(directory), stderr=subprocess.DEVNULL,
                            start_new_session=True, **kwargs)


def _signal(handle):
    if handle is not None:
        try:
            signal.pidfd_send_signal(handle, signal.SIGKILL)
            return True
        except OSError:
            # Control closure and bootstrap death independently terminate init.
            pass
    return False


def _drain_cleanup(deadline):
    """One retained cleanup slot; never accumulate helpers or stale profiles.

    Filesystem operations run in a disposable child. A stuck helper prevents
    new attempts until it exits and the known directory is successfully deleted.
    No worker-side filesystem walk or unbounded process wait is permitted.
    """
    global _pending_cleanup
    if _pending_cleanup is None:
        return True
    pending = _pending_cleanup
    bootstrap = pending["bootstrap"]
    if bootstrap is not None and bootstrap.poll() is None:
        return False
    helper = pending["helper"]
    if helper is not None and pending.get("stopping") and helper.poll() is None:
        try:
            helper.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            return False
    if helper is not None and helper.poll() is not None:
        if helper.returncode == 0:
            _pending_cleanup = None
            return True
        pending["helper"] = helper = None
        pending["stopping"] = False
    if helper is None and time.monotonic() < deadline:
        try:
            helper = _spawn(_cleanup_command(pending["directory"]), pending["directory"],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            pending["helper"] = helper
        except OSError:
            return False
    if helper is not None:
        try:
            helper.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            try:
                helper.kill()
            except OSError:
                pass
            pending["stopping"] = True
            return False
        if helper.returncode == 0:
            _pending_cleanup = None
            return True
    return False


def _process_start_time(pid):
    tail = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    return int(tail[19])


def _reclaim_restart_profiles(deadline):
    """Run one bounded orphan scan after each worker process starts."""
    global _restart_reclaim_pending
    if not _restart_reclaim_pending:
        return True
    helper = None
    try:
        helper = _spawn(_reclaim_command(), "/tmp", stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        helper.wait(timeout=max(0, min(2., deadline - time.monotonic())))
        if helper.returncode == 0:
            _restart_reclaim_pending = False
            return True
    except (OSError, subprocess.TimeoutExpired):
        pass
    finally:
        if helper is not None and helper.poll() is None:
            try:
                helper.kill()
            except OSError:
                pass
            try:
                helper.wait(timeout=max(0, min(.1, deadline - time.monotonic())))
            except subprocess.TimeoutExpired:
                pass
    return False


def _receive(process, control, request, cutoff, handles):
    """Nonblocking bounded receipt, including the ownership handshake."""
    output = bytearray()
    owner = ready = acknowledged = eof = False
    offset = 0
    with selectors.DefaultSelector() as poller:
        control.setblocking(False)
        os.set_blocking(process.stdin.fileno(), False)
        os.set_blocking(process.stdout.fileno(), False)
        poller.register(control, selectors.EVENT_READ, "control")
        poller.register(process.stdout, selectors.EVENT_READ, "output")
        while time.monotonic() < cutoff:
            for key, _ in poller.select(max(0, min(.05, cutoff - time.monotonic()))):
                if key.data == "control":
                    raw = control.recv(CONTROL_BYTES + 1)
                    if not raw:
                        poller.unregister(control)
                        if not acknowledged:
                            return {"code": "RUNTIME_UNAVAILABLE"}
                        continue
                    if len(raw) > CONTROL_BYTES:
                        return {"code": "RUNTIME_UNAVAILABLE"}
                    try:
                        message = json.loads(raw)
                    except (ValueError, UnicodeError, RecursionError):
                        return {"code": "RUNTIME_UNAVAILABLE"}
                    if not isinstance(message, dict):
                        return {"code": "RUNTIME_UNAVAILABLE"}
                    if message.get("kind") == "OWNER" and not owner:
                        pid = message.get("pid")
                        if type(pid) is not int or pid <= 1 or pid == process.pid:
                            return {"code": "RUNTIME_UNAVAILABLE"}
                        try:
                            handles["owner"] = os.pidfd_open(pid)
                            signal.pidfd_send_signal(handles["owner"], 0)
                        except OSError:
                            return {"code": "RUNTIME_UNAVAILABLE"}
                        owner = True
                    elif message.get("kind") == "READY" and not ready:
                        if (message.get("pid") != 1 or message.get("uid") != os.geteuid()
                                or message.get("gid") != os.getegid()):
                            return {"code": "RUNTIME_UNAVAILABLE"}
                        ready = True
                    else:
                        return {"code": "RUNTIME_UNAVAILABLE"}
                    if owner and ready and not acknowledged:
                        try:
                            control.send(b"ACK")
                        except OSError:
                            return {"code": "RUNTIME_UNAVAILABLE"}
                        acknowledged = True
                        poller.register(process.stdin, selectors.EVENT_WRITE, "input")
                elif key.data == "input":
                    offset += os.write(process.stdin.fileno(), memoryview(request)[offset:offset + 65536])
                    if offset == len(request):
                        poller.unregister(process.stdin)
                        process.stdin.close()
                else:
                    # Read only remaining capacity plus one byte. A hostile
                    # child cannot force communicate() to buffer its full output.
                    chunk = os.read(process.stdout.fileno(), min(65536, MAX_BYTES + 1 - len(output)))
                    if not chunk:
                        poller.unregister(process.stdout)
                        eof = True
                    else:
                        output.extend(chunk)
                        if len(output) > MAX_BYTES:
                            return {"code": "OUTPUT_LIMIT"}
            if process.poll() is not None and eof:
                if not acknowledged:
                    return {"code": "RUNTIME_UNAVAILABLE"}
                if process.returncode != 0:
                    return {"code": "RUNTIME_FAILED"}
                try:
                    result = json.loads(output)
                    if (isinstance(result, dict) and isinstance(result.get("code"), str)
                            and result["code"] in CODES):
                        return result
                except (ValueError, UnicodeError, RecursionError):
                    pass
                return {"code": "INVALID_OUTPUT"}
    return {"code": "DEADLINE" if acknowledged else "RUNTIME_UNAVAILABLE"}


def render_cached(html, source_url, platform, analysis_mode, csp):
    global _pending_cleanup
    deadline = time.monotonic() + BUDGET_SECONDS
    if (sys.platform != "linux" or os.geteuid() == 0 or os.getegid() == 0
            or not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal")):
        return {"code": "RUNTIME_UNAVAILABLE"}
    if not _attempt_lock.acquire(blocking=False):
        return {"code": "RUNTIME_UNAVAILABLE"}
    process = control = child_control = None
    handles = {"owner": None, "bootstrap": None}
    directory = None
    completed = False
    result = {"code": "RUNTIME_UNAVAILABLE"}
    try:
        # Verify prerequisites before creating any helper. This also avoids
        # relying on a bootstrap pidfd acquired after a denied pidfd syscall.
        prerequisite = os.pidfd_open(os.getpid())
        try:
            signal.pidfd_send_signal(prerequisite, 0)
        finally:
            os.close(prerequisite)
        if not _reclaim_restart_profiles(deadline - CLEANUP_RESERVE):
            return result
        # Recovery spends this attempt's existing budget. Reserving only half a
        # second here repeatedly kills healthy deletions taking slightly longer.
        if not _drain_cleanup(deadline - CLEANUP_RESERVE):
            return result
        if (len(html.encode("utf-8")) > MAX_BYTES or not isinstance(csp, (list, tuple))
                or sum(len(str(value)) for value in [source_url, platform, analysis_mode, *csp]) > 65536):
            return {"code": "INPUT_LIMIT"}
        request = json.dumps(dict(html=html, source_url=source_url, platform=platform,
                                  analysis_mode=analysis_mode, csp=csp)).encode("utf-8")
        if len(request) > MAX_BYTES * 6 + 65536:
            return {"code": "INPUT_LIMIT"}
        # Naming only; creation/deletion happen outside the threaded worker.
        directory = f"/tmp/vct-browser-{os.getpid()}-{_process_start_time(os.getpid())}-{uuid4().hex}"
        control, child_control = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        process = _spawn(_bootstrap_command(child_control.fileno(), directory), directory,
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         pass_fds=(child_control.fileno(),))
        child_control.close()
        child_control = None
        handles["bootstrap"] = os.pidfd_open(process.pid)
        signal.pidfd_send_signal(handles["bootstrap"], 0)
        result = _receive(process, control, request, deadline - CLEANUP_RESERVE, handles)
        completed = process.poll() == 0  # Namespace exit AND profile deletion.
        return result
    except (OSError, ValueError, UnicodeError, RecursionError, MemoryError):
        return {"code": "RUNTIME_FAILED" if handles["owner"] is not None else "RUNTIME_UNAVAILABLE"}
    finally:
        # Cleanup can itself encounter MemoryError (for example while creating
        # deferred cleanup state). The admission lock must never depend on any
        # cleanup allocation succeeding.
        try:
            # Independent cleanup steps: one failed signal cannot skip the others.
            for channel in (control, child_control):
                if channel is not None:
                    try:
                        channel.close()
                    except OSError:
                        pass
            if not completed:
                # Init death kills the namespace. Keep its warm bootstrap alive to
                # reap init and delete the profile during this same deadline.
                signalled = _signal(handles["owner"])
                if signalled and process is not None:
                    try:
                        process.wait(timeout=max(0, deadline - time.monotonic()))
                    except subprocess.TimeoutExpired:
                        pass
                    completed = process.poll() == 0
                if process is not None and process.poll() is None:
                    if not _signal(handles["bootstrap"]):
                        try:
                            process.kill()
                        except OSError:
                            pass
            for handle in handles.values():
                if handle is not None:
                    try:
                        os.close(handle)
                    except OSError:
                        pass
            if process is not None:
                for stream in (process.stdin, process.stdout):
                    if stream is not None:
                        try:
                            stream.close()
                        except OSError:
                            pass
                if not completed:
                    try:
                        process.wait(timeout=max(0, min(.1, deadline - time.monotonic())))
                    except subprocess.TimeoutExpired:
                        pass
            if directory is not None and not completed:
                _pending_cleanup = {"directory": directory, "bootstrap": process, "helper": None}
                _drain_cleanup(deadline)
        finally:
            _attempt_lock.release()


def maybe_render(result, html, page_bytes, *, enabled=False, csp=(), renderer=None):
    started = time.monotonic()
    data = result.get("supplier_data") or {}
    before = field_count(data)
    code = eligibility(result, html, enabled=enabled)
    rendered = {}
    selected = result
    if code is None:
        access = access_wall(html)
        if access:
            code = "CONFLICT" if access == 'PARSE_FAILED' else "ACCESS_WALL"
            selected = {"source_url": result["source_url"], "extraction_status": access,
                        "reason": "PARSER_LIMIT" if access == 'PARSE_FAILED' else "LOGIN_REQUIRED" if access == "AUTH_REQUIRED" else "ACCESS_CHALLENGE"}
    if code is None:
        try:
            rendered = (renderer or render_cached)(html, result["source_url"], data["platform"], data["analysis_mode"], list(csp))
            code = rendered.get("code", "INVALID_OUTPUT")
            candidate = rendered.get("outcome") or {}
            if code == "ACCESS_WALL" and candidate.get("extraction_status") in {"AUTH_REQUIRED", "BLOCKED"}:
                selected = {"source_url": result["source_url"], "extraction_status": candidate["extraction_status"],
                            "reason": "LOGIN_REQUIRED" if candidate["extraction_status"] == "AUTH_REQUIRED" else "ACCESS_CHALLENGE"}
            elif code == "GAIN":
                after = candidate.get("supplier_data") or {}
                if candidate.get("extraction_status") not in {"SUCCESS", "PARTIAL"} or not preserves(data, after):
                    code = "CONFLICT"
                elif field_count(after) <= before:
                    code = "NO_GAIN"
                elif not re.fullmatch(r"[a-f0-9]{64}", rendered.get("rendered_sha256", "")):
                    code = "INVALID_OUTPUT"
                else:
                    selected = deepcopy(candidate)
                    selected["supplier_data"].update(extraction_method="PUBLIC_BROWSER", extractor_version=VERSION)
                    selected["raw_payload"].update(html_sha256=sha256(page_bytes).hexdigest(),
                        rendered_html_sha256=rendered["rendered_sha256"], extraction_method="PUBLIC_BROWSER",
                        extractor_version=VERSION, rendered_at=after["extracted_at"])
            elif code not in CODES:
                code = "INVALID_OUTPUT"
        except Exception:
            # Source exceptions and browser diagnostic strings must never leak.
            code = "RUNTIME_FAILED"
            selected = result
    def count(name):
        value = rendered.get(name, 0)
        return min(max(value, 0), MAX_BYTES) if type(value) is int else 0
    log.info("public_browser code=%s platform=%s elapsed_ms=%d input_bytes=%d dom_bytes=%d denials=%d fields_before=%d fields_after=%d",
             code, data.get("platform") if data.get("platform") in DOM_FIELDS else "UNKNOWN",
             min(int((time.monotonic() - started) * 1000), 60000), len(page_bytes), count("dom_bytes"), count("denials"),
             before, field_count(selected.get("supplier_data") or {}))
    return selected
