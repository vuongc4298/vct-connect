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
SCREEN_WALL_CASES = [
    ('<style>.runtime-wall{display:none}.runtime-wall{display:block}</style>', '<p class="runtime-wall">WALL</p>', 'AUTH_REQUIRED'),
    ('', '<p style="display:none;display:block">WALL</p>', 'AUTH_REQUIRED'),
    ('', '<div style="visibility:hidden">INVISIBLE_PARENT_SENTINEL<span style="visibility:visible">WALL</span></div>', 'AUTH_REQUIRED'),
    ('<style media="print">.runtime-wall{display:none}</style>', '<p class="runtime-wall">WALL</p>', 'AUTH_REQUIRED'),
    ('<style>.runtime-wall{opacity:0%}</style>', '<p class="runtime-wall">WALL</p>', None),
]


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
    from uuid import uuid4
    from backend.app.extraction.renormalize import renormalize_public_fields

    url, html = fixture(platform)
    if platform == "1688":
        # Replay needs retained model identity; a DOM canonical alone cannot bind it.
        model = {"result": {"data": {
            "Root": {"fields": {"dataJson": {"offerBaseInfo": {"offerId": "987654321012"}}}},
            "productTitle": {"fields": {"shopInfo": {"companyName": "Public supplier"}}},
        }}}
        html = html.replace("<body>", '<body><script>(function() {})(window.contextPath,' + json.dumps(model) + ');</script>')
    result = ADAPTERS[platform][1](html, url)
    started = time.monotonic()
    with caplog.at_level(logging.INFO, logger="backend.app.extraction.browser"):
        selected = maybe_render(result, html, html.encode(), enabled=True)
    assert selected["supplier_data"]["extraction_method"] == "PUBLIC_BROWSER", caplog.text
    assert field_count(selected["supplier_data"]) > field_count(result["supplier_data"])
    assert preserves(result["supplier_data"], selected["supplier_data"])
    assert time.monotonic() - started < 11
    print(platform, "fields", field_count(result["supplier_data"]), "->", field_count(selected["supplier_data"]), "elapsed_ms", int((time.monotonic() - started) * 1000))
    data = selected["supplier_data"]
    before = deepcopy(selected)
    replay = renormalize_public_fields(
        raw_payload=selected["raw_payload"], source_url=selected["source_url"],
        extraction_method=data["extraction_method"], analysis_mode=data["analysis_mode"],
        extracted_at=data["extracted_at"], source_snapshot_id=uuid4(),
        source_extractor_version=data["extractor_version"],
    )
    gained = set(result["supplier_data"]["missing_fields"]) - set(data["missing_fields"])
    assert gained == {"products" if platform == "TAOBAO" else "reviews"}
    for field in gained:
        assert replay["supplier_data"][field] == data[field]
    assert replay["reviews"] == (replay["supplier_data"]["reviews"] or [])
    assert replay["reviews"] == selected["reviews"]
    assert replay["raw_payload"]["public_fields"] == selected["raw_payload"]["public_fields"]
    assert selected == before


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
@pytest.mark.parametrize("platform", ADAPTERS)
def test_actual_computed_visibility_preserves_restored_descendant_evidence(platform, caplog):
    selector = {"1688": ".review-item", "TAOBAO": ".shopProductShelfArea--test", "ALIBABA": ".product-review"}[platform]
    program = """
      const evidence=document.querySelector(SELECTOR);
      const parent=document.createElement('section');
      parent.className='inherited-hidden';
      evidence.before(parent);parent.appendChild(evidence);
      parent.appendChild(document.createTextNode('INVISIBLE_PARENT_SENTINEL'));
      evidence.style.visibility='visible';
    """.replace('SELECTOR', json.dumps(selector))
    result, html = extracted(platform, extra=program)
    html = html.replace('</head>', '<style>@media (min-width:1px){.inherited-hidden{visibility:hidden}}</style></head>')
    started = time.monotonic()
    with caplog.at_level(logging.INFO, logger='backend.app.extraction.browser'):
        selected = maybe_render(result, html, html.encode(), enabled=True)
    assert selected['supplier_data']['extraction_method'] == 'PUBLIC_BROWSER', caplog.text
    assert 'code=GAIN' in caplog.text
    assert time.monotonic() - started < 10
    assert field_count(selected['supplier_data']) > field_count(result['supplier_data'])
    assert preserves(result['supplier_data'], selected['supplier_data'])
    assert selected['raw_payload']['html_sha256'] == sha256(html.encode()).hexdigest()
    assert 'INVISIBLE_PARENT_SENTINEL' not in json.dumps(selected)


@REAL
@pytest.mark.parametrize("platform", ADAPTERS)
@pytest.mark.parametrize("style", ['opacity:0%', 'display:none', 'visibility:hidden'])
def test_actual_invisible_access_text_does_not_latch_a_wall(platform, style):
    letters = json.dumps([ord(char) for char in 'Captcha Please sign in'])
    program = "document.body.insertAdjacentHTML('afterbegin','<p style=\"' + STYLE + '\">' + LETTERS.map(n=>String.fromCharCode(n)).join('') + '</p>');"
    result, html = extracted(platform, extra=program.replace('STYLE', json.dumps(style)).replace('LETTERS', letters))
    selected = maybe_render(result, html, html.encode(), enabled=True)
    assert selected['supplier_data']['extraction_method'] == 'PUBLIC_BROWSER'
    assert 'Captcha' not in json.dumps(selected)


@REAL
@pytest.mark.parametrize("platform", ADAPTERS)
@pytest.mark.parametrize("styles,markup,expected", SCREEN_WALL_CASES)
def test_actual_five_screen_cases_through_wrapper_and_latch(platform, styles, markup, expected, caplog):
    from backend.app.extraction.browser import access_wall
    letters = json.dumps([ord(char) for char in ('Please sign in' if expected else 'Captcha Please sign in')])
    program = "document.body.insertAdjacentHTML('afterbegin', MARKUP.replace('WALL', LETTERS.map(n=>String.fromCharCode(n)).join('')));"
    result, html = extracted(platform, extra=program.replace('MARKUP', json.dumps(markup)).replace('LETTERS', letters))
    html = html.replace('</head>', styles + '</head>')
    assert access_wall(html) is None  # Wall text only exists after execution.
    with caplog.at_level(logging.INFO, logger='backend.app.extraction.browser'):
        selected = maybe_render(result, html, html.encode(), enabled=True)
    if expected:
        assert selected['extraction_status'] == expected
        assert 'supplier_data' not in selected and 'raw_payload' not in selected
        assert 'code=ACCESS_WALL' in caplog.text
    else:
        assert selected['supplier_data']['extraction_method'] == 'PUBLIC_BROWSER'
        assert preserves(result['supplier_data'], selected['supplier_data'])
        assert 'code=GAIN' in caplog.text and 'code=ACCESS_WALL' not in caplog.text


@REAL
@pytest.mark.parametrize("platform", ADAPTERS)
@pytest.mark.parametrize("styles,markup,expected", SCREEN_WALL_CASES)
def test_actual_five_screen_cases_through_isolated_collector(platform, styles, markup, expected):
    import asyncio
    from backend.app.extraction.browser import access_wall, MAX_BYTES
    from backend.app.extraction.browser_runner import COLLECT_DOM, _reparse
    from backend.app.extraction.dom import tree
    from playwright.async_api import async_playwright

    source, original = fixture(platform, render=False)
    inert = tree(original)
    for script in inert.css('script'):
        script.decompose()
    wall_text = 'Please sign in' if expected else 'Captcha Please sign in'
    html = inert.html.replace('</head>', styles + '</head>').replace('<body>', '<body>' + markup.replace('WALL', wall_text))
    async def collect():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True, chromium_sandbox=True, timeout=7000)
            try:
                context = await browser.new_context(offline=True, service_workers='block')
                await context.route('**/*', lambda route: route.abort())
                page = await context.new_page()
                await page.set_content(html)
                session = await context.new_cdp_session(page)
                frame = (await session.send('Page.getFrameTree'))['frameTree']['frame']['id']
                world = await session.send('Page.createIsolatedWorld', {'frameId': frame, 'worldName': 'vct-visibility-test'})
                result = await session.send('Runtime.callFunctionOn', {
                    'executionContextId': world['executionContextId'], 'returnByValue': True,
                    'arguments': [{'value': MAX_BYTES}], 'functionDeclaration': COLLECT_DOM,
                })
                return result['result']['value']
            finally:
                await browser.close()
    collected = asyncio.run(collect())
    assert access_wall(collected['dom']) == expected
    assert 'INVISIBLE_PARENT_SENTINEL' not in collected['dom']
    if expected is None:
        assert 'Please sign in' not in collected['dom']
    before = ADAPTERS[platform][1](original, source)
    after = _reparse(collected['dom'], original, {'platform': platform, 'source_url': source, 'analysis_mode': 'ACCOUNT_PUBLIC'}, collected['authored'])
    # Access precedence belongs to each adapter; whenever it selects evidence,
    # this collector must preserve its original model and source binding.
    if after.get('supplier_data'):
        assert preserves(before['supplier_data'], after['supplier_data'])


