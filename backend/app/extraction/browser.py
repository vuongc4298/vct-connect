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
import signal
import subprocess
import sys
import tempfile
import time

from .contracts import EVIDENCE_FIELDS

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
    return value is not None and value != "" and value != [] and value != {}


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
    from .taobao import _tree, _scripts
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
    from .taobao import _tree, _prune_dom
    from .alibaba import _stylesheet_hidden
    tree = _tree(html)
    _stylesheet_hidden(tree)
    _prune_dom(tree)
    title = tree.css_first("title")
    body = tree.css_first("body")
    title_text = title.text(strip=True).lower() if title else ""
    text = title_text + " " + (body.text(strip=True).lower()[:2000] if body else "")
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


def _kill_tree(process):
    # Playwright's driver may put Chromium into a different process group.
    # Freeze the child and every descendant before killing; pidfds bind signals
    # to those processes even if a numeric PID is subsequently reused.
    handles = {}
    roots = {process.pid}
    try:
        for _ in range(3):
            parents = {}
            for path in Path("/proc").iterdir():
                if path.name.isdigit():
                    try:
                        parents[int(path.name)] = int((path / "stat").read_text().rsplit(")", 1)[1].split()[1])
                    except (OSError, ValueError, IndexError):
                        pass
            while True:
                found = {pid for pid, parent in parents.items() if parent in roots}
                if found <= roots:
                    break
                roots.update(found)
            for pid in roots - handles.keys():
                try:
                    handle = os.pidfd_open(pid)
                    signal.pidfd_send_signal(handle, signal.SIGSTOP)
                    handles[pid] = handle
                except ProcessLookupError:
                    pass
        for handle in handles.values():
            try:
                signal.pidfd_send_signal(handle, signal.SIGKILL)
            except ProcessLookupError:
                pass
    finally:
        for handle in handles.values():
            os.close(handle)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=.5)


def render_cached(html, source_url, platform, analysis_mode, csp):
    # Linux is the deployment runtime. Without a supervised process group on
    # another OS, decline the attempt rather than leave browser descendants.
    if (sys.platform != "linux" or os.geteuid() == 0 or not hasattr(os, "pidfd_open")
            or not hasattr(signal, "pidfd_send_signal")):
        return {"code": "RUNTIME_UNAVAILABLE"}
    try:
        handle = os.pidfd_open(os.getpid())
        try:
            signal.pidfd_send_signal(handle, 0)
        finally:
            os.close(handle)
    except OSError:
        return {"code": "RUNTIME_UNAVAILABLE"}
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="vct-browser-") as directory:
        process = None
        try:
            request = json.dumps(dict(html=html, source_url=source_url, platform=platform,
                                      analysis_mode=analysis_mode, csp=csp)).encode("utf-8")
            process = subprocess.Popen([sys.executable, "-m", "backend.app.extraction.browser_runner"],
                                       cwd=Path(__file__).resolve().parents[3], env=_environment(directory),
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                       start_new_session=True)
            output, _ = process.communicate(request, timeout=max(.01, BUDGET_SECONDS - .5 - (time.monotonic() - started)))
            if len(output) > MAX_BYTES:
                return {"code": "OUTPUT_LIMIT"}
            if process.returncode != 0:
                return {"code": "RUNTIME_FAILED"}
            result = json.loads(output)
            if not isinstance(result, dict) or result.get("code") not in CODES:
                return {"code": "INVALID_OUTPUT"}
            return result
        except subprocess.TimeoutExpired:
            return {"code": "DEADLINE"}
        except (OSError, ValueError, UnicodeError):
            return {"code": "RUNTIME_FAILED"}
        finally:
            if process is not None:
                _kill_tree(process)


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
            code = "ACCESS_WALL"
            selected = {"source_url": result["source_url"], "extraction_status": access,
                        "reason": "LOGIN_REQUIRED" if access == "AUTH_REQUIRED" else "ACCESS_CHALLENGE"}
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
