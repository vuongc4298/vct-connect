import type { LegacyCapture } from "./capture";
import type { HtmlSource } from "./html-capture";

export type ShopSelection = { source_url: string; credit_url?: string; company_name?: string; factory_url?: string };
export type FactorySelection = { source_url: string; canonical_url: string; shop_url: string;
  claims: { name: string; value: string }[]; description?: string };
export type CollectionOutcome = { page: "SHOP" | "FACTORY"; status: "OK" | "NO_PERMISSION" | "LINK_UNAVAILABLE" | "UNAVAILABLE" | "TIMEOUT" };
export type SupplierBundle = { job_id: string; product: LegacyCapture; shop_url?: string;
  shop?: ShopSelection; factory?: FactorySelection; outcomes: CollectionOutcome[]; html_sources?: HtmlSource[]; html_capture_requested?: boolean; guided?: boolean };
export type CollectionJob = { id: string; ownerId: string; sourceUrl: string; startedAt: number;
  stage: "STARTING" | "SHOP" | "FACTORY" | "ASSESSING" | "ERROR" | "WAITING_COMPANY" | "WAITING_FACTORY" | "FINISHING"; companyUrl?: string; factoryUrl?: string; expiresAt?: number; error?: string; reservationUncertain?: boolean };

export function restoreCollectionJob(value: unknown, owner: string): CollectionJob | null {
  if (!value || typeof value !== "object") return null;
  const j = value as CollectionJob;
  return j.ownerId === owner && typeof j.id === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(j.id) &&
    typeof j.sourceUrl === "string" && /^https:\/\/detail\.1688\.com\/offer\/[0-9]{6,20}\.html$/.test(j.sourceUrl) &&
    typeof j.startedAt === "number" && Number.isFinite(j.startedAt) && j.startedAt >= 0 &&
    ["STARTING", "SHOP", "FACTORY", "ASSESSING", "ERROR", "WAITING_COMPANY", "WAITING_FACTORY", "FINISHING"].includes(j.stage) &&
    (j.companyUrl === undefined || (typeof j.companyUrl === "string" && shopUrl(j.companyUrl) === j.companyUrl)) &&
    (j.factoryUrl === undefined || (typeof j.factoryUrl === "string" && factoryUrl(j.factoryUrl) === j.factoryUrl)) &&
    (j.expiresAt === undefined || (typeof j.expiresAt === "number" && Number.isFinite(j.expiresAt))) &&
    (j.reservationUncertain === undefined || typeof j.reservationUncertain === "boolean") &&
    (j.error === undefined || (typeof j.error === "string" && j.error.length <= 500)) ? j : null;
}

export function shopUrl(value: string): string | null {
  try {
    const u = new URL(value);
    return u.protocol === "https:" && !u.port && !u.username && !u.password &&
      /^shop[a-z0-9]{6,30}\.1688\.com$/.test(u.hostname) && ["", "/"].includes(u.pathname)
      ? `${u.origin}/` : null;
  } catch { return null; }
}

export function factoryUrl(value: string): string | null {
  try {
    const u = new URL(value);
    if (u.protocol !== "https:" || u.port || u.username || u.password) return null;
    let member = /^\/factory\/(b2b-[a-z0-9]{6,60})\.html$/.exec(u.pathname)?.[1];
    if (u.hostname === "sale.1688.com" && u.pathname === "/factory/card.html") {
      const ids = u.searchParams.getAll("memberId"), fac = u.searchParams.getAll("facMemId");
      member = ids.length === 1 && (!fac.length || (fac.length === 1 && fac[0] === ids[0])) ? ids[0] : undefined;
    } else if (u.hostname !== "www.1688.com") return null;
    return member && /^b2b-[a-z0-9]{6,60}$/.test(member) ? `https://www.1688.com/factory/${member}.html` : null;
  } catch { return null; }
}