@REAL
@pytest.mark.parametrize("platform", ADAPTERS)
def test_actual_access_latch_resists_visibility_api_tampering(platform):
    letters = json.dumps([ord(char) for char in 'Captcha'])
    program = """
      window.getComputedStyle=()=>({display:'none',visibility:'hidden',opacity:'0'});
      document.createTreeWalker=()=>({nextNode:()=>null});
      TreeWalker.prototype.nextNode=()=>null;
      CSSStyleDeclaration.prototype.getPropertyValue=()=> 'none';
      document.body.insertAdjacentHTML('afterbegin','<p>'+LETTERS.map(n=>String.fromCharCode(n)).join('')+'</p>');
    """.replace('LETTERS', letters)
    result, html = extracted(platform, extra=program)
    selected = maybe_render(result, html, html.encode(), enabled=True)
    assert selected['extraction_status'] == 'BLOCKED'
    assert 'supplier_data' not in selected and 'raw_payload' not in selected


@REAL
@pytest.mark.parametrize('platform', ADAPTERS)
def test_actual_transient_access_wall_resists_mutable_number(platform):
    letters = json.dumps([ord(char) for char in 'Captcha'])
    program = """
      window.Number=()=>0;
      const wall=document.createElement('p');
      wall.textContent=LETTERS.map(n=>String.fromCharCode(n)).join('');
      document.body.appendChild(wall);
      setTimeout(()=>wall.remove(),50);
    """.replace('LETTERS', letters)
    original, html = extracted(platform, extra=program)
    selected = maybe_render(original, html, html.encode(), enabled=True)
    assert selected['extraction_status'] == 'BLOCKED'
    assert 'supplier_data' not in selected and 'raw_payload' not in selected


@REAL
@pytest.mark.parametrize('platform', ADAPTERS)
@pytest.mark.parametrize('mutation', ['style', 'class', 'hidden'])
def test_actual_transient_access_wall_latches_attribute_only_reveal(platform, mutation):
    letters = json.dumps([ord(char) for char in 'Captcha'])
    setup = {
        'style': "wall.style.display='none';setTimeout(()=>wall.style.display='block',20);setTimeout(()=>wall.style.display='none',60);",
        'class': "const css=document.createElement('style');css.textContent='.concealed{display:none}.revealed{display:block}';document.head.appendChild(css);wall.className='concealed';setTimeout(()=>wall.className='revealed',20);setTimeout(()=>wall.className='concealed',60);",
        'hidden': "wall.hidden=true;setTimeout(()=>wall.hidden=false,20);setTimeout(()=>wall.hidden=true,60);",
    }[mutation]
    program = """
      const wall=document.createElement('p');
      wall.textContent=LETTERS.map(n=>String.fromCharCode(n)).join('');
      SETUP
      document.body.prepend(wall);
    """.replace('LETTERS', letters).replace('SETUP', setup)
    original, html = extracted(platform, extra=program)
    selected = maybe_render(original, html, html.encode(), enabled=True)
    assert selected['extraction_status'] == 'BLOCKED'
    assert selected['reason'] == 'ACCESS_CHALLENGE'
    assert 'supplier_data' not in selected and 'raw_payload' not in selected


@REAL
@pytest.mark.parametrize('platform', ADAPTERS)
@pytest.mark.parametrize('fault', ['includes', 'whitespace', 'normalizer', 'split-whitespace',
                                 'call', 'symbol-replace', 'regexp-test', 'regexp-exec', 'regexp-both'])
def test_actual_transient_access_wall_survives_mutable_traversal_and_normalized_budget(platform, fault):
    letters = json.dumps([ord(char) for char in 'Captcha'])
    program = """
      FAULT
      const wall=document.createElement('p');
      wall.textContent=PREFIX+LETTERS.map(n=>String.fromCharCode(n)).join('');
      document.body.prepend(wall);
      setTimeout(()=>wall.remove(),50);
    """
    fault_program = {
        'includes': "const includes=Array.prototype.includes;Array.prototype.includes=function(v,...rest){if(v==='P')return true;return includes.call(this,v,...rest);};",
        'normalizer': "String.prototype.replace=function(){return '';};String.prototype.slice=function(){return '';};String.prototype.toLowerCase=function(){return '';};",
        'whitespace': '',
        'split-whitespace': "for(let i=0;i<2100;i++)document.body.appendChild(document.createTextNode(' '));",
        'call': "const call=Function.prototype.call;Function.prototype.call=function(...args){if(this.name==='get body')return null;return Reflect.apply(call,this,args);};",
        'symbol-replace': "RegExp.prototype[Symbol.replace]=function(){return '';};",
        'regexp-test': "RegExp.prototype.test=function(){return false;};",
        'regexp-exec': "RegExp.prototype.exec=function(){return null;};",
        'regexp-both': "RegExp.prototype.test=function(){return false;};RegExp.prototype.exec=function(){return null;};",
    }[fault]
    prefix = "''" if fault in {'includes', 'split-whitespace'} else "' '.repeat(5000)"
    program = program.replace('FAULT', fault_program).replace('PREFIX', prefix).replace('LETTERS', letters)
    if fault == 'split-whitespace':
        program = program.replace('document.body.prepend(wall)', 'document.body.appendChild(wall)')
    original, html = extracted(platform, extra=program)
    selected = maybe_render(original, html, html.encode(), enabled=True)
    assert selected['extraction_status'] == 'BLOCKED'
    assert selected['reason'] == 'ACCESS_CHALLENGE'
    assert 'supplier_data' not in selected and 'raw_payload' not in selected


@REAL
@pytest.mark.parametrize('platform', ADAPTERS)
def test_actual_temporal_captcha_then_login_retains_blocked_precedence(platform):
    captcha = json.dumps([ord(char) for char in 'Captcha'])
    login = json.dumps([ord(char) for char in 'Please sign in'])
    program = """
      const wall=document.createElement('p');
      wall.textContent=CAPTCHA.map(n=>String.fromCharCode(n)).join('');
      document.body.prepend(wall);
      setTimeout(()=>{wall.textContent=LOGIN.map(n=>String.fromCharCode(n)).join('');},50);
    """.replace('CAPTCHA', captcha).replace('LOGIN', login)
    original, html = extracted(platform, extra=program)
    selected = maybe_render(original, html, html.encode(), enabled=True)
    assert selected['extraction_status'] == 'BLOCKED'
    assert selected['reason'] == 'ACCESS_CHALLENGE'
    assert 'supplier_data' not in selected and 'raw_payload' not in selected


