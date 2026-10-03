"""Secret-free, single-attempt Chromium child. stdout is bounded selected JSON."""
import asyncio
from hashlib import sha256
import json
import sys

from .browser import MAX_BYTES

SETTLE_MILLISECONDS = 750

# Source CSP remains in force; this second policy only further restricts it.
RESTRICTION = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
               "connect-src 'none'; frame-src 'none'; child-src 'none'; worker-src 'none'; "
               "object-src 'none'; form-action 'none'; base-uri 'none'")

# These wrappers expose no state. Count denials without URLs, source labels or
# values. The observer latches access walls so a later DOM change cannot hide it.
GUARD = r"""(() => {
  let denials = 0;
  const report = () => { denials=Math.min(denials+1,2000000); };
  const deny = function() { report(); throw new DOMException('Unavailable', 'SecurityError'); };
  const lock = (obj, key, descriptor) => { try { Object.defineProperty(obj, key, {...descriptor, configurable:false}); } catch {} };
  lock(globalThis,'globalThis',{value:globalThis,writable:false});
  for (const key of ['localStorage','sessionStorage','indexedDB','caches']) lock(globalThis,key,{get:deny});
  lock(Document.prototype,'cookie',{get:() => '',set:deny});
  for (const key of ['WebSocket','WebTransport','RTCPeerConnection','webkitRTCPeerConnection','Worker','SharedWorker'])
    lock(globalThis,key,{value:deny,writable:false});
  for (const key of ['open','fetch']) lock(globalThis,key,{value:deny,writable:false});
  lock(XMLHttpRequest.prototype,'open',{value:deny,writable:false});
  lock(Navigator.prototype,'sendBeacon',{value:deny,writable:false});
  if (globalThis.ServiceWorkerContainer) lock(ServiceWorkerContainer.prototype,'register',{value:deny,writable:false});
  const create = Document.prototype.createElement;
  lock(Document.prototype,'createElement',{value:function(tag,...args) {
    if (['iframe','frame','object','embed'].includes(String(tag).toLowerCase())) return deny();
    return create.call(this,tag,...args);
  },writable:false});
  const forbidden = /<\s*(?:[\w.-]+:)?(?:iframe|frame|object|embed)\b/i;
  const forbiddenElement = node => node?.namespaceURI &&
    ['iframe','frame','object','embed'].includes(node.localName?.toLowerCase());
  const unsafeNode = node => node && typeof node === 'object' &&
    (forbiddenElement(node) || Array.from(node.querySelectorAll?.('*') || []).some(forbiddenElement));
  for (const key of ['innerHTML','outerHTML']) {
    const descriptor=Object.getOwnPropertyDescriptor(Element.prototype,key);
    lock(Element.prototype,key,{get:descriptor.get,set:function(value) {
      if(forbidden.test(String(value))) return deny();
      descriptor.set.call(this,value);
    }});
  }
  const insert=Element.prototype.insertAdjacentHTML;
  lock(Element.prototype,'insertAdjacentHTML',{value:function(position,value) {
    if(forbidden.test(String(value))) return deny();
    return insert.call(this,position,value);
  },writable:false});
  for (const key of ['write','writeln']) {
    const original=Document.prototype[key];
    lock(Document.prototype,key,{value:function(...values) {
      if(values.some(value=>forbidden.test(String(value)))) return deny();
      return original.apply(this,values);
    },writable:false});
  }
  const createNS=Document.prototype.createElementNS;
  lock(Document.prototype,'createElementNS',{value:function(ns,tag,...args) {
    if(['iframe','frame','object','embed'].includes(String(tag).split(':').pop().toLowerCase())) return deny();
    return createNS.call(this,ns,tag,...args);
  },writable:false});
  for (const [prototype,keys] of [[Node.prototype,['appendChild','insertBefore','replaceChild']],
      [Element.prototype,['append','prepend','before','after','replaceWith','replaceChildren','insertAdjacentElement']],
      [Range.prototype,['insertNode']]]) {
    for (const key of keys) {
      const original=prototype[key];
      lock(prototype,key,{value:function(...values) {
        if(values.some(unsafeNode)) return deny();
        return original.apply(this,values);
      },writable:false});
    }
  }
  document.addEventListener('click', e => { const a=e.target.closest?.('a'); if(a) {e.preventDefault();report();} },true);
  document.addEventListener('submit', e => {e.preventDefault();report();},true);
  document.addEventListener('securitypolicyviolation',report);
  let wall = null;
  lock(globalThis,'__vctAccess',{get:()=>wall});
  lock(globalThis,'__vctDenials',{get:()=>denials});
  const inspect = () => {
    const title=(document.title || '').toLowerCase();
    const body=(document.body?.innerText || '').slice(0,2000).toLowerCase();
    if (/(captcha|verify you are human|security verification|access denied|滑动验证|安全验证|请输入验证码|访问受限)/.test(title+' '+body)) wall='BLOCKED';
    else if (/(login required|please log in|please sign in|登录后|请登录)/.test(title+' '+body) || /^(login|sign in|登录|用户登录|会员登录|1688登录)$/.test(title.trim())) wall='AUTH_REQUIRED';
    if (wall) window.stop();
  };
  new MutationObserver(inspect).observe(document,{childList:true,subtree:true,characterData:true});
  document.addEventListener('DOMContentLoaded',inspect);
})()"""


