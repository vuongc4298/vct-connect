"""Secret-free, single-attempt Chromium child. stdout is bounded selected JSON."""
import asyncio
from hashlib import sha256
import json
import sys

from .browser import MAX_BYTES

SETTLE_MILLISECONDS = 750

# Snapshot styles before changing the tree: removing siblings can change selector
# matches. Visibility-hidden ancestors retain their explicitly visible children.
# Compile an inert view: source visibility rules cannot recascade after removals.
# Retain only visibility boundaries, rather than annotating every visible node.
COLLECT_DOM = r"""function(limit) {
  // This private authored view precedes every mutation of the live tree. Shallow
  // native clones preserve selector structure/attributes without copying source
  // scripts or unrelated text. CSSOM state stays separate from selector-relevant
  // attributes; UA display defaults do not admit hints.
  if (document.adoptedStyleSheets.length) return {error:'UNREPRESENTED_STYLESHEET'};
  for (const sheet of document.styleSheets) {
    if (sheet.ownerNode?.tagName !== 'STYLE') return {error:'UNREPRESENTED_STYLESHEET'};
  }
  const sheets=new Map();
  try {
    for (const node of document.querySelectorAll('style')) {
      const sheet=node.sheet;
      const rules=sheet ? Array.from(sheet.cssRules) : [];
      if (rules.some(rule=>rule.type === 3)) return {error:'UNREPRESENTED_STYLESHEET'};
      sheets.set(node,{css:rules.map(rule=>rule.cssText).join('\n'),
        media:sheet ? sheet.media.mediaText : '', disabled:!sheet || sheet.disabled});
    }
  } catch { return {error:'UNREPRESENTED_STYLESHEET'}; }
  const root=document.documentElement.cloneNode(false);
  const pending=[[document.documentElement,root]];
  while (pending.length) {
    const [source,copy]=pending.pop();
    if (source.tagName === 'STYLE') {
      // Keep STYLE's selector position and attributes, but no raw CSS text:
      // CSSOM strings containing </style> must never become snapshot markup.
      continue;
    }
    for (const child of source.children) {
      const clone=child.cloneNode(false);
      copy.appendChild(clone);
      pending.push([child,clone]);
    }
  }
  const authored=JSON.stringify({html:root.outerHTML,
    sheets:Array.from(document.querySelectorAll('style'),node=>{
      const state=sheets.get(node);
      return {css:state.css,media:state.media,disabled:state.disabled};
    })});
  const bounded=text=>text.length <= limit && new TextEncoder().encode(text).length <= limit;
  if (!bounded(authored)) return null;
  const nodes=Array.from(document.querySelectorAll('*')).map(node => {
    const style=getComputedStyle(node);
    return {node, display:style.display, visibility:style.visibility, opacity:style.opacity};
  });
  const visibilityMap=new Map(nodes.map(({node,visibility})=>[node,visibility]));
  // Snapshotting is complete before any selector inputs are changed.
  for (const {node} of nodes) {
    node.removeAttribute('style');
    if (node.tagName === 'STYLE') node.remove();
  }
  for (const {node, display, visibility, opacity} of nodes) {
    if (!node.isConnected || ['HEAD','LINK','META','SCRIPT'].includes(node.tagName)) continue;
    if(node.hidden || node.getAttribute('aria-hidden') === 'true' ||
       display === 'none' || Number(opacity) === 0) {
      // Keep the document scaffolding and original head identity/model inputs.
      if (node === document.documentElement || node === document.body)
        node.setAttribute('style','display:none');
      else node.remove();
      continue;
    }
    if (['hidden','collapse'].includes(visibility)) {
      for (const child of Array.from(node.childNodes)) {
        if (child.nodeType === Node.TEXT_NODE) child.remove();
      }
    }
    const parentVisibility=visibilityMap.get(node.parentElement) || 'visible';
    if (visibility !== parentVisibility)
      node.setAttribute('style','visibility:'+visibility);
  }
  const text=document.documentElement.outerHTML;
  return bounded(text) ? {dom:text, authored} : null;
}"""