async def collect_isolated(html):
    from backend.app.extraction.browser import MAX_BYTES
    from backend.app.extraction.browser_runner import COLLECT_DOM
    from playwright.async_api import async_playwright
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, chromium_sandbox=True, timeout=7000)
        try:
            context = await browser.new_context(offline=True, service_workers='block')
            await context.route('**/*', lambda route: route.abort())
            page = await context.new_page()
            await page.set_content(html)
            session = await context.new_cdp_session(page)
            frame = (await session.send('Page.getFrameTree'))['frameTree']['frame']['id']
            world = await session.send('Page.createIsolatedWorld', {'frameId': frame, 'worldName': 'vct-regression'})
            result = await session.send('Runtime.callFunctionOn', {
                'executionContextId': world['executionContextId'], 'returnByValue': True,
                'arguments': [{'value': MAX_BYTES}], 'functionDeclaration': COLLECT_DOM})
            assert 'exceptionDetails' not in result, result
            return result['result'].get('value')
        finally:
            await browser.close()


def inactive_authoritative_input(kind, placement):
    attributes = 'class="source-inactive"' + (' style="display:none"' if placement == 'inline' else '')
    foreign = 'https://www.alibaba.com/product-detail/Other_999999999.html'
    if kind == 'meta':
        markup = f'<meta property="og:url" content="{foreign}" {attributes}>'
    elif kind == 'canonical':
        markup = f'<link rel="canonical" href="{foreign}" {attributes}>'
    else:
        markup = f'<script type="application/ld+json" {attributes}>{{"@type":"Product","sku":"999999999"}}</script>'
    if placement.startswith('ancestor-'):
        markup = '<section class="source-inactive"' + (' style="display:none"' if placement == 'ancestor-inline' else '') + '>' + markup + '</section>'
    styles = '<style>.source-inactive{display:none}</style>' if placement in {'stylesheet', 'ancestor-stylesheet'} else ''
    return styles + markup


INACTIVE_INPUT_CASES = [(kind, placement) for placement in ('inline', 'stylesheet')
                        for kind in ('meta', 'canonical', 'jsonld')]
INACTIVE_INPUT_CASES += [('jsonld', 'ancestor-inline'), ('jsonld', 'ancestor-stylesheet')]


@pytest.mark.parametrize('kind,placement', INACTIVE_INPUT_CASES)
def test_reparse_preserves_original_inactive_authoritative_inputs(kind, placement):
    from backend.app.extraction.browser_runner import _reparse
    from selectolax.parser import HTMLParser
    source, original = fixture('ALIBABA')
    original = original.replace('</head>', inactive_authoritative_input(kind, placement) + '</head>')
    before = ADAPTERS['ALIBABA'][1](original, source)
    assert before['extraction_status'] == 'PARTIAL'
    compiled = HTMLParser(original)
    # Independent reproduction of the collector's style compilation.
    for node in compiled.css('[style]'):
        del node.attrs['style']
    for node in compiled.css('style'):
        node.decompose()
    review = '<div class="product-review"><div class="product-review-list"><div class="r-relative r-whitespace-normal">Useful public review</div></div></div>'
    compiled.body.insert_child(HTMLParser(review).css_first('.product-review'))
    after = _reparse(compiled.html, original, dict(platform='ALIBABA', source_url=source, analysis_mode='ACCOUNT_PUBLIC'), authored_snapshot(original))
    assert after['extraction_status'] == 'PARTIAL'
    assert preserves(before['supplier_data'], after['supplier_data'])
    assert after['raw_payload']['public_fields']['jsonld_identity'] == []
    selected = maybe_render(before, original, original.encode(), enabled=True, renderer=lambda *_: dict(
        code='GAIN', outcome=after, rendered_sha256=sha256(compiled.html.encode()).hexdigest()))
    assert selected['supplier_data']['extraction_method'] == 'PUBLIC_BROWSER'
    assert selected['supplier_data']['reviews'] == [{'text': 'Useful public review', 'source_url': source}]
    assert field_count(selected['supplier_data']) > field_count(before['supplier_data'])
    assert selected['raw_payload']['html_sha256'] == sha256(original.encode()).hexdigest()


@REAL
@pytest.mark.parametrize('kind,placement', INACTIVE_INPUT_CASES)
def test_actual_inactive_authoritative_inputs_preserve_gain_and_original_hash(kind, placement):
    source, html = fixture('ALIBABA')
    html = html.replace('</head>', inactive_authoritative_input(kind, placement) + '</head>')
    original = ADAPTERS['ALIBABA'][1](html, source)
    assert original['extraction_status'] == 'PARTIAL'
    frozen = deepcopy(original)
    selected = maybe_render(original, html, html.encode(), enabled=True)
    assert selected['supplier_data']['extraction_method'] == 'PUBLIC_BROWSER'
    assert selected['supplier_data']['reviews'] == [{'text': 'Useful public review', 'source_url': source}]
    assert preserves(original['supplier_data'], selected['supplier_data'])
    assert original == frozen
    assert selected['raw_payload']['public_fields']['jsonld_identity'] == []
    assert selected['raw_payload']['html_sha256'] == sha256(html.encode()).hexdigest()


@pytest.mark.parametrize('change', ['changed', 'introduced', 'duplicate', 'revealed'])
def test_reparse_checks_changed_or_new_rendered_foreign_identity_hints(change):
    from backend.app.extraction.browser_runner import _reparse
    from selectolax.parser import HTMLParser
    source, original = fixture('ALIBABA', render=False)
    original = original.replace('</head>', inactive_authoritative_input('meta', 'inline') + '</head>')
    compiled = HTMLParser(original)
    node = compiled.css_first('meta[property="og:url"]')
    if change == 'changed':
        del node.attrs['style']
        node.attrs['content'] = 'https://www.alibaba.com/product-detail/Changed_888888888.html'
    elif change == 'revealed':
        node.attrs['style'] = 'display:block'
    else:
        extra = node.html.replace(' style="display:none"', '') if change == 'duplicate' else '<link rel="canonical" href="https://www.alibaba.com/product-detail/Other_999999999.html">'
        compiled.head.insert_child(HTMLParser(extra).css_first('link, meta'))
    after = _reparse(compiled.html, original, dict(platform='ALIBABA', source_url=source, analysis_mode='ACCOUNT_PUBLIC'), authored_snapshot(compiled.html))
    assert after['extraction_status'] == 'PARSE_FAILED'
    assert 'supplier_data' not in after and 'raw_payload' not in after


METADATA_VISIBILITY = [('display', 'none', 'block'), ('visibility', 'hidden', 'visible'), ('opacity', '0', '1')]


def authored_snapshot(html, states=None):
    from selectolax.parser import HTMLParser
    structure = HTMLParser(html)
    sheets = []
    for index, node in enumerate(structure.css('style')):
        state = states[index] if states is not None else dict(media=node.attributes.get('media') or '', disabled=False)
        sheets.append(dict(css=node.text(), **state))
        while node.child:
            node.child.decompose()
    return json.dumps(dict(html=structure.html, sheets=sheets))


@pytest.mark.parametrize('kind', ['meta', 'canonical'])
@pytest.mark.parametrize('property,hidden,visible', [('display', 'none', 'block'), ('visibility', 'hidden', 'visible'), ('opacity', '0', '1')])
@pytest.mark.parametrize('reveal', [False, True])
def test_reparse_declines_conditional_metadata_visibility(kind, property, hidden, visible, reveal):
    from backend.app.extraction.browser_runner import _reparse
    source, original = fixture('ALIBABA')
    foreign = 'https://www.alibaba.com/product-detail/Other_999999999.html'
    attrs = f'property="og:url" content="{foreign}"' if kind == 'meta' else f'rel="canonical" href="{foreign}"'
    hint = f'<{ "meta" if kind == "meta" else "link"} class="conditional-hint" {attrs} style="{property}:{hidden if reveal else visible}">'
    css = '@media screen and (min-width:1px){.conditional-hint{' + property + ':' + (visible if reveal else hidden) + '!important}}'
    authored = original.replace('</head>', hint + '<style>' + css + '</style></head>')
    after = _reparse(compiled_metadata_view(authored), original,
        dict(platform='ALIBABA', source_url=source, analysis_mode='ACCOUNT_PUBLIC'), authored_snapshot(authored))
    assert after == dict(source_url=source, extraction_status='PARSE_FAILED', reason='MALFORMED_PAGE')
    before = ADAPTERS['ALIBABA'][1](original, source)
    assert before['raw_payload']['html_sha256'] == sha256(original.encode()).hexdigest()