def _reparse(dom, original, request):
    from selectolax.parser import HTMLParser
    from .dom import tree as _tree
    from .offer1688 import parse_1688_page
    from .taobao import parse_taobao_page
    from .alibaba import parse_alibaba_page
    tree = HTMLParser(dom)
    # Ignore globals and any scripts introduced/changed during execution. The
    # original source model and its ambiguity/identity guards stay authoritative.
    for node in tree.css("script"):
        node.decompose()
    source = _tree(original)
    scripts = "".join(node.html for node in source.css("script"))
    body = tree.css_first("body")
    if body is None:
        return {}
    parser = {"1688": parse_1688_page, "TAOBAO": parse_taobao_page, "ALIBABA": parse_alibaba_page}[request["platform"]]
    reparsed = tree.html.replace("</body>", scripts + "</body>")
    return parser(reparsed, request["source_url"], analysis_mode=request["analysis_mode"])


async def render(request):
    from playwright.async_api import async_playwright
    from playwright.async_api import Error, TimeoutError
    html = request["html"]
    if len(html.encode("utf-8")) > MAX_BYTES:
        return {"code": "INPUT_LIMIT"}
    from selectolax.parser import HTMLParser
    cached = HTMLParser(html)
    frames = cached.css("iframe, frame, object, embed")
    frame_denials = len(frames)
    for node in frames:
        node.decompose()
    safe_html = cached.html
    if len(safe_html.encode("utf-8")) > MAX_BYTES:
        return {"code": "INPUT_LIMIT"}
    denials = 0
    def denied(*_):
        nonlocal denials
        denials = min(denials + 1, MAX_BYTES)
    consumed = False
    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch(headless=True, chromium_sandbox=True, timeout=7000,
                proxy={"server": "http://127.0.0.1:9", "bypass": "<-loopback>"},
                args=["--disable-background-networking", "--disable-component-update", "--disable-domain-reliability",
                      "--disable-sync", "--disable-breakpad", "--no-pings", "--disable-features=MediaRouter",
                      "--force-webrtc-ip-handling-policy=disable_non_proxied_udp", "--host-resolver-rules=MAP * ~NOTFOUND"])
        except (Error, TimeoutError):
            return {"code": "RUNTIME_UNAVAILABLE"}
        try:
            context = await browser.new_context(accept_downloads=False, service_workers="block", offline=True,
                                                java_script_enabled=True, storage_state={"cookies": [], "origins": []})
            await context.add_init_script(GUARD)
            page = await context.new_page()
            async def route_request(route):
                nonlocal consumed
                req = route.request
                if not consumed and req.is_navigation_request() and req.frame == page.main_frame and req.url == request["source_url"]:
                    consumed = True
                    headers = {"content-type": "text/html; charset=utf-8",
                               "content-security-policy": ", ".join([*request.get("csp", []), RESTRICTION])}
                    await route.fulfill(status=200, headers=headers, body=safe_html)
                else:
                    denied()
                    await route.abort()
            await context.route("**/*", route_request)
            async def websocket(ws):
                denied()
                await ws.close()
            await context.route_web_socket("**/*", websocket)
            async def popup(other):
                if other != page:
                    denied()
                    await other.close()
            context.on("page", popup)
            page.on("download", lambda download: denied())
            page.on("dialog", lambda dialog: dialog.dismiss())
            # Access detection may stop parsing/loading. Waiting only for commit
            # avoids turning that intentional stop into a navigation timeout.
            await page.goto(request["source_url"], wait_until="commit", timeout=7000)
            # A short fixed settling window allows inline timers, with no retries
            # or waiting for remote bundles. The supervisor owns the total budget.
            await page.wait_for_timeout(SETTLE_MILLISECONDS)
            wall = await page.evaluate("globalThis.__vctAccess")
            script_denials = await page.evaluate("globalThis.__vctDenials")
            if type(script_denials) is int:
                denials = min(denials + max(0, script_denials) + frame_denials, MAX_BYTES)
            if wall in {"AUTH_REQUIRED", "BLOCKED"}:
                return dict(code="ACCESS_WALL", denials=denials,
                            outcome=dict(source_url=request["source_url"], extraction_status=wall))
            if page.url != request["source_url"]:
                return {"code": "CONFLICT", "denials": denials}
            # Read at most a bounded document, never globals, errors or console.
            # Native DOM APIs in an isolated world cannot be replaced by source
            # scripts in the main world. Only the bounded document is returned.
            session = await context.new_cdp_session(page)
            frame = (await session.send("Page.getFrameTree"))["frameTree"]["frame"]["id"]
            world = await session.send("Page.createIsolatedWorld", {"frameId": frame, "worldName": "vct-public-dom"})
            collected = await session.send("Runtime.callFunctionOn", {
                "executionContextId": world["executionContextId"], "returnByValue": True,
                "arguments": [{"value": MAX_BYTES}], "functionDeclaration": """function(limit) {
              for (const node of Array.from(document.querySelectorAll('body *'))) {
                if (['LINK','META'].includes(node.tagName)) continue;
                const style=getComputedStyle(node);
                if(node.hidden || node.getAttribute('aria-hidden') === 'true' ||
                   style.display === 'none' || ['hidden','collapse'].includes(style.visibility) ||
                   Number(style.opacity) === 0) node.remove();
              }
              const text=document.documentElement.outerHTML;
              return text.length <= limit && new TextEncoder().encode(text).length <= limit ? text : null;
            }"""})
            dom = collected["result"].get("value")
            if dom is None:
                return {"code": "DOM_LIMIT", "denials": denials}
            encoded = dom.encode("utf-8")
            outcome = _reparse(dom, html, request)
            if outcome.get("extraction_status") in {"AUTH_REQUIRED", "BLOCKED"}:
                return dict(code="ACCESS_WALL", outcome=outcome, denials=denials, dom_bytes=len(encoded))
            if outcome.get("extraction_status") not in {"SUCCESS", "PARTIAL"}:
                return dict(code="CONFLICT", denials=denials, dom_bytes=len(encoded))
            return dict(code="GAIN", outcome=outcome, rendered_sha256=sha256(encoded).hexdigest(),
                        denials=denials, dom_bytes=len(encoded))
        finally:
            await browser.close()


def main():
    try:
        # Escaped JSON can be larger than its bounded decoded HTML.
        raw = sys.stdin.buffer.read(MAX_BYTES * 6 + 65537)
        if len(raw) > MAX_BYTES * 6 + 65536:
            result = {"code": "INPUT_LIMIT"}
        else:
            result = asyncio.run(render(json.loads(raw)))
        output = json.dumps(result, ensure_ascii=True).encode("utf-8")
        if len(output) > MAX_BYTES:
            output = b'{"code":"OUTPUT_LIMIT"}'
    except Exception:
        output = b'{"code":"RUNTIME_FAILED"}'
    sys.stdout.buffer.write(output)


if __name__ == "__main__":
    main()