# Source CSP remains in force; this second policy only further restricts it.
RESTRICTION = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
               "connect-src 'none'; frame-src 'none'; child-src 'none'; worker-src 'none'; "
               "object-src 'none'; form-action 'none'; base-uri 'none'")

# These wrappers expose no state. Count denials without URLs, source labels or
# values. The observer latches access walls so a later DOM change cannot hide it.
GUARD = r"""(() => {
  const invoke=Reflect.apply;
  const native=fn=>(receiver,...args)=>invoke(fn,receiver,args);
  const exec=native(RegExp.prototype.exec);
  const matches=(pattern,value)=>exec(pattern,value) !== null;
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
      if(matches(forbidden,String(value))) return deny();
      descriptor.set.call(this,value);
    }});
  }
  const insert=Element.prototype.insertAdjacentHTML;
  lock(Element.prototype,'insertAdjacentHTML',{value:function(position,value) {
    if(matches(forbidden,String(value))) return deny();
    return insert.call(this,position,value);
  },writable:false});
  for (const key of ['write','writeln']) {
    const original=Document.prototype[key];
    lock(Document.prototype,key,{value:function(...values) {
      if(values.some(value=>matches(forbidden,String(value)))) return deny();
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
  const computedStyle=window.getComputedStyle.bind(window);
  const numeric=Number;
  const includes=native(Array.prototype.includes);
  const slice=native(String.prototype.slice);
  const lowercase=native(String.prototype.toLowerCase);
  const trim=native(String.prototype.trim);
  const whitespace=/\s+/g;
  const normalize=value=>{
    // Native exec bypasses both Symbol.replace and a replaced regexp exec.
    whitespace.lastIndex=0;
    let part, start=0, text='';
    while ((part=exec(whitespace,value)) !== null) {
      text+=slice(value,start,part.index)+' ';
      start=part.index+part[0].length;
    }
    return text+slice(value,start);
  };
  const cssValue=native(CSSStyleDeclaration.prototype.getPropertyValue);
  const createWalker=native(Document.prototype.createTreeWalker);
  const nextText=native(TreeWalker.prototype.nextNode);
  const parentElement=native(Object.getOwnPropertyDescriptor(Node.prototype,'parentElement').get);
  const textContent=native(Object.getOwnPropertyDescriptor(Node.prototype,'textContent').get);
  const tagName=native(Object.getOwnPropertyDescriptor(Element.prototype,'tagName').get);
  const attribute=native(Element.prototype.getAttribute);
  const bodyElement=native(Object.getOwnPropertyDescriptor(Document.prototype,'body').get);
  const titleText=native(Object.getOwnPropertyDescriptor(Document.prototype,'title').get);
  const nodeType=native(Object.getOwnPropertyDescriptor(Node.prototype,'nodeType').get);
  const visibleBody = () => {
    const body=bodyElement(document);
    if (!body) return '';
    const walker=createWalker(document,body,5);
    let part, text='', previousBlock=null, lineBreak=false;
    while ((part=nextText(walker)) && text.length < 2000) {
      let visible=true;
      const element=nodeType(part) === 1;
      const owner=element ? part : parentElement(part);
      let block=null;
      for (let node=owner;node;node=parentElement(node)) {
        const style=computedStyle(node);
        if (!block && includes(['block','flex','grid','table','table-cell','table-row','list-item','flow-root'],cssValue(style,'display'))) block=node;
        if (includes(['SCRIPT','STYLE','TEMPLATE','NOSCRIPT'],tagName(node)) || attribute(node,'hidden') !== null ||
            attribute(node,'aria-hidden') === 'true' || cssValue(style,'display') === 'none' ||
            numeric(cssValue(style,'opacity')) === 0 ||
            node === owner && includes(['hidden','collapse'],cssValue(style,'visibility'))) {
          visible=false;break;
        }
      }
      if (element) {
        if (visible && tagName(part) === 'BR') lineBreak=true;
        continue;
      }
      if (visible) {
        const normalized=normalize(textContent(part));
        // Inline fragments stay contiguous; only layout or authored whitespace
        // separates them. All operations here were captured before source code.
        if (normalized && text && (lineBreak || block !== previousBlock) && text[text.length-1] !== ' ') text += ' ';
        const start=text[text.length-1] === ' ' && normalized[0] === ' ' ? 1 : 0;
        text += slice(normalized,start,start+2000-text.length);
        previousBlock=block;
        lineBreak=false;
      }
    }
    return lowercase(text);
  };
  const inspect = () => {
    const title=lowercase(titleText(document) || '');
    const body=visibleBody();
    if (matches(/(captcha|verify you are human|security verification|access denied|滑动验证|安全验证|请输入验证码|访问受限)/,title+' '+body)) wall='BLOCKED';
    else if (wall !== 'BLOCKED' && (matches(/(login required|please log in|please sign in|登录后|请登录)/,title+' '+body) || matches(/^(login|sign in|登录|用户登录|会员登录|1688登录)$/,trim(title)))) wall='AUTH_REQUIRED';
    if (wall) window.stop();
  };
  new MutationObserver(inspect).observe(document,{childList:true,subtree:true,characterData:true,attributes:true});
  document.addEventListener('DOMContentLoaded',inspect);
})()"""