@pytest.mark.parametrize('kind', ['meta', 'canonical'])
@pytest.mark.parametrize('css', [
    '.unrepresented:first-of-type{display:block!important}',
    '.unrepresented{all:initial!important}',
    '.unrepresented{display:var(--shown)!important}:root{--shown:block}',
    '.unrepresented{opacity:calc(1)!important}',
])
def test_reparse_declines_unrepresented_top_level_metadata(kind, css):
    from backend.app.extraction.browser_runner import _reparse
    source, original = fixture('ALIBABA')
    foreign = 'https://www.alibaba.com/product-detail/Other_999999999.html'
    hint = (f'<meta property="og:url" content="{foreign}"' if kind == 'meta'
            else f'<link rel="canonical" href="{foreign}"')
    authored = original.replace('</head>', hint + ' class="unrepresented" style="display:none;opacity:0">'
                                + '<style>' + css + '</style></head>')
    result = _reparse(compiled_metadata_view(authored), original,
        dict(platform='ALIBABA', source_url=source, analysis_mode='ACCOUNT_PUBLIC'), authored_snapshot(authored))
    assert result == dict(source_url=source, extraction_status='PARSE_FAILED', reason='MALFORMED_PAGE')


@pytest.mark.parametrize('style', ['display:var(--shown)', 'opacity:calc(1)', 'all:initial'])
def test_reparse_declines_unrepresented_inline_metadata(style):
    from backend.app.extraction.browser_runner import _reparse
    source, original = fixture('ALIBABA')
    authored = original.replace('</head>', f'<meta property="og:url" content="{source}" style="{style}"></head>')
    result = _reparse(compiled_metadata_view(authored), original,
        dict(platform='ALIBABA', source_url=source, analysis_mode='ACCOUNT_PUBLIC'), authored_snapshot(authored))
    assert result == dict(source_url=source, extraction_status='PARSE_FAILED', reason='MALFORMED_PAGE')


@REAL
@pytest.mark.parametrize('kind', ['meta', 'canonical'])
@pytest.mark.parametrize('rule', [
    '.unrepresented:first-of-type{display:block!important}',
    '.unrepresented{all:initial!important}',
    '.unrepresented{display:var(--shown)!important}:root{--shown:block}',
])
def test_actual_unrepresented_top_level_metadata_preserves_http(kind, rule, caplog):
    foreign = 'https://www.alibaba.com/product-detail/Other_999999999.html'
    program = ('const h=document.createElement(' + json.dumps('meta' if kind == 'meta' else 'link') + ');'
               + ('h.setAttribute("property","og:url");h.content=' if kind == 'meta' else 'h.rel="canonical";h.href=')
               + json.dumps(foreign) + ';h.className="unrepresented";h.style.display="none";document.head.appendChild(h);'
               + 'const s=document.createElement("style");s.textContent=' + json.dumps(rule) + ';document.head.appendChild(s);')
    original, html = extracted('ALIBABA', extra=program)
    frozen = deepcopy(original)
    with caplog.at_level(logging.INFO, logger='backend.app.extraction.browser'):
        selected = maybe_render(original, html, html.encode(), enabled=True)
    assert selected is original and original == frozen
    assert 'code=CONFLICT' in caplog.text
    assert selected['raw_payload']['html_sha256'] == sha256(html.encode()).hexdigest()
    assert 'rendered_html_sha256' not in selected['raw_payload']


@pytest.mark.parametrize('css,media,disabled', [
    ('@media screen{.unused{display:none}}', '', False),
    ('@media screen{meta{color:red}}', '', False),
    ('@media print{meta{display:none}}', '', False),
    ('meta{display:none}', 'print', False),
    ('meta{display:none}', 'screen and (min-width:1px)', True),
])
def test_irrelevant_or_disabled_conditional_metadata_keeps_gain(css, media, disabled):
    from backend.app.extraction.browser_runner import _reparse
    source, original = fixture('ALIBABA')
    authored = original.replace('</head>', f'<meta property="og:url" content="{source}"><style>{css}</style></head>')
    after = _reparse(compiled_metadata_view(authored), original,
        dict(platform='ALIBABA', source_url=source, analysis_mode='ACCOUNT_PUBLIC'),
        authored_snapshot(authored, [dict(media=media, disabled=disabled)]))
    assert after['extraction_status'] == 'PARTIAL'
    assert after['supplier_data']['reviews']
    assert preserves(ADAPTERS['ALIBABA'][1](original, source)['supplier_data'], after['supplier_data'])


@pytest.mark.parametrize('media', ['screen and (min-width:1px)', '(min-width:1px)'])
def test_reparse_declines_relevant_conditional_sheet_media(media):
    from backend.app.extraction.browser_runner import _reparse
    source, original = fixture('ALIBABA')
    authored = original.replace('</head>', f'<meta property="og:url" content="{source}"><style>meta{{display:none}}</style></head>')
    after = _reparse(compiled_metadata_view(authored), original,
        dict(platform='ALIBABA', source_url=source, analysis_mode='ACCOUNT_PUBLIC'),
        authored_snapshot(authored, [dict(media=media, disabled=False)]))
    assert after == dict(source_url=source, extraction_status='PARSE_FAILED', reason='MALFORMED_PAGE')


def test_reparse_current_metadata_exhaustion_rejects_original_model_evidence():
    from backend.app.extraction.browser_runner import _reparse
    source, original = fixture('ALIBABA')
    authored = original.replace('</head>', '<meta property="og:url" content="' + source + '"><style>' + '.x{display:block}' * 4500 + '</style></head>').replace('</body>', '<i class="x"></i>' * 1000 + '</body>')
    after = _reparse(compiled_metadata_view(authored), original,
        dict(platform='ALIBABA', source_url=source, analysis_mode='ACCOUNT_PUBLIC'), authored_snapshot(authored))
    assert after == dict(source_url=source, extraction_status='PARSE_FAILED', reason='PARSER_LIMIT')


@REAL
@pytest.mark.parametrize('kind', ['meta', 'canonical'])
@pytest.mark.parametrize('reveal', [True, False])
@pytest.mark.parametrize('conditional', ['rule', 'sheet'])
def test_actual_conditional_metadata_declines_gain(kind, reveal, conditional, caplog):
    foreign = 'https://www.alibaba.com/product-detail/Other_999999999.html'
    program = ('const hint=document.createElement(' + json.dumps('meta' if kind == 'meta' else 'link') + ');'
        + ('hint.setAttribute("property","og:url");hint.content=' if kind == 'meta' else 'hint.rel="canonical";hint.href=')
        + json.dumps(foreign) + ';hint.className="conditional-hint";hint.style.display=' + json.dumps('none' if reveal else 'block')
        + ';document.head.appendChild(hint);const s=document.createElement("style");')
    rule = '.conditional-hint{display:' + ('block' if reveal else 'none') + '!important}'
    if conditional == 'rule':
        rule = '@media screen and (min-width:1px){' + rule + '}'
    else:
        program += 's.media="screen and (min-width:1px)";'
    program += 's.textContent=' + json.dumps(rule) + ';document.head.appendChild(s);'
    original, html = extracted('ALIBABA', extra=program)
    frozen = deepcopy(original)
    with caplog.at_level(logging.INFO, logger='backend.app.extraction.browser'):
        selected = maybe_render(original, html, html.encode(), enabled=True)
    assert selected is original and original == frozen
    assert 'code=CONFLICT' in caplog.text
    assert selected['raw_payload']['html_sha256'] == sha256(html.encode()).hexdigest()
    assert 'rendered_html_sha256' not in selected['raw_payload']