// Self-contained injected function. Only selected visible supplier regions are read.
export function captureLinkedDom(mode: "PRODUCT_LINK" | "SHOP" | "FACTORY" | "OPEN_FACTORY", expectedProduct?: string): string | ShopSelection | FactorySelection | null {
  function visible(n: HTMLElement): boolean {
    if (!n.getClientRects().length || n.closest('template,noscript,[hidden],[aria-hidden="true"]')) return false;
    for (let p: HTMLElement | null = n; p; p = p.parentElement) {
      const s = getComputedStyle(p);
      if (s.display === "none" || s.visibility === "hidden" || s.visibility === "collapse" || s.opacity === "0") return false;
    }
    return true;
  }
  function text(n: HTMLElement | null, max: number): string | undefined {
    if (!n || !visible(n)) return;
    const walker = document.createTreeWalker(n, NodeFilter.SHOW_TEXT);
    const parts: string[] = [];
    for (let t = walker.nextNode(); t; t = walker.nextNode()) {
      if (t.parentElement && visible(t.parentElement)) parts.push(t.textContent || "");
    }
    return Array.from(parts.join(" ").replace(/\s+/g, " ").trim()).slice(0, max).join("") || undefined;
  }
  function shop(value: string): string | null {
    try { const u = new URL(value); return u.protocol === "https:" && !u.port && !u.username && !u.password &&
      /^shop[a-z0-9]{6,30}\.1688\.com$/.test(u.hostname) && ["", "/"].includes(u.pathname) ? `${u.origin}/` : null; } catch { return null; }
  }
  function factory(value: string): string | null {
    try {
      const u = new URL(value); if (u.protocol !== "https:" || u.port || u.username || u.password) return null;
      let id = /^\/factory\/(b2b-[a-z0-9]{6,60})\.html$/.exec(u.pathname)?.[1];
      if (u.hostname === "sale.1688.com" && u.pathname === "/factory/card.html") {
        const ids = u.searchParams.getAll("memberId"), fac = u.searchParams.getAll("facMemId");
        id = ids.length === 1 && (!fac.length || (fac.length === 1 && fac[0] === ids[0])) ? ids[0] : undefined;
      } else if (u.hostname !== "www.1688.com") return null;
      return id && /^b2b-[a-z0-9]{6,60}$/.test(id) ? `https://www.1688.com/factory/${id}.html` : null;
    } catch { return null; }
  }
  if (mode === "PRODUCT_LINK") {
    if (expectedProduct && location.origin + location.pathname !== expectedProduct) throw new Error("Product changed during capture");
    const links = Array.from(document.querySelectorAll<HTMLAnchorElement>("#shopNavigation a.shop-company-name[href]"))
      .filter(visible).map(a => shop(a.href)).filter(Boolean);
    return new Set(links).size === 1 ? links[0] : null;
  }
  if (mode === "SHOP" || mode === "OPEN_FACTORY") {
    const own = shop(location.href); if (!own) return null;
    const canonical = document.querySelector<HTMLLinkElement>('link[rel="canonical"]')?.href;
    if (canonical && shop(canonical) !== own) return null;
    const credit = Array.from(document.querySelectorAll<HTMLAnchorElement>("#bd_2_container_0 a[href]"))
      .find(a => visible(a) && a.href.split("?")[0] === own + "page/creditdetail.html");
    const names = Array.from(document.querySelectorAll<HTMLElement>("#pcMainCompanyNameV2")).filter(visible);
    const companyName = names.length === 1 ? text(names[0], 240) : undefined;
    if (!credit && !companyName) return null;
    // Navigation labels only: recommended supplier cards cannot become targets.
    const nav = Array.from(document.querySelectorAll<HTMLAnchorElement>("#hd a, #shopNavigation a, #pcTopNav a"))
      .filter(a => visible(a) && /^(工厂档案|工厂介绍|工厂名片|工厂资料|Factory profile)$/i.test(text(a, 80) || ""));
    if (mode === "OPEN_FACTORY") {
      if (nav.length !== 1) return null;
      nav[0].click(); return "CLICKED";
    }
    const targets = nav.map(a => factory(a.href)).filter(Boolean);
    const profile = new Set(targets).size === 1 ? targets[0] : null;
    return { source_url: own, ...(credit ? { credit_url: credit.href.split("?")[0] } : {}), ...(companyName ? { company_name: companyName } : {}), ...(profile ? { factory_url: profile } : {}) };
  }
  const source = factory(location.href), canonical = document.querySelector<HTMLLinkElement>('link[rel="canonical"]')?.href;
  if (!source || canonical !== source) return null;
  const links = Array.from(document.querySelectorAll<HTMLAnchorElement>("#pc_card_baseinfo a[href]"))
    .filter(visible).map(a => shop(a.href)).filter(Boolean);
  if (new Set(links).size !== 1) return null;
  const permitted = ["成立时间", "年交易额", "员工总数", "定制起订量", "贴牌起订量", "接外贸订单", "加工方式", "增值税发票"];
  const claims: { name: string; value: string }[] = [];
  for (const label of document.querySelectorAll<HTMLElement>("#pc_card_exhibition .ability_info .ability_key")) {
    const name = text(label, 80), next = label.nextElementSibling as HTMLElement | null;
    const value = next?.classList.contains("ability_value") ? text(next, 240) : undefined;
    if (name && value && permitted.includes(name)) claims.push({ name, value });
    if (claims.length > 32) return null;
  }
  if (!claims.length) return null;
  const heading = Array.from(document.querySelectorAll<HTMLElement>("#pc_card_exhibition div"))
    .find(n => text(n, 1001) === "工厂展厅");
  const description = heading ? text(heading.nextElementSibling as HTMLElement | null, 1000) : undefined;
  return { source_url: source, canonical_url: source, shop_url: links[0]!, claims, ...(description ? { description } : {}) };
}