def _collected_views(value):
    """Validate both private strings before either is parsed or used as evidence."""
    if value is None:
        raise OverflowError("Private view capacity")
    if type(value) is not dict or set(value) != {"dom", "authored"}:
        raise ValueError("Invalid private collector envelope")
    encoded = {}
    for name in ("dom", "authored"):
        text = value[name]
        if type(text) is not str or not text:
            raise ValueError("Invalid private collector view")
        if len(text) > MAX_BYTES:
            raise OverflowError("Private view capacity")
        encoded[name] = text.encode("utf-8")
        if len(encoded[name]) > MAX_BYTES:
            raise OverflowError("Private view capacity")
    return value["dom"], encoded["dom"], value["authored"]


def _require_metadata_representation(current):
    """Decline relevant cascade inputs the supported static resolver cannot use.

    A conditional rule is safe to ignore only if it cannot affect a hint or its
    ancestors, or its sheet is disabled/definitely print-only. We do not guess
    viewport/support-query truth from a static authored snapshot.
    """
    import tinycss2
    from .dom import _specificity, _declarations, CSS_MATCH_WORK_LIMIT
    targets = set()
    for hint in current.css('link, meta'):
        node = hint
        while node is not None:
            targets.add(node.mem_id)
            node = node.parent
    if not targets:
        return
    count = sum(1 for _ in current.root.traverse())
    work = CSS_MATCH_WORK_LIMIT

    visibility_properties = {'display', 'visibility', 'opacity', 'all', 'animation', 'animation-name', 'transition', 'transition-property'}

    def declarations_represented(declarations):
        return all(list(_declarations(tinycss2.serialize([d]))) for d in declarations
                   if d.type == 'declaration' and d.lower_name in visibility_properties)

    def affects(selector):
        nonlocal work
        groups = selector.split(',')
        # Complex/unsupported selectors cannot prove irrelevance safely.
        if any(_specificity(group.strip()) is None for group in groups):
            return True
        cost = sum(count * max(1, (len(group) + 15) // 16) for group in groups)
        work -= cost
        if work < 0:
            raise ValueError('Metadata representability work limit')
        try:
            return any(node.mem_id in targets for group in groups for node in current.css(group.strip()))
        except ValueError:
            return True

    def inspect(rules, conditional=False, depth=0):
        if depth > 32:
            raise ValueError('Metadata conditional nesting limit')
        for rule in rules:
            if rule.type == 'qualified-rule':
                declarations = tinycss2.parse_declaration_list(rule.content, skip_comments=True, skip_whitespace=True)
                if any(d.type == 'declaration' and d.lower_name in visibility_properties for d in declarations):
                    selector = tinycss2.serialize(rule.prelude).strip()
                    represented = all(_specificity(group.strip()) is not None for group in selector.split(','))
                    if (conditional or not represented or not declarations_represented(declarations)) and affects(selector):
                        raise ValueError('Unrepresented metadata visibility')
            elif rule.type == 'at-rule' and rule.content is not None:
                media = tinycss2.serialize(rule.prelude).strip().lower()
                if rule.lower_at_keyword == 'media' and media in {'print', 'not all', 'not screen'}:
                    continue
                inspect(tinycss2.parse_rule_list(rule.content, skip_comments=True, skip_whitespace=True), True, depth+1)

    for node in current.root.traverse():
        if node.mem_id in targets and 'style' in node.attributes:
            declarations = tinycss2.parse_declaration_list(node.attributes['style'], skip_comments=True, skip_whitespace=True)
            if not declarations_represented(declarations):
                raise ValueError('Unrepresented inline metadata visibility')

    for style in current.css('style'):
        media = current._screen_stylesheet_media[style.mem_id]
        if media is None or media.strip().lower() in {'print', 'not all', 'not screen'}:
            continue
        if (style.attributes.get('type') or 'text/css').strip().lower() != 'text/css':
            continue
        representable = not media.strip() or any(part.strip().lower() in {'screen', 'all'} for part in media.split(','))
        inspect(tinycss2.parse_stylesheet(current._screen_stylesheet_rules[style.mem_id], skip_comments=True, skip_whitespace=True), not representable)


def _reparse(dom, original, request, authored):
    from selectolax.parser import HTMLParser
    from .dom import tree as _tree, active as _active, visibility_exhausted
    from .offer1688 import parse_1688_page
    from .taobao import parse_taobao_page
    from .alibaba import parse_alibaba_page
    tree = HTMLParser(dom)
    # Ignore globals and any scripts introduced/changed during execution. The
    # original source model and its ambiguity/identity guards stay authoritative.
    for node in tree.css("script"):
        node.decompose()
    source = _tree(original)
    failure = dict(source_url=request['source_url'], extraction_status='PARSE_FAILED', reason='PARSER_LIMIT')
    if visibility_exhausted(source):
        return failure
    snapshot = json.loads(authored)
    if type(snapshot) is not dict or set(snapshot) != {'html', 'sheets'} or type(snapshot['html']) is not str or not snapshot['html'] or type(snapshot['sheets']) is not list:
        raise ValueError('Invalid authored snapshot')
    current = _tree(snapshot['html'])
    styles = current.css('style')
    if len(styles) != len(snapshot['sheets']):
        raise ValueError('Invalid authored stylesheet count')
    media, rules = {}, {}
    for node, state in zip(styles, snapshot['sheets']):
        if (type(state) is not dict or set(state) != {'css', 'media', 'disabled'}
                or type(state['css']) is not str or type(state['media']) is not str
                or type(state['disabled']) is not bool):
            raise ValueError('Invalid authored stylesheet state')
        media[node.mem_id] = None if state['disabled'] else state['media']
        rules[node.mem_id] = state['css']
    # Private document state, never an author-provided marker or a body selector.
    current._screen_stylesheet_media = media
    current._screen_stylesheet_rules = rules
    if visibility_exhausted(current):
        return failure
    try:
        _require_metadata_representation(current)
    except ValueError:
        # A valid snapshot with unrepresented activity is an explicit failed
        # reparse, so callers retain HTTP and even an invisible root cannot gain.
        return dict(source_url=request['source_url'], extraction_status='PARSE_FAILED', reason='MALFORMED_PAGE')
    # Keep every current hint, in document order, including duplicates and hints
    # whose ancestors the evidence compiler removed. Resolve activity before
    # moving hints; carrying their original CSS would recascade body evidence.
    hints = []
    for node in current.css('link, meta'):
        admitted = _active(node)
        if 'style' in node.attributes:
            del node.attrs['style']
        if not admitted:
            node.attrs['style'] = 'display:none'
        hints.append(node.html)
    for node in tree.css('link, meta'):
        node.decompose()
    head = tree.css_first('head')
    if head is None:
        return {}
    for node in HTMLParser(''.join(hints)).css('link, meta'):
        head.insert_child(node)
    # Only original script text supplies models. Encode inactive source inputs
    # before moving them out of their original ancestor/stylesheet context.
    for node in source.css('script'):
        if not _active(node):
            node.attrs['style'] = 'display:none'
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
            # A fresh temporary profile starts its initial page in the same
            # launch operation. Starting a browser, context and page serially
            # spends the bounded attempt on renderer startup under CPU quotas.
            # No saved profile/session is supplied; Playwright removes this
            # temporary profile on close, and the supervisor owns its TMPDIR.
            context = await playwright.chromium.launch_persistent_context("", headless=True, chromium_sandbox=True, timeout=7000,
                accept_downloads=False, service_workers="block", offline=True, java_script_enabled=True,
                proxy={"server": "http://127.0.0.1:9", "bypass": "<-loopback>"},
                args=["--disable-background-networking", "--disable-component-update", "--disable-domain-reliability",
                      "--disable-sync", "--disable-breakpad", "--no-pings", "--disable-features=MediaRouter",
                      "--force-webrtc-ip-handling-policy=disable_non_proxied_udp", "--host-resolver-rules=MAP * ~NOTFOUND"])
        except (Error, TimeoutError):
            return {"code": "RUNTIME_UNAVAILABLE"}
        try:
            await context.add_init_script(GUARD)
            # The initial page is blank. Install the guard and all routes before
            # the sole cached-source navigation executes any source script.
            page = context.pages[0]
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
            # scripts in the main world. Both bounded views stay private here.
            session = await context.new_cdp_session(page)
            frame = (await session.send("Page.getFrameTree"))["frameTree"]["frame"]["id"]
            world = await session.send("Page.createIsolatedWorld", {"frameId": frame, "worldName": "vct-public-dom"})
            collected = await session.send("Runtime.callFunctionOn", {
                "executionContextId": world["executionContextId"], "returnByValue": True,
                "arguments": [{"value": MAX_BYTES}], "functionDeclaration": COLLECT_DOM})
            try:
                if ("exceptionDetails" in collected or type(collected.get('result')) is not dict
                        or 'value' not in collected['result']):
                    raise ValueError("Private collector exception")
                dom, encoded, authored = _collected_views(collected['result']['value'])
            except OverflowError:
                return {"code": "DOM_LIMIT", "denials": denials}
            except (ValueError, TypeError, UnicodeError):
                return {"code": "RUNTIME_FAILED", "denials": denials}
            try:
                outcome = _reparse(dom, html, request, authored)
            except (ValueError, TypeError, UnicodeError):
                return {"code": "RUNTIME_FAILED", "denials": denials}
            if outcome.get("extraction_status") in {"AUTH_REQUIRED", "BLOCKED"}:
                return dict(code="ACCESS_WALL", outcome=outcome, denials=denials, dom_bytes=len(encoded))
            if outcome.get("extraction_status") not in {"SUCCESS", "PARTIAL"}:
                return dict(code="CONFLICT", denials=denials, dom_bytes=len(encoded))
            return dict(code="GAIN", outcome=outcome, rendered_sha256=sha256(encoded).hexdigest(),
                        denials=denials, dom_bytes=len(encoded))
        finally:
            await context.close()


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