@REAL
def test_actual_current_metadata_exhaustion_preserves_http(caplog):
    # Unmatched supported rules still consume the finite document-scan budget.
    # This probes rejection, separately from the local all-matching consumer
    # regression and the observed actual all-matching deadline preservation.
    program = 'const s=document.createElement("style");s.textContent=".x{display:block}".repeat(4500);document.head.appendChild(s);for(let i=0;i<1000;i++){const n=document.createElement("i");document.body.appendChild(n);}'
    original, html = extracted('ALIBABA', extra=program)
    frozen = deepcopy(original)
    with caplog.at_level(logging.INFO, logger='backend.app.extraction.browser'):
        selected = maybe_render(original, html, html.encode(), enabled=True)
    assert selected is original and original == frozen
    assert 'code=CONFLICT' in caplog.text
    assert selected['raw_payload']['html_sha256'] == sha256(html.encode()).hexdigest()
    assert 'rendered_html_sha256' not in selected['raw_payload']


@REAL
@pytest.mark.parametrize('platform', ADAPTERS)
@pytest.mark.parametrize('markup,status', [
    ('<p>cap<span>tcha</span></p>', 'BLOCKED'),
    ('cap<div style="display:inline">tcha</div>', 'BLOCKED'),
    ('<span style="display:block flow">Please</span><span style="display:block flow">sign in</span>', 'AUTH_REQUIRED'),
    ('<span style="display:block flex">Please</span><span style="display:block flex">sign in</span>', 'AUTH_REQUIRED'),
    ('<p>Please<br>sign in</p>', 'AUTH_REQUIRED'),
    ('<div>Please</div><div>sign in</div>', 'AUTH_REQUIRED'),
    ('<p>cap<span style="display:none">IGNORE</span>tcha</p>', 'BLOCKED'),
])
def test_actual_transient_inline_and_layout_access_text(platform, markup, status):
    # Character codes keep the original inert script from serving as access text.
    letters = json.dumps([ord(char) for char in markup])
    program = 'const wall=document.createElement("section");wall.innerHTML=' + letters + '.map(n=>String.fromCharCode(n)).join("");document.body.prepend(wall);setTimeout(()=>wall.remove(),50);'
    original, html = extracted(platform, extra=program)
    selected = maybe_render(original, html, html.encode(), enabled=True)
    assert selected['extraction_status'] == status
    assert 'supplier_data' not in selected and 'raw_payload' not in selected


def compiled_metadata_view(authored):
    """Independent reproduction of CSS removal, with selected rendered evidence."""
    from selectolax.parser import HTMLParser
    compiled = HTMLParser(authored)
    for node in compiled.css('style'):
        node.decompose()
    for node in compiled.css('[style]'):
        del node.attrs['style']
    review = '<div class="product-review"><div class="product-review-list"><div class="r-relative r-whitespace-normal">Useful public review</div></div></div>'
    compiled.body.insert_child(HTMLParser(review).css_first('.product-review'))
    return compiled.html


def assert_metadata_gain(original, source, authored, compiled):
    from backend.app.extraction.browser_runner import _reparse
    before = ADAPTERS['ALIBABA'][1](original, source)
    after = _reparse(compiled, original, dict(platform='ALIBABA', source_url=source, analysis_mode='ACCOUNT_PUBLIC'), authored_snapshot(authored))
    assert after['extraction_status'] == 'PARTIAL'
    assert preserves(before['supplier_data'], after['supplier_data'])
    selected = maybe_render(before, original, original.encode(), enabled=True, renderer=lambda *_: dict(
        code='GAIN', outcome=after, rendered_sha256=sha256(compiled.encode()).hexdigest()))
    assert selected['supplier_data']['extraction_method'] == 'PUBLIC_BROWSER'
    assert selected['supplier_data']['supplier_name'] == 'Public supplier'
    assert selected['supplier_data']['reviews'] == [{'text': 'Useful public review', 'source_url': source}]
    assert selected['raw_payload']['public_fields']['review_bodies'] == [dict(
        text='Useful public review', source_url=source, original_length=20, truncated=False)]
    assert selected['raw_payload']['html_sha256'] == sha256(original.encode()).hexdigest()
    assert selected['raw_payload']['rendered_html_sha256'] == sha256(compiled.encode()).hexdigest()
    return selected


@pytest.mark.parametrize('kind', ['meta', 'canonical'])
@pytest.mark.parametrize('property,hidden,visible', METADATA_VISIBILITY)
def test_reparse_stylesheet_only_reveal_uses_current_activity_with_stale_negative_control(kind, property, hidden, visible):
    from backend.app.extraction.browser_runner import _reparse
    source, original = fixture('ALIBABA')
    markup = inactive_authoritative_input(kind, 'stylesheet').replace('display:none', property + ':' + hidden)
    original = original.replace('</head>', markup + '</head>')
    authored = original.replace(property + ':' + hidden, property + ':' + visible)
    compiled = compiled_metadata_view(authored)
    request = dict(platform='ALIBABA', source_url=source, analysis_mode='ACCOUNT_PUBLIC')
    after = _reparse(compiled, original, request, authored_snapshot(authored))
    assert after['extraction_status'] == 'PARSE_FAILED'
    assert 'supplier_data' not in after and 'raw_payload' not in after
    # Passing stale HTTP activity reproduces the prohibited gain independently.
    stale = _reparse(compiled, original, request, authored_snapshot(original))
    assert stale['extraction_status'] == 'PARTIAL'
    assert stale['supplier_data']['reviews']


@pytest.mark.parametrize('kind', ['meta', 'canonical'])
@pytest.mark.parametrize('property,hidden,visible', METADATA_VISIBILITY)
@pytest.mark.parametrize('placement', ['inline', 'stylesheet'])
def test_reparse_current_hidden_hints_preserve_gain_and_selected_hashes(kind, property, hidden, visible, placement):
    source, original = fixture('ALIBABA')
    markup = inactive_authoritative_input(kind, placement).replace('display:none', property + ':' + hidden)
    authored = original.replace('</head>', markup + '</head>')
    assert_metadata_gain(original, source, authored, compiled_metadata_view(authored))


@pytest.mark.parametrize('kind', ['meta', 'canonical'])
@pytest.mark.parametrize('state', ['default', 'active-inline', 'active-stylesheet', 'hidden-inline', 'hidden-stylesheet'])
def test_reparse_unchanged_head_hint_activity_and_default_admission(kind, state):
    source, original = fixture('ALIBABA')
    placement = 'stylesheet' if state.endswith('stylesheet') else 'inline'
    markup = inactive_authoritative_input(kind, placement)
    if state == 'default':
        markup = markup.replace(' style="display:none"', '')
    elif state.startswith('active'):
        markup = markup.replace('display:none', 'display:block')
    if not state.startswith('hidden'):
        markup = markup.replace('https://www.alibaba.com/product-detail/Other_999999999.html', source)
    original = original.replace('</head>', markup + '</head>')
    assert_metadata_gain(original, source, original, compiled_metadata_view(original))


@pytest.mark.parametrize('kind', ['meta', 'canonical'])
@pytest.mark.parametrize('active_duplicate', [False, True])
def test_reparse_duplicate_hints_do_not_consume_stale_or_pruned_activity(kind, active_duplicate):
    from backend.app.extraction.browser_runner import _reparse
    from selectolax.parser import HTMLParser
    source, original = fixture('ALIBABA')
    hint = inactive_authoritative_input(kind, 'inline').replace(' style="display:none"', '')
    # Both copies have identical attributes; only their ancestor state differs.
    authored = original.replace('</body>', '<section style="display:none">' + hint + '</section>'
        + '<section style="display:' + ('block' if active_duplicate else 'none') + '">' + hint + '</section></body>')
    compiled = HTMLParser(compiled_metadata_view(authored))
    for node in compiled.css('section'):
        node.decompose()  # Evidence pruning cannot erase current identity checks.
    if active_duplicate:
        after = _reparse(compiled.html, original, dict(platform='ALIBABA', source_url=source, analysis_mode='ACCOUNT_PUBLIC'), authored_snapshot(authored))
        assert after['extraction_status'] == 'PARSE_FAILED'
        assert 'supplier_data' not in after and 'raw_payload' not in after
    else:
        assert_metadata_gain(original, source, authored, compiled.html)


