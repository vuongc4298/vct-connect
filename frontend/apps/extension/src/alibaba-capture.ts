import type { LegacyCapture } from "./capture";
import type { FactorySelection, ShopSelection } from "./linked-capture";
import type { HtmlSource } from "./html-capture";

export function alibabaPage(value: string): { source: string; shop?: string; kind: "product" | "shop" | "profile"; id: string } | null {
  try {
    if (value.length > 2048 || /[\s\\]/.test(value) || /#|^https:\/\/[^/]*:/.test(value)) return null;
    const u = new URL(value);
    if (u.protocol !== "https:" || u.port || u.username || u.password) return null;
    const product = /^\/product-detail\/[A-Za-z0-9][A-Za-z0-9-]{0,199}_([1-9][0-9]{0,19})\.html$/.exec(u.pathname);
    if (u.hostname === "www.alibaba.com" && product) return { source: u.origin + u.pathname, kind: "product", id: product[1] };
    const store = /^([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)\.(?:m\.)?en\.alibaba\.com$/.exec(u.hostname);
    if (!store || !["/", "/index.html", "/company_profile.html"].includes(u.pathname)) return null;
    const shop = `https://${store[1]}.en.alibaba.com/`;
    return { source: u.pathname === "/company_profile.html" ? shop + "company_profile.html" : shop,
      shop, kind: u.pathname === "/company_profile.html" ? "profile" : "shop", id: store[1] };
  } catch { return null; }
}

// Chrome serializes this function. Read rendered public regions only; no page globals.
export function captureAlibabaDom(mode: "PRODUCT" | "PRODUCT_LINK" | "SHOP" | "FACTORY", expected?: string): LegacyCapture | string | ShopSelection | FactorySelection | null {
  function visible(n: HTMLElement): boolean {
    if (!n.getClientRects().length || n.closest('script,style,template,noscript,[hidden],[aria-hidden="true"]')) return false;
    for (let p: HTMLElement | null = n; p; p = p.parentElement) {
      const s = getComputedStyle(p);
      if (s.display === "none" || s.visibility !== "visible" || s.opacity === "0") return false;
    }
    return true;
  }
  function text(n: HTMLElement | null, max = 240): string | undefined {
    if (!n || !visible(n)) return;
    const walker = document.createTreeWalker(n, NodeFilter.SHOW_TEXT);
    const parts: string[] = [];
    for (let t = walker.nextNode(); t; t = walker.nextNode()) if (t.parentElement && visible(t.parentElement)) parts.push(t.textContent || "");
    return Array.from(parts.join(" ").replace(/\s+/g, " ").trim()).slice(0, max).join("") || undefined;
  }
  // Keep these rules identical in both injected functions: Chrome serializes each independently.
  function profileClaims(nameNode: HTMLElement): { name: string; value: string }[] | null {
    const allowed = ["Business type", "Country / Region", "Main Products", "Total employees", "Total Annual Revenue", "Year established", "Main Markets", "Factory Size", "Factory Country/Region", "No. of Production Lines", "Contract Manufacturing", "Annual Output Value", "Average Lead Time", "Accepted Delivery Terms", "Accepted Payment Currency", "Accepted payment methods"];
    const claims: { name: string; value: string }[] = [];
    let conflict = false;
    function quantity(value: string, area: boolean) {
      // Parse a complete bounded measurement, never a truncated numeric prefix.
      const number = "(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\\.[0-9]{1,3})?";
      const match = new RegExp(`^(?:(about|approximately|approx\\.?|below|above|less than|more than|[~<>≤≥])\\s*)?(${number})(?:\\s*[-–—−]\\s*(${number}))?\\s*(.*?)$`, "i").exec(value);
      if (!match) return null;
      const rawNumbers = [match[2], ...(match[3] ? [match[3]] : [])];
      if (rawNumbers.some(n => n.replace(/,/g, "").split(".")[0].length > 9)) return null;
      const numbers = rawNumbers.map(n => Number(n.replace(/,/g, "")));
      if (numbers.some(n => !Number.isFinite(n) || n <= 0 || n > 999_999_999 || !area && !Number.isInteger(n)) ||
          numbers.length === 2 && numbers[0] > numbers[1]) return null;
      const rawUnit = match[4].toLowerCase().replace(/\./g, "").replace(/\s+/g, " ");
      const unit = !rawUnit ? "" : area
        ? /^(?:㎡|m²|m2|sqm|sq m|square met(?:er|re)s?)$/.test(rawUnit) ? "m2"
          : /^(?:ft²|ft2|sq ft|square (?:feet|foot))$/.test(rawUnit) ? "ft2"
          : /^(?:acres?|hectares?|ha)$/.test(rawUnit) ? rawUnit.replace(/s$/, "").replace(/^ha$/, "hectare") : null
        : /^(?:production )?lines?$/.test(rawUnit) ? "lines" : null;
      return unit === null ? null : { key: JSON.stringify([match[1]?.toLowerCase() || "", numbers, unit || (area ? "" : "lines")]), unit };
    }
    function add(name: string | undefined, value: string | undefined, squareMetres = false) {
      if (!name || !value || value === "-" || !allowed.includes(name)) return;
      const measured = name === "Factory Size" || name === "No. of Production Lines";
      if (measured) {
        if (Array.from(value).length > 240) return;
        const parsed = quantity(value, name === "Factory Size");
        if (!parsed) return;
        if (squareMetres && !parsed.unit) value += " square metres";
        if (Array.from(value).length > 240) return;
      }
      const existing = claims.find(c => c.name === name);
      const comparable = (v: string) => measured ? quantity(v, name === "Factory Size")?.key
        : name === "Business type" ? v.split(",").map(role => role.trim()).sort().join(",") : v;
      if (existing && comparable(existing.value) !== comparable(value)) conflict = true;
      if (!existing) claims.push({ name, value });
    }
    const legacy = ".icbu-pc-cpCompanyOverview,.icbu-pc-cpProductionCapacity,.icbu-pc-cpTradeCapability";
    for (const region of document.querySelectorAll<HTMLElement>(legacy)) {
      for (const label of region.querySelectorAll<HTMLElement>("tr .field-title,tr.icbu-shop-table-col-item td.title")) {
        const next = label.nextElementSibling as HTMLElement | null, key = text(label, 80);
        add(key, text(next?.querySelector<HTMLElement>(".field-content") || next, key === "Factory Size" || key === "No. of Production Lines" ? 241 : 240));
      }
    }
    const aliases: Record<string, string> = { "Number of production line": "No. of Production Lines", "Floor space(㎡)": "Factory Size" };
    for (const section of document.querySelectorAll<HTMLElement>('#fresh-shop-content section[data-module-name="factoryCapability"]')) {
      // Bind adjacent values to the supplier's manufacturer capability / Production card.
      const spans = Array.from(section.querySelectorAll<HTMLElement>("span"));
      if (!spans.some(n => n.closest("section") === section && text(n, 80) === "Manufacturer capability")) continue;
      for (const label of spans) {
        const key = aliases[text(label, 80) || ""];
        if (!key) continue;
        const row = label.parentElement, group = row?.parentElement?.parentElement;
        if (row?.children.length !== 2 || row.firstElementChild !== label || row.lastElementChild?.tagName !== "SPAN" ||
            group?.closest("section") !== section || text(group.firstElementChild?.querySelector<HTMLElement>("span") || null, 80) !== "Production") continue;
        add(key, text(row.lastElementChild as HTMLElement, 241), key === "Factory Size");
      }
    }
    if (!claims.length) return null; // A loaded supplier header is not a loaded company profile.
    const hadBusinessType = claims.some(c => c.name === "Business type");
    const header = nameNode.closest(".bc-shop-shopsign-new");
    const roles = Array.from(header?.querySelectorAll<HTMLElement>(".company-type .business-type") || [])
      .flatMap(type => (text(type, 240) || "").split(",").map(role => role.trim()).filter(Boolean));
    const businessType = [...new Set(roles)].join(", ");
    if (businessType.length <= 240) add("Business type", businessType);
    if (!hadBusinessType) {
      const index = claims.findIndex(c => c.name === "Business type");
      if (index >= 0) claims.unshift(...claims.splice(index, 1));
    }
    return !conflict && claims.length <= 32 ? claims : null;
  }
  function store(value: string): string | null {
    try {
      const u = new URL(value), m = /^([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)\.(?:m\.)?en\.alibaba\.com$/.exec(u.hostname);
      return u.protocol === "https:" && !u.port && !u.username && !u.password && !u.hash && m &&
        ["/", "/index.html", "/company_profile.html"].includes(u.pathname) ? `https://${m[1]}.en.alibaba.com/` : null;
    } catch { return null; }
  }
  const own = store(location.href);
  const hints = Array.from(document.querySelectorAll<HTMLLinkElement>('link[rel="canonical"]'));
  if (hints.length > 1 || own && hints.length && store(hints[0].href) !== own) return null;
  if (mode === "PRODUCT" || mode === "PRODUCT_LINK") {
    const id = /^\/product-detail\/[A-Za-z0-9][A-Za-z0-9-]{0,199}_([1-9][0-9]{0,19})\.html$/.exec(location.pathname)?.[1];
    const source = location.origin + location.pathname;
    if (location.protocol !== "https:" || location.hostname !== "www.alibaba.com" || !id || expected && source !== expected) return null;
    if (hints.length && hints[0].href.split("?")[0] !== source) return null;
    const cards = Array.from(document.querySelectorAll<HTMLElement>(".module_unifed_company_card")).filter(visible);
    if (cards.length !== 1) return null;
    const links = Array.from(cards[0].querySelectorAll<HTMLAnchorElement>('a[href]')).filter(visible).map(a => store(a.href)).filter(Boolean);
    if (new Set(links).size !== 1) return null;
    if (mode === "PRODUCT_LINK") return links[0]!;
    const title = text(document.querySelector<HTMLElement>(".product-title-container h1"), 500);
    if (!title) return null;
    const name = Array.from(cards[0].querySelectorAll<HTMLElement>("a,div,span"))
      .find(n => !n.children.length && /(?:Co\.|Company|Limited|LTD|有限公司)/i.test(text(n) || ""));
    const price = text(document.querySelector<HTMLElement>('[data-testid="pc-purchase-price"]'), 1200);
    const fields: LegacyCapture["fields"] = { product_title: title, ...(text(name || null) ? { supplier_name: text(name || null) } : {}),
      ...(price ? { price_details: price } : {}) };
    const supplierText = text(cards[0], 2000) || "";
    const tenure = /\b[0-9]+ yrs? on Alibaba\.com/i.exec(supplierText)?.[0];
    if (tenure) fields.supplier_tenure = tenure;
    const type = /\bManufacturer\s*,?\s*Trading Company\b|\bCustom Manufacturer\b|\bManufacturer\b|\bTrading Company\b/i.exec(supplierText)?.[0];
    const metrics: { name: string; value: string }[] = type ? [{ name: "Business type", value: type }] : [];
    for (const [label, pattern] of [["Dispute rate", /Dispute rate\s*ⓘ?\s*([0-9.]+%)/i], ["Online revenue", /Online revenue\s*ⓘ?\s*(\$[0-9A-Z]+\s*[—−-]\s*\$[0-9A-Z]+)/i], ["Top buyers served", /Top buyers served\s*ⓘ?\s*([0-9]+)/i]] as const) {
      const value = pattern.exec(supplierText)?.[1]; if (value) metrics.push({ name: label, value });
    }
    if (metrics.length) fields.supplier_metrics = metrics;
    const attrs: { name: string; value: string }[] = [];
    for (const row of document.querySelectorAll<HTMLElement>('[data-testid="module-attribute-row"]')) {
      const parts = Array.from(row.children).filter((n): n is HTMLElement => n instanceof HTMLElement).map(n => text(n)).filter(Boolean);
      if (parts.length === 2 && attrs.length < 50) attrs.push({ name: parts[0]!, value: parts[1]! });
    }
    if (attrs.length) fields.product_attributes = attrs;
    const reviews = Array.from(document.querySelectorAll<HTMLElement>('.product-review .product-review-list div.r-relative.r-whitespace-normal')).filter(visible);
    fields.reviews = reviews.slice(0, 20).map(n => { const body = text(n, 100_000) || ""; return { text: Array.from(body).slice(0, 2000).join(""), original_length: Array.from(body).length }; }).filter(r => r.text);
    const summary = text(document.querySelector<HTMLElement>(".product-review"), 180) || "";
    const rating = /^([0-5](?:\.[0-9]+)?)\b/.exec(summary), count = /Based on ([0-9,]+) reviews/i.exec(summary);
    if (rating) fields.rating = Number(rating[1]);
    if (count) fields.review_count = Number(count[1].replace(/,/g, ""));
    const result = { source_url: source, offer_id: id, fields };
    while (new TextEncoder().encode(JSON.stringify(result)).length > 16_384) {
      if (fields.reviews?.length) fields.reviews.pop();
      else if (fields.product_attributes?.length) fields.product_attributes.pop();
      else return null;
    }
    return result;
  }
  if (!own) return null;
  const names = Array.from(document.querySelectorAll<HTMLElement>(".cp-name")).filter(visible);
  const name = names.length === 1 ? text(names[0]) : undefined;
  if (!name) return null;
  if (mode === "SHOP") {
    if (!["/", "/index.html"].includes(location.pathname)) return null;
    const links = Array.from(document.querySelectorAll<HTMLAnchorElement>('.nav-item a[href],.menu-link[href],.verify-details a[href],a[href]'))
      .filter(a => visible(a) && store(a.href) === own && new URL(a.href).pathname === "/company_profile.html");
    const profile = links.length ? own + "company_profile.html" : undefined;
    return { source_url: own, company_name: name, ...(profile ? { factory_url: profile } : {}) };
  }
  if (location.pathname !== "/company_profile.html") return null;
  const claims = profileClaims(names[0]);
  if (!claims) return null;
  const description = text(document.querySelector<HTMLElement>(".overview-redesign-introduction"), 1000);
  return { source_url: own + "company_profile.html", canonical_url: own + "company_profile.html", shop_url: own,
    company_name: name, claims, ...(description ? { description } : {}) };
}

// Build a small, inert HTML document with stable regions for server-side enrichment.
export function captureAlibabaHtml(page: HtmlSource["page"], expected: string, selectedProfile?: FactorySelection): HtmlSource | null {
  const current = new URL(location.href);
  const store = /^([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)\.(?:m\.)?en\.alibaba\.com$/.exec(current.hostname);
  const own = store ? `https://${store[1]}.en.alibaba.com/` : null;
  if (current.protocol !== "https:" || current.port || current.username || current.password || current.hash) return null;
  if (page === "PRODUCT" ? current.origin + current.pathname !== expected : !own ||
      (page === "SHOP" ? !["/", "/index.html"].includes(current.pathname) || own !== expected : current.pathname !== "/company_profile.html" || own + "company_profile.html" !== expected)) return null;
  const hints = Array.from(document.querySelectorAll<HTMLLinkElement>('link[rel="canonical"]'));
  if (hints.length > 1) return null;
  const canonical = hints[0]?.href;
  if (canonical) {
    const hint = new URL(canonical), m = /^([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)\.(?:m\.)?en\.alibaba\.com$/.exec(hint.hostname);
    if (hint.protocol !== "https:" || hint.port || hint.username || hint.password ||
        (own ? !m || `https://${m[1]}.en.alibaba.com/` !== own : hint.origin + hint.pathname !== expected)) return null;
  }
  function visible(n: HTMLElement): boolean {
    if (!n.getClientRects().length || n.closest('script,style,template,noscript,[hidden],[aria-hidden="true"]')) return false;
    for (let p: HTMLElement | null = n; p; p = p.parentElement) { const s = getComputedStyle(p); if (s.display === "none" || s.visibility !== "visible" || s.opacity === "0") return false; }
    return true;
  }
  function text(n: HTMLElement | null, max = 3000): string {
    if (!n || !visible(n)) return "";
    const walker = document.createTreeWalker(n, NodeFilter.SHOW_TEXT), parts: string[] = [];
    for (let t = walker.nextNode(); t; t = walker.nextNode()) if (t.parentElement && visible(t.parentElement)) parts.push(t.textContent || "");
    return Array.from(parts.join(" ").replace(/\s+/g, " ").trim()).slice(0, max).join("");
  }
  // Keep these rules identical in both injected functions: Chrome serializes each independently.
  function profileClaims(nameNode: HTMLElement): { name: string; value: string }[] | null {
    const allowed = ["Business type", "Country / Region", "Main Products", "Total employees", "Total Annual Revenue", "Year established", "Main Markets", "Factory Size", "Factory Country/Region", "No. of Production Lines", "Contract Manufacturing", "Annual Output Value", "Average Lead Time", "Accepted Delivery Terms", "Accepted Payment Currency", "Accepted payment methods"];
    const claims: { name: string; value: string }[] = [];
    let conflict = false;
    function quantity(value: string, area: boolean) {
      // Parse a complete bounded measurement, never a truncated numeric prefix.
      const number = "(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\\.[0-9]{1,3})?";
      const match = new RegExp(`^(?:(about|approximately|approx\\.?|below|above|less than|more than|[~<>≤≥])\\s*)?(${number})(?:\\s*[-–—−]\\s*(${number}))?\\s*(.*?)$`, "i").exec(value);
      if (!match) return null;
      const rawNumbers = [match[2], ...(match[3] ? [match[3]] : [])];
      if (rawNumbers.some(n => n.replace(/,/g, "").split(".")[0].length > 9)) return null;
      const numbers = rawNumbers.map(n => Number(n.replace(/,/g, "")));
      if (numbers.some(n => !Number.isFinite(n) || n <= 0 || n > 999_999_999 || !area && !Number.isInteger(n)) ||
          numbers.length === 2 && numbers[0] > numbers[1]) return null;
      const rawUnit = match[4].toLowerCase().replace(/\./g, "").replace(/\s+/g, " ");
      const unit = !rawUnit ? "" : area
        ? /^(?:㎡|m²|m2|sqm|sq m|square met(?:er|re)s?)$/.test(rawUnit) ? "m2"
          : /^(?:ft²|ft2|sq ft|square (?:feet|foot))$/.test(rawUnit) ? "ft2"
          : /^(?:acres?|hectares?|ha)$/.test(rawUnit) ? rawUnit.replace(/s$/, "").replace(/^ha$/, "hectare") : null
        : /^(?:production )?lines?$/.test(rawUnit) ? "lines" : null;
      return unit === null ? null : { key: JSON.stringify([match[1]?.toLowerCase() || "", numbers, unit || (area ? "" : "lines")]), unit };
    }
    function add(name: string | undefined, value: string | undefined, squareMetres = false) {
      if (!name || !value || value === "-" || !allowed.includes(name)) return;
      const measured = name === "Factory Size" || name === "No. of Production Lines";
      if (measured) {
        if (Array.from(value).length > 240) return;
        const parsed = quantity(value, name === "Factory Size");
        if (!parsed) return;
        if (squareMetres && !parsed.unit) value += " square metres";
        if (Array.from(value).length > 240) return;
      }
      const existing = claims.find(c => c.name === name);
      const comparable = (v: string) => measured ? quantity(v, name === "Factory Size")?.key
        : name === "Business type" ? v.split(",").map(role => role.trim()).sort().join(",") : v;
      if (existing && comparable(existing.value) !== comparable(value)) conflict = true;
      if (!existing) claims.push({ name, value });
    }
    const legacy = ".icbu-pc-cpCompanyOverview,.icbu-pc-cpProductionCapacity,.icbu-pc-cpTradeCapability";
    for (const region of document.querySelectorAll<HTMLElement>(legacy)) {
      for (const label of region.querySelectorAll<HTMLElement>("tr .field-title,tr.icbu-shop-table-col-item td.title")) {
        const next = label.nextElementSibling as HTMLElement | null, key = text(label, 80);
        add(key, text(next?.querySelector<HTMLElement>(".field-content") || next, key === "Factory Size" || key === "No. of Production Lines" ? 241 : 240));
      }
    }
    const aliases: Record<string, string> = { "Number of production line": "No. of Production Lines", "Floor space(㎡)": "Factory Size" };
    for (const section of document.querySelectorAll<HTMLElement>('#fresh-shop-content section[data-module-name="factoryCapability"]')) {
      // Bind adjacent values to the supplier's manufacturer capability / Production card.
      const spans = Array.from(section.querySelectorAll<HTMLElement>("span"));
      if (!spans.some(n => n.closest("section") === section && text(n, 80) === "Manufacturer capability")) continue;
      for (const label of spans) {
        const key = aliases[text(label, 80) || ""];
        if (!key) continue;
        const row = label.parentElement, group = row?.parentElement?.parentElement;
        if (row?.children.length !== 2 || row.firstElementChild !== label || row.lastElementChild?.tagName !== "SPAN" ||
            group?.closest("section") !== section || text(group.firstElementChild?.querySelector<HTMLElement>("span") || null, 80) !== "Production") continue;
        add(key, text(row.lastElementChild as HTMLElement, 241), key === "Factory Size");
      }
    }
    if (!claims.length) return null; // A loaded supplier header is not a loaded company profile.
    const hadBusinessType = claims.some(c => c.name === "Business type");
    const header = nameNode.closest(".bc-shop-shopsign-new");
    const roles = Array.from(header?.querySelectorAll<HTMLElement>(".company-type .business-type") || [])
      .flatMap(type => (text(type, 240) || "").split(",").map(role => role.trim()).filter(Boolean));
    const businessType = [...new Set(roles)].join(", ");
    if (businessType.length <= 240) add("Business type", businessType);
    if (!hadBusinessType) {
      const index = claims.findIndex(c => c.name === "Business type");
      if (index >= 0) claims.unshift(...claims.splice(index, 1));
    }
    return !conflict && claims.length <= 32 ? claims : null;
  }
  const safe = document.implementation.createHTMLDocument("VCT public Alibaba evidence");
  const link = safe.createElement("link"); link.rel = "canonical"; link.href = expected; safe.head.append(link);
  function section(id: string, value: string) { if (!value) return; const n = safe.createElement("section"); n.id = id; n.textContent = value; safe.body.append(n); }
  function pairs(id: string, values: { name: string; value: string }[]) {
    const section = safe.createElement("section"); section.id = id;
    for (const pair of values) { const row = safe.createElement("dl"), label = safe.createElement("dt"), value = safe.createElement("dd"); label.textContent = pair.name; value.textContent = pair.value; row.append(label, value); section.append(row); }
    if (values.length) safe.body.append(section);
  }
  if (page === "PRODUCT") {
    section("vct-alibaba-title", text(document.querySelector(".product-title-container h1"), 500));
    section("vct-alibaba-price", text(document.querySelector('[data-testid="pc-purchase-price"]'), 1200));
    const card = document.querySelector<HTMLElement>(".module_unifed_company_card");
    section("vct-alibaba-supplier", text(card, 2000));
    const suppliers = new Set<string>();
    for (const a of card?.querySelectorAll<HTMLAnchorElement>("a[href]") || []) {
      if (!visible(a)) continue;
      const u = new URL(a.href), m = /^([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)\.(?:m\.)?en\.alibaba\.com$/.exec(u.hostname);
      if (u.protocol === "https:" && !u.port && !u.username && !u.password && m && ["/", "/index.html", "/company_profile.html"].includes(u.pathname)) suppliers.add(`https://${m[1]}.en.alibaba.com/`);
    }
    if (suppliers.size !== 1) return null;
    const anchor = safe.createElement("a"); anchor.id = "vct-alibaba-shop-link"; anchor.href = [...suppliers][0]; anchor.textContent = "Supplier storefront"; safe.body.append(anchor);
    const attrs = Array.from(document.querySelectorAll<HTMLElement>('[data-testid="module-attribute-row"]')).map(row => {
      const parts = Array.from(row.children).filter((n): n is HTMLElement => n instanceof HTMLElement).map(n => text(n, 240));
      return { name: parts[0] || "", value: parts[1] || "" };
    }).filter(p => p.name && p.value).slice(0, 50);
    pairs("vct-alibaba-attributes", attrs);
    section("vct-alibaba-review-summary", text(document.querySelector(".product-review"), 180));
    const reviews = safe.createElement("section"); reviews.id = "vct-review-bodies";
    for (const n of Array.from(document.querySelectorAll<HTMLElement>('.product-review .product-review-list div.r-relative.r-whitespace-normal')).filter(visible).slice(0, 20)) {
      const body = safe.createElement("div"); body.className = "review-item"; body.textContent = text(n, 2000); reviews.append(body);
    }
    safe.body.append(reviews);
    const protections = Array.from(document.querySelectorAll<HTMLElement>("h3"))
      .filter(n => visible(n) && text(n, 80) === "Alibaba.com order protection").map(n => text(n.parentElement?.parentElement?.parentElement?.parentElement || null, 1800));
    section("vct-alibaba-policy", [...new Set(protections)].filter(value => value && !protections.some(other => other !== value && other.includes(value))).join(" "));
  } else {
    const names = Array.from(document.querySelectorAll<HTMLElement>(".cp-name")).filter(visible);
    if (names.length !== 1 || !text(names[0], 240)) return null;
    section("vct-alibaba-company-name", text(names[0], 240));
    const nav = safe.createElement("a"); nav.id = "vct-alibaba-own-shop"; nav.href = own!; nav.textContent = "Supplier storefront"; safe.body.append(nav);
    section("vct-alibaba-introduction", text(document.querySelector(page === "SHOP" ? ".hover-span.desc" : ".overview-redesign-introduction"), 1600));
    if (page === "SHOP") {
      const values = Array.from(document.querySelectorAll<HTMLElement>(".verify-details a[href]")).filter(visible).map(n => text(n, 320));
      section("vct-alibaba-shop-claims", values.join("; "));
    } else {
      const claims = profileClaims(names[0]);
      if (!claims || selectedProfile && (selectedProfile.source_url !== expected || selectedProfile.canonical_url !== expected ||
          selectedProfile.shop_url !== own || selectedProfile.company_name !== text(names[0], 240) ||
          selectedProfile.claims.length !== claims.length || claims.some(claim => !selectedProfile.claims.some(selected => selected.name === claim.name && selected.value === claim.value)))) return null;
      pairs("vct-alibaba-company-claims", claims);
      // Retain supplier values only; never the neighboring industry-average column.
      section("vct-alibaba-profile-rating", text(document.querySelector(".merchant-performance-review"), 300));
    }
  }
  if (!safe.body.textContent?.trim()) return null;
  const html = "<!doctype html>" + safe.documentElement.outerHTML;
  return new TextEncoder().encode(html).length <= 2_000_000 ? { page, source_url: expected, html } : null;
}
