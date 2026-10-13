export type HtmlSource = { page: "PRODUCT" | "SHOP" | "FACTORY"; source_url: string; html: string };
export const MAX_HTML_BYTES = 2_000_000;
export const MAX_HTML_BUNDLE_BYTES = 8_000_000;

// Serialized by Chrome for injection: no globals, cookies, storage or source scripts.
export function capturePublicHtml(page: HtmlSource["page"], expected: string): HtmlSource | null {
  const current = new URL(location.href);
  const canonical = document.querySelector<HTMLLinkElement>('link[rel="canonical"]')?.href;
  if (page === "PRODUCT" && current.origin + current.pathname !== expected) throw new Error("Product changed");
  if (page === "SHOP" && current.origin + "/" !== expected) throw new Error("Shop changed");
  if (page === "FACTORY" && canonical !== expected) throw new Error("Factory changed");
  if (page === "FACTORY") {
    const ids = current.searchParams.getAll("memberId"), fac = current.searchParams.getAll("facMemId");
    const cardMatches = current.hostname === "sale.1688.com" && current.pathname === "/factory/card.html" &&
      ids.length === 1 && (!fac.length || (fac.length === 1 && fac[0] === ids[0])) &&
      expected === `https://www.1688.com/factory/${ids[0]}.html`;
    if (current.origin + current.pathname !== expected && !cardMatches) throw new Error("Factory navigation changed");
  }
  if (canonical && page !== "FACTORY" && new URL(canonical).origin + new URL(canonical).pathname !== expected) throw new Error("Canonical changed");
  function visible(node: Element): boolean {
    if (node.closest('script,style,template,noscript,[hidden],[aria-hidden="true"]')) return false;
    for (let p: Element | null = node; p; p = p.parentElement) {
      const s = getComputedStyle(p);
      if (s.display === "none" || s.visibility !== "visible" || s.opacity === "0") return false;
    }
    return true;
  }
  const blocked = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "TEMPLATE", "IFRAME", "FORM", "INPUT", "TEXTAREA", "SELECT", "BUTTON", "OBJECT", "EMBED", "SVG", "IMG", "VIDEO", "AUDIO", "SOURCE", "CANVAS"]);
  const safe = document.implementation.createHTMLDocument("VCT public evidence snapshot");
  const link = safe.createElement("link"); link.rel = "canonical"; link.href = expected; safe.head.append(link);
  let count = 0;
  function copy(node: Node, depth = 0): Node | null {
    if (++count > 30_000 || depth > 100) throw new Error("HTML snapshot too complex");
    if (node.nodeType === Node.TEXT_NODE) return safe.createTextNode(node.textContent || "");
    if (node.nodeType !== Node.ELEMENT_NODE) return null;
    const el = node as HTMLElement;
    // HTML tagName is uppercase, but SVG/MathML keep namespace-specific casing.
    if (blocked.has(el.tagName.toUpperCase()) || el.namespaceURI !== "http://www.w3.org/1999/xhtml" || !visible(el)) return null;
    const out = safe.createElement(el.tagName.toLowerCase());
    for (const key of ["id", "class"]) if (el.hasAttribute(key)) out.setAttribute(key, el.getAttribute(key)!);
    if (el.tagName === "A" && el.hasAttribute("href")) {
      try {
        const href = new URL(el.getAttribute("href")!, location.href);
        // Preserve public identities, strip tracking/query state; factory card IDs only.
        if (href.protocol === "https:" && !href.username && !href.password && !href.port &&
            (href.hostname === "1688.com" || href.hostname.endsWith(".1688.com"))) {
          const ids = href.searchParams.getAll("memberId"), fac = href.searchParams.getAll("facMemId");
          const member = href.hostname === "sale.1688.com" && href.pathname === "/factory/card.html" && ids.length === 1 &&
            (!fac.length || (fac.length === 1 && fac[0] === ids[0])) ? ids[0] : null;
          out.setAttribute("href", member && /^[a-z0-9][a-z0-9_-]{0,62}[a-z0-9]$/.test(member)
            ? `https://www.1688.com/factory/${member}.html` : href.origin + href.pathname);
        }
      } catch { /* no unsafe link */ }
    }
    for (const child of el.childNodes) { const selected = copy(child, depth + 1); if (selected) out.appendChild(selected); }
    return out;
  }
  const selectors = page === "PRODUCT"
    ? ["#shopNavigation", "#productTitle", "#mainPrice", "#productAttributes", "#skuSelection", "#shippingServices", "#mainServices", "#consign", "#officialInspection", "#productWarning", "#sizeChart", "#productPackInfo", "#description"]
    : page === "SHOP" ? ["#pcMainCompanyNameV2", "#pcV2SellerTagYear", "#pcV2MainCateLabel", "#pcV2ServiceScoreLabel", "#pcV2ServiceScoreValue", "#pcTopNav"]
      : ["#pc_card_baseinfo", "#pc_card_exhibition"];
  const roots = selectors.flatMap(selector => Array.from(document.querySelectorAll<HTMLElement>(selector)));
  if (page === "SHOP") {
    // Company introduction only, excluding neighboring recommended product modules.
    const credits = Array.from(document.querySelectorAll<HTMLAnchorElement>("#bd_2_container_0 a[href]"))
      .filter(a => a.href.split("?")[0] === expected + "page/creditdetail.html" && visible(a));
    if (credits.length > 1) throw new Error("Ambiguous company introduction");
    if (credits.length === 1) {
      const module = credits[0].closest<HTMLElement>(".module-wrapper");
      if (!module) return null;
      const wrapper = safe.createElement("div"); wrapper.id = "bd_2_container_0";
      const selected = copy(module); if (selected) wrapper.appendChild(selected); safe.body.append(wrapper);
    } else {
      const names = Array.from(document.querySelectorAll<HTMLElement>("#pcMainCompanyNameV2")).filter(visible);
      if (names.length !== 1 || !names[0].textContent?.trim()) return null;
    }
  }
  for (const root of roots) {
    if (roots.some(other => other !== root && other.contains(root))) continue;
    const selected = copy(root); if (selected) safe.body.appendChild(selected);
  }
  if (page === "PRODUCT") {
    // Review bodies only: never clone buyer names, avatars, orders or account controls.
    const drawer = Array.from(document.querySelectorAll<HTMLElement>(".ant-drawer-body .evaluate-panel-content")).filter(visible);
    if (drawer.length > 1) throw new Error("Ambiguous review drawer");
    const reviews = drawer.length ? drawer[0].querySelectorAll<HTMLElement>(".evaluate-panel-list .evaluation-content .content-info .content-text")
      : document.querySelectorAll<HTMLElement>("#productEvaluation .evaluation-content .content-text");
    const section = safe.createElement("section"); section.id = "vct-review-bodies";
    for (const body of Array.from(reviews).filter(visible).slice(0, 20)) {
      const card = safe.createElement("div"); card.className = "review-item";
      const selected = copy(body); if (selected) card.appendChild(selected); section.append(card);
    }
    safe.body.append(section);
  }
  if (!safe.body.textContent?.trim()) return null;
  const html = "<!doctype html>" + safe.documentElement.outerHTML;
  if (new TextEncoder().encode(html).length > 2_000_000) throw new Error("HTML snapshot exceeds 2 MB");
  return { page, source_url: expected, html };
}