@pytest.mark.parametrize('value,error', [
    (None, OverflowError), ('<html></html>', ValueError), ({}, ValueError),
    ({'dom': '<html></html>'}, ValueError),
    ({'dom': '<html></html>', 'authored': None}, ValueError),
    ({'dom': [], 'authored': '<html></html>'}, ValueError),
    ({'dom': '', 'authored': '<html></html>'}, ValueError),
    ({'dom': '<html></html>', 'authored': ''}, ValueError),
    ({'dom': '<html></html>', 'authored': '<html></html>', 'extra': 'untrusted'}, ValueError),
])
def test_private_collector_requires_both_valid_views(value, error):
    from backend.app.extraction.browser_runner import _collected_views
    with pytest.raises(error):
        _collected_views(value)


@pytest.mark.parametrize('name', ['dom', 'authored'])
@pytest.mark.parametrize('multibyte', [False, True])
def test_private_collector_bounds_each_view_independently(name, multibyte):
    from backend.app.extraction.browser import MAX_BYTES
    from backend.app.extraction.browser_runner import _collected_views
    value = dict(dom='<html></html>', authored='<html></html>')
    value[name] = '界' * (MAX_BYTES // 3 + 1) if multibyte else 'x' * (MAX_BYTES + 1)
    with pytest.raises(OverflowError):
        _collected_views(value)
    value[name] = 'x' * MAX_BYTES
    dom, encoded, authored = _collected_views(value)
    assert dom == value['dom'] and encoded == dom.encode() and authored == value['authored']


@pytest.mark.parametrize('kind', ['meta', 'canonical'])
@pytest.mark.parametrize('state,media,disabled', [('disabled', '', True), ('print', 'print', False), ('screen', 'screen', False)])
def test_reparse_uses_private_sheet_state_without_changing_selector_attributes(kind, state, media, disabled):
    from backend.app.extraction.browser_runner import _reparse
    source, original = fixture('ALIBABA')
    markup = inactive_authoritative_input(kind, 'stylesheet')
    # The current sheet media can differ from markup. A selector depending on
    # the authored STYLE attribute still matches the unchanged DOM structure.
    markup = markup.replace('<style>', '<style media="print">').replace('.source-inactive', 'style[media="print"] + .source-inactive')
    authored = original.replace('</head>', markup + '</head>')
    compiled = compiled_metadata_view(authored)
    after = _reparse(compiled, original, dict(platform='ALIBABA', source_url=source, analysis_mode='ACCOUNT_PUBLIC'),
        authored_snapshot(authored, [dict(media=media, disabled=disabled)]))
    assert after['extraction_status'] == ('PARTIAL' if state == 'screen' else 'PARSE_FAILED')


@pytest.mark.parametrize('snapshot', [
    '', '{}', 'null', '[]', '{"html":7,"sheets":[]}', '{"html":"","sheets":[]}',
    '{"html":"<style></style>","sheets":[]}',
    '{"html":"<style></style>","sheets":[{"media":"","disabled":0}]}',
    '{"html":"<style></style>","sheets":[{"media":null,"disabled":false}]}',
    '{"html":"<style></style>","sheets":[{}]}',
])
def test_reparse_declines_malformed_authored_snapshot(snapshot):
    from backend.app.extraction.browser_runner import _reparse
    source, original = fixture('ALIBABA')
    with pytest.raises(ValueError):
        _reparse(original, original, dict(platform='ALIBABA', source_url=source, analysis_mode='ACCOUNT_PUBLIC'), snapshot)


@pytest.mark.parametrize('kind', ['meta', 'canonical'])
@pytest.mark.parametrize('property,hidden,visible', METADATA_VISIBILITY)
def test_private_stylesheet_delimiter_cannot_create_metadata_or_override_current_activity(kind, property, hidden, visible):
    from backend.app.extraction.browser_runner import _reparse
    from selectolax.parser import HTMLParser
    source, original = fixture('ALIBABA')
    markup = inactive_authoritative_input(kind, 'stylesheet').replace('display:none', property + ':' + hidden)
    authored = original.replace('</head>', markup + '</head>')
    snapshot = json.loads(authored_snapshot(authored))
    injected = "</style><meta property='og:url' content='https://www.alibaba.com/product-detail/Injected_888888888.html'>"
    snapshot['sheets'][0]['css'] += '.unused{--label:"' + injected + '"}'
    assert len(HTMLParser(snapshot['html']).css('meta, link')) == 1
    compiled = compiled_metadata_view(authored)
    request = dict(platform='ALIBABA', source_url=source, analysis_mode='ACCOUNT_PUBLIC')
    after = _reparse(compiled, original, request, json.dumps(snapshot))
    assert after['extraction_status'] == 'PARTIAL'
    selected = maybe_render(ADAPTERS['ALIBABA'][1](original, source), original, original.encode(), enabled=True,
        renderer=lambda *_: dict(code='GAIN', outcome=after, rendered_sha256=sha256(compiled.encode()).hexdigest()))
    assert selected['supplier_data']['extraction_method'] == 'PUBLIC_BROWSER'
    assert selected['supplier_data']['reviews'] == [{'text': 'Useful public review', 'source_url': source}]
    assert selected['raw_payload']['html_sha256'] == sha256(original.encode()).hexdigest()
    # The real current rule remains authoritative despite a markup delimiter in
    # an unrelated declaration; changing only that rule must activate the hint.
    snapshot['sheets'][0]['css'] = snapshot['sheets'][0]['css'].replace(property + ':' + hidden, property + ':' + visible)
    conflict = _reparse(compiled, original, request, json.dumps(snapshot))
    assert conflict['extraction_status'] == 'PARSE_FAILED'
    assert 'supplier_data' not in conflict and 'raw_payload' not in conflict


@pytest.mark.parametrize('bad_css', [None, [], {}, 1, True])
def test_private_stylesheet_rules_require_text_before_activity_lookup(bad_css):
    from backend.app.extraction.browser_runner import _reparse
    source, original = fixture('ALIBABA')
    snapshot = dict(html='<html><head><style></style></head><body></body></html>',
        sheets=[dict(css=bad_css, media='', disabled=False)])
    with pytest.raises(ValueError):
        _reparse(original, original, dict(platform='ALIBABA', source_url=source, analysis_mode='ACCOUNT_PUBLIC'), json.dumps(snapshot))


@REAL
@pytest.mark.parametrize('kind', ['meta', 'canonical'])
@pytest.mark.parametrize('style', ['visibility:hidden', 'display:none', 'opacity:0'])
@pytest.mark.parametrize('placement', ['inline', 'stylesheet'])
def test_actual_introduced_hidden_identity_hints_preserve_gain(kind, style, placement):
    foreign = 'https://www.alibaba.com/product-detail/Other_999999999.html'
    program = (f"const hint=document.createElement({json.dumps('meta' if kind == 'meta' else 'link')});"
               + ("hint.setAttribute('property','og:url');hint.content=" if kind == 'meta' else "hint.rel='canonical';hint.href=")
               + json.dumps(foreign) + ';document.head.appendChild(hint);')
    if placement == 'inline':
        program += 'hint.style.cssText=' + json.dumps(style) + ';'
    else:
        program += 'hint.className="introduced-hint";const s=document.createElement("style");s.textContent=' + json.dumps('.introduced-hint{' + style + '}') + ';document.head.appendChild(s);'
    original, html = extracted('ALIBABA', extra=program)
    selected = maybe_render(original, html, html.encode(), enabled=True)
    assert selected['supplier_data']['extraction_method'] == 'PUBLIC_BROWSER'
    assert selected['supplier_data']['reviews'] == [{'text': 'Useful public review', 'source_url': original['source_url']}]
    assert preserves(original['supplier_data'], selected['supplier_data'])
    assert selected['raw_payload']['html_sha256'] == sha256(html.encode()).hexdigest()


@REAL
@pytest.mark.parametrize('kind', ['meta', 'canonical'])
@pytest.mark.parametrize('placement', ['inline', 'stylesheet'])
def test_actual_revealed_original_foreign_identity_hint_preserves_http(kind, placement, caplog):
    original, html = extracted('ALIBABA', extra="document.querySelector('.source-inactive').style.display='block';")
    html = html.replace('</head>', inactive_authoritative_input(kind, placement) + '</head>')
    original = ADAPTERS['ALIBABA'][1](html, original['source_url'])
    assert original['extraction_status'] == 'PARTIAL'
    frozen = deepcopy(original)
    with caplog.at_level(logging.INFO, logger='backend.app.extraction.browser'):
        selected = maybe_render(original, html, html.encode(), enabled=True)
    assert selected is original and original == frozen
    assert 'code=CONFLICT' in caplog.text
    assert 'rendered_html_sha256' not in selected['raw_payload']


@REAL
@pytest.mark.parametrize('kind', ['meta', 'canonical'])
@pytest.mark.parametrize('property,hidden,visible', [('display', 'none', 'block'),
                                                   ('visibility', 'hidden', 'visible'), ('opacity', '0', '1')])
def test_actual_stylesheet_only_reveal_checks_current_metadata_activity(kind, property, hidden, visible, caplog):
    rule = '.source-inactive{' + property + ':' + visible + '}'
    source, html = fixture('ALIBABA', extra='document.querySelector("style").textContent=' + json.dumps(rule) + ';')
    markup = inactive_authoritative_input(kind, 'stylesheet').replace('display:none', property + ':' + hidden)
    html = html.replace('</head>', markup + '</head>')
    original = ADAPTERS['ALIBABA'][1](html, source)
    assert original['extraction_status'] == 'PARTIAL'
    frozen = deepcopy(original)
    with caplog.at_level(logging.INFO, logger='backend.app.extraction.browser'):
        selected = maybe_render(original, html, html.encode(), enabled=True)
    assert selected is original and original == frozen
    assert 'code=CONFLICT' in caplog.text
    assert 'rendered_html_sha256' not in selected['raw_payload']


@REAL
@pytest.mark.parametrize('kind', ['meta', 'canonical'])
@pytest.mark.parametrize('property,hidden,visible', METADATA_VISIBILITY)
def test_actual_cssom_only_reveal_checks_current_metadata_activity(kind, property, hidden, visible, caplog):
    program = 'document.querySelector("style").sheet.cssRules[0].style.setProperty(' + json.dumps(property) + ',' + json.dumps(visible) + ');'
    source, html = fixture('ALIBABA', extra=program)
    markup = inactive_authoritative_input(kind, 'stylesheet').replace('display:none', property + ':' + hidden)
    html = html.replace('</head>', markup + '</head>')
    original = ADAPTERS['ALIBABA'][1](html, source)
    assert original['extraction_status'] == 'PARTIAL'
    frozen = deepcopy(original)
    with caplog.at_level(logging.INFO, logger='backend.app.extraction.browser'):
        selected = maybe_render(original, html, html.encode(), enabled=True)
    assert selected is original and original == frozen
    assert 'code=CONFLICT' in caplog.text
    assert 'rendered_html_sha256' not in selected['raw_payload']


@REAL
@pytest.mark.parametrize('kind', ['meta', 'canonical'])
@pytest.mark.parametrize('state', ['disabled', 'media', 'print-to-screen'])
def test_actual_cssom_sheet_disabled_and_media_state(kind, state, caplog):
    program = {'disabled': 'document.querySelector("style").sheet.disabled=true;',
        'media': 'document.querySelector("style").sheet.media.mediaText="print";',
        'print-to-screen': 'document.querySelector("style").sheet.media.mediaText="screen";'}[state]
    source, html = fixture('ALIBABA', extra=program)
    markup = inactive_authoritative_input(kind, 'stylesheet')
    if state == 'print-to-screen':
        markup = markup.replace('<style>', '<style media="print">').replace(
            'https://www.alibaba.com/product-detail/Other_999999999.html', source)
    html = html.replace('</head>', markup + '</head>')
    original = ADAPTERS['ALIBABA'][1](html, source)
    assert original['extraction_status'] == 'PARTIAL'
    with caplog.at_level(logging.INFO, logger='backend.app.extraction.browser'):
        selected = maybe_render(original, html, html.encode(), enabled=True)
    if state == 'print-to-screen':
        assert selected['supplier_data']['extraction_method'] == 'PUBLIC_BROWSER'
        assert selected['raw_payload']['html_sha256'] == sha256(html.encode()).hexdigest()
    else:
        assert selected is original
        assert 'code=CONFLICT' in caplog.text


@REAL
def test_actual_private_snapshot_is_native_current_cssom_and_omits_unrelated_text():
    import asyncio
    from backend.app.extraction.browser_runner import _collected_views
    html = ('<html><head><style media="print">.hint{display:none}</style><meta class="hint"></head>'
        '<body><p data-selector="kept">PRIVATE_BODY_SENTINEL</p><script>'
        'document.querySelector("style").sheet.cssRules[0].style.display="block";'
        'document.querySelector("style").sheet.media.mediaText="screen";'
        'JSON.stringify=()=>"SOURCE_ENVELOPE_SENTINEL";'
        'Element.prototype.cloneNode=()=>null;'
        '</script></body></html>')
    collected = asyncio.run(collect_isolated(html))
    dom, _, authored = _collected_views(collected)
    snapshot = json.loads(authored)
    assert 'display' not in snapshot['html']
    assert 'media="print"' in snapshot['html'] and 'data-selector="kept"' in snapshot['html']
    assert snapshot['sheets'] == [dict(css='.hint { display: block; }', media='screen', disabled=False)]
    assert 'PRIVATE_BODY_SENTINEL' not in snapshot['html']
    assert 'SOURCE_ENVELOPE_SENTINEL' not in authored and 'JSON.stringify' not in snapshot['html']
    assert '<script></script>' in snapshot['html']
    assert '<style' not in dom


@REAL
def test_actual_unrepresented_adopted_stylesheet_explicitly_preserves_http(caplog):
    original, html = extracted('ALIBABA', extra='const s=new CSSStyleSheet();s.replaceSync("meta{display:none}");document.adoptedStyleSheets=[s];')
    frozen = deepcopy(original)
    with caplog.at_level(logging.INFO, logger='backend.app.extraction.browser'):
        selected = maybe_render(original, html, html.encode(), enabled=True)
    assert selected is original and selected == frozen
    assert 'code=RUNTIME_FAILED' in caplog.text


@REAL
@pytest.mark.parametrize('kind', ['meta', 'canonical'])
@pytest.mark.parametrize('state', ['default', 'active-inline', 'active-stylesheet', 'hidden-inline', 'hidden-stylesheet'])
def test_actual_unchanged_head_hint_activity_and_default_admission(kind, state):
    source, html = fixture('ALIBABA')
    markup = inactive_authoritative_input(kind, 'stylesheet' if state.endswith('stylesheet') else 'inline')
    if state == 'default':
        markup = markup.replace(' style="display:none"', '')
    elif state.startswith('active'):
        markup = markup.replace('display:none', 'display:block')
    if not state.startswith('hidden'):
        markup = markup.replace('https://www.alibaba.com/product-detail/Other_999999999.html', source)
    html = html.replace('</head>', markup + '</head>')
    original = ADAPTERS['ALIBABA'][1](html, source)
    frozen = deepcopy(original)
    selected = maybe_render(original, html, html.encode(), enabled=True)
    assert selected['supplier_data']['extraction_method'] == 'PUBLIC_BROWSER'
    assert selected['supplier_data']['reviews'] == [{'text': 'Useful public review', 'source_url': source}]
    assert preserves(original['supplier_data'], selected['supplier_data']) and original == frozen
    assert selected['raw_payload']['html_sha256'] == sha256(html.encode()).hexdigest()


@REAL
@pytest.mark.parametrize('kind', ['meta', 'canonical'])
@pytest.mark.parametrize('active_duplicate', [False, True])
def test_actual_duplicate_hint_ancestor_activity_is_current(kind, active_duplicate, caplog):
    hint = inactive_authoritative_input(kind, 'inline').replace(' style="display:none"', '')
    markup = '<section style="display:none">' + hint + '</section><section style="display:' + ('block' if active_duplicate else 'none') + '">' + hint + '</section>'
    original, html = extracted('ALIBABA', extra='document.body.insertAdjacentHTML("beforeend",' + json.dumps(markup) + ');')
    with caplog.at_level(logging.INFO, logger='backend.app.extraction.browser'):
        selected = maybe_render(original, html, html.encode(), enabled=True)
    if active_duplicate:
        assert selected is original and 'code=CONFLICT' in caplog.text
    else:
        assert selected['supplier_data']['extraction_method'] == 'PUBLIC_BROWSER'
        assert preserves(original['supplier_data'], selected['supplier_data'])
        assert selected['raw_payload']['html_sha256'] == sha256(html.encode()).hexdigest()


@REAL
def test_actual_private_cssom_snapshot_limit_preserves_http(caplog):
    program = 'document.querySelector("style").sheet.cssRules[0].style.setProperty("--large","x".repeat(2000001));'
    source, html = fixture('ALIBABA', extra=program)
    html = html.replace('</head>', '<style>.unused{display:block}</style></head>')
    original = ADAPTERS['ALIBABA'][1](html, source)
    frozen = deepcopy(original)
    with caplog.at_level(logging.INFO, logger='backend.app.extraction.browser'):
        selected = maybe_render(original, html, html.encode(), enabled=True)
    assert selected is original and selected == frozen
    assert 'code=DOM_LIMIT' in caplog.text


@REAL
@pytest.mark.parametrize('kind', ['meta', 'canonical'])
def test_actual_private_stylesheet_delimiter_preserves_metadata_structure_evidence_and_hash(kind):
    import asyncio
    from selectolax.parser import HTMLParser
    foreign = 'https://www.alibaba.com/product-detail/Other_999999999.html'
    markup = (f"<meta property='og:url' content='{foreign}'>" if kind == 'meta'
        else f"<link rel='canonical' href='{foreign}'>")
    value = '"</style>' + markup + '"'
    program = 'document.querySelector("style").sheet.cssRules[0].style.setProperty("--label",' + json.dumps(value) + ');'
    source, html = fixture('ALIBABA', extra=program)
    html = html.replace('</head>', '<style id="authored-sheet">.unused{display:block}</style></head>')
    collected = asyncio.run(collect_isolated(html))
    snapshot = json.loads(collected['authored'])
    assert len(HTMLParser(snapshot['html']).css('meta, link')) == 0
    assert '<style id="authored-sheet"></style>' in snapshot['html']
    assert '</style>' + markup in snapshot['sheets'][0]['css']
    assert snapshot['sheets'][0]['media'] == '' and snapshot['sheets'][0]['disabled'] is False
    original = ADAPTERS['ALIBABA'][1](html, source)
    frozen = deepcopy(original)
    selected = maybe_render(original, html, html.encode(), enabled=True)
    assert selected['supplier_data']['extraction_method'] == 'PUBLIC_BROWSER'
    assert selected['supplier_data']['reviews'] == [{'text': 'Useful public review', 'source_url': source}]
    assert preserves(original['supplier_data'], selected['supplier_data']) and original == frozen
    assert selected['raw_payload']['public_fields']['review_bodies'] == [dict(
        text='Useful public review', source_url=source, original_length=20, truncated=False)]
    assert selected['raw_payload']['html_sha256'] == sha256(html.encode()).hexdigest()


@REAL
@pytest.mark.parametrize('platform', ADAPTERS)
def test_actual_changed_foreign_canonical_preserves_http(platform, caplog):
    foreign = {
        '1688': 'https://detail.1688.com/offer/999999999.html',
        'TAOBAO': 'https://shop999999999.taobao.com/',
        'ALIBABA': 'https://www.alibaba.com/product-detail/Other_999999999.html',
    }[platform]
    source, html = fixture(platform, extra='document.querySelector(\'link[rel="canonical"]\').href=' + json.dumps(foreign) + ';')
    if platform != '1688':
        html = html.replace('</head>', f'<link rel="canonical" href="{source}"></head>')
    original = ADAPTERS[platform][1](html, source)
    assert original['extraction_status'] == 'PARTIAL'
    with caplog.at_level(logging.INFO, logger='backend.app.extraction.browser'):
        selected = maybe_render(original, html, html.encode(), enabled=True)
    assert selected is original
    assert 'code=CONFLICT' in caplog.text
    assert 'rendered_html_sha256' not in selected['raw_payload']


@REAL
def test_actual_rendered_model_tampering_keeps_original_authoritative_evidence():
    name = json.dumps([ord(char) for char in 'detailData'])
    program = ('const modelName=' + name + '.map(n=>String.fromCharCode(n)).join(\'\');'
               'window[modelName].globalData.product.productId="999999999";'
               'window[modelName].globalData.seller.companyName="Foreign supplier";'
               'document.querySelector(\'script\').textContent="window."+modelName+"={};";')
    original, html = extracted('ALIBABA', extra=program)
    assert original['extraction_status'] == 'PARTIAL'
    selected = maybe_render(original, html, html.encode(), enabled=True)
    assert selected['supplier_data']['extraction_method'] == 'PUBLIC_BROWSER'
    assert selected['supplier_data']['supplier_name'] == 'Public supplier'
    assert preserves(original['supplier_data'], selected['supplier_data'])
    assert 'Foreign supplier' not in json.dumps(selected)
    assert selected['raw_payload']['html_sha256'] == sha256(html.encode()).hexdigest()


@REAL
def test_actual_collector_conditional_root_opacity_hides_selected_evidence():
    import asyncio
    from backend.app.extraction.browser_runner import _reparse
    source, _ = fixture(render=False)
    html = ('<html><head><link rel="canonical" href="' + source + '">'
            '<style>@media (min-width:1px){html{opacity:0}}</style></head>'
            '<body><div class="shop-company-name"><h1>Invisible supplier</h1></div>'
            '<div class="review-item">Invisible review</div></body></html>')
    collected = asyncio.run(collect_isolated(html))
    after = _reparse(collected['dom'], html, dict(platform='1688', source_url=source, analysis_mode='ACCOUNT_PUBLIC'), collected['authored'])
    assert after['extraction_status'] == 'PARSE_FAILED'
    assert 'supplier_data' not in after and 'raw_payload' not in after


@REAL
def test_actual_collector_does_not_recascade_after_sibling_removal():
    import asyncio
    from backend.app.extraction.browser import access_wall
    html = ('<html><head><style>.gone{display:none}.gone + .wall{display:none}</style></head>'
            '<body><i class="gone"></i><p class="wall">Please sign in</p><p>Public</p></body></html>')
    collected = asyncio.run(collect_isolated(html))
    assert access_wall(collected['dom']) is None
    assert 'Please sign in' not in collected['dom'] and 'Public' in collected['dom']
    assert '<style' not in collected['dom']


@REAL
def test_actual_near_capacity_collector_keeps_evidence_without_annotation_growth():
    import asyncio
    from backend.app.extraction.browser import MAX_BYTES
    from backend.app.extraction.browser_runner import _reparse
    source, html = fixture(render=False)
    html = html.replace('</body>', '<i></i>' * 1000 + '<div class="review-item">Public review</div></body>')
    html = html.replace('</body>', ' ' * (MAX_BYTES - 2000 - len(html.encode())) + '</body>')
    collected = asyncio.run(collect_isolated(html))
    assert collected is not None
    assert len(collected['dom'].encode()) <= MAX_BYTES
    assert len(collected['authored'].encode()) <= MAX_BYTES
    assert 'style=' not in collected['dom']
    after = _reparse(collected['dom'], html, dict(platform='1688', source_url=source, analysis_mode='ACCOUNT_PUBLIC'), collected['authored'])
    assert after['supplier_data']['supplier_name'] == 'Public supplier'
    assert after['supplier_data']['reviews'] == [{'text': 'Public review', 'source_url': source}]


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
