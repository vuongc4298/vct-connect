import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { captureAlibabaDom, captureAlibabaHtml } from "./alibaba-capture";
import type { FactorySelection } from "./linked-capture";

// Rendered DOM double; offline Chromium also exercises the saved public layout.
class Element {
  parentElement: Element | null = null;
  children: Element[] = [];
  style = { display: "block", visibility: "visible", opacity: "1" };
  attributes: Record<string, string> = {};
  constructor(readonly tagName = "DIV", public ownText = "") {}
  append(...nodes: Element[]) { for (const n of nodes) { n.parentElement = this; this.children.push(n); } return this; }
  get firstElementChild(): Element | null { return this.children[0] || null; }
  get lastElementChild(): Element | null { return this.children.at(-1) || null; }
  get nextElementSibling(): Element | null { return this.parentElement?.children[this.parentElement.children.indexOf(this) + 1] || null; }
  getClientRects() { return this.style.display === "none" ? [] : [{}]; }
  get href() { return this.attributes.href; } set href(v: string) { this.attributes.href = v; }
  get id() { return this.attributes.id; } set id(v: string) { this.attributes.id = v; }
  get rel() { return this.attributes.rel; } set rel(v: string) { this.attributes.rel = v; }
  get textContent(): string { return this.ownText + this.children.map(n => n.textContent).join(""); }
  set textContent(v: string) { this.ownText = v; this.children = []; }
  matches(selector: string): boolean {
    return selector.split(",").some(part => {
      const chain = part.trim().split(/\s+/), last = chain.pop()!;
      const tag = /^[a-z]+/i.exec(last)?.[0], id = /#([\w-]+)/.exec(last)?.[1], cls = /\.([\w-]+)/.exec(last)?.[1];
      if (tag && this.tagName !== tag.toUpperCase() || id && this.id !== id || cls && !this.attributes.class?.split(" ").includes(cls)) return false;
      const attr = /\[([\w-]+)(?:="([^"]*)")?\]/.exec(last);
      if (attr && (!(attr[1] in this.attributes) || attr[2] !== undefined && this.attributes[attr[1]] !== attr[2])) return false;
      if (!chain.length) return true;
      for (let p = this.parentElement; p; p = p.parentElement) if (p.matches(chain.join(" "))) return true;
      return false;
    });
  }
  closest(selector: string): Element | null { for (let p: Element | null = this; p; p = p.parentElement) if (p.matches(selector)) return p; return null; }
  querySelectorAll(selector: string): Element[] { return this.children.flatMap(n => [n, ...n.querySelectorAll("*")]).filter(n => n.matches(selector)); }
  querySelector(selector: string) { return this.querySelectorAll(selector)[0] || null; }
  get outerHTML(): string {
    const escape = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
    return `<${this.tagName.toLowerCase()}${Object.entries(this.attributes).map(([k, v]) => ` ${k}="${escape(v)}"`).join("")}>${escape(this.ownText)}${this.children.map(n => n.outerHTML).join("")}</${this.tagName.toLowerCase()}>`;
  }
}
const e = (tag = "div", text = "", attrs: Record<string, string> = {}) => Object.assign(new Element(tag.toUpperCase(), text), { attributes: attrs });
const supplier = "Guangzhou Lianxian Electronic Technology Co., Ltd.";
const source = "https://gzlianxian.en.alibaba.com/company_profile.html";
const row = (key: string, value: string) => e().append(e("span", key), e("span", value));
const tableRow = (key: string, value: string) => e("tr").append(e("td", key, { class: "field-title" }), e("td").append(e("span", value, { class: "field-content" })));
const table = (...rows: Element[]) => e("table", "", { class: "icbu-pc-cpProductionCapacity" }).append(...rows);
function modern() {
  const rows = e().append(row("Number of production line", "2"), row("Floor space(㎡)", "5000"));
  const card = e().append(e().append(e("span", "Production")), rows);
  const capability = e("section", "", { "data-module-name": "factoryCapability" }).append(e("span", "Manufacturer capability"), e().append(e().append(card)));
  const header = e("header", "", { class: "bc-shop-shopsign-new" }).append(e("h2", supplier, { class: "cp-name" }),
    e("div", "", { class: "company-type" }).append(e("span", "Custom Manufacturer", { class: "business-type" })));
  const content = e("main", "", { id: "fresh-shop-content" }).append(capability);
  return { root: e().append(header, content), rows, header, content, capability };
}
function capture(root: Element, url = source, betweenCaptures?: (selected: FactorySelection | null) => void) {
  const keys = ["document", "location", "getComputedStyle", "NodeFilter"] as const;
  const previous = keys.map(key => Object.getOwnPropertyDescriptor(globalThis, key));
  const querySelectorAll = (selector: string) => root.querySelectorAll(selector);
  const head = e("head"), body = e("body"), safeRoot = e("html").append(head, body);
  const document = { querySelectorAll, querySelector: (s: string) => querySelectorAll(s)[0] || null,
    get cookie() { throw Error("Account state read"); },
    createTreeWalker(n: Element) {
      const texts = (node: Element): { parentElement: Element; textContent: string }[] => [
        ...(node.ownText ? [{ parentElement: node, textContent: node.ownText }] : []), ...node.children.flatMap(texts)];
      const nodes = texts(n); return { nextNode: () => nodes.shift() || null };
    },
    implementation: { createHTMLDocument: () => ({ head, body, documentElement: safeRoot, createElement: (tag: string) => e(tag) }) },
  };
  try {
    const values = [document, new URL(url), (n: Element) => n.style, { SHOW_TEXT: 4 }];
    keys.forEach((key, i) => Object.defineProperty(globalThis, key, { configurable: true, value: values[i] }));
    const selected = captureAlibabaDom("FACTORY") as FactorySelection | null;
    betweenCaptures?.(selected);
    return { selected, html: captureAlibabaHtml("FACTORY", source, selected || undefined) };
  } finally {
    keys.forEach((key, i) => previous[i] ? Object.defineProperty(globalThis, key, previous[i]!) : Reflect.deleteProperty(globalThis, key));
  }
}
function equalClaims(result: ReturnType<typeof capture>) {
  assert.ok(result.selected); assert.ok(result.html);
  const claims = [...result.html.html.matchAll(/<dl><dt>(.*?)<\/dt><dd>(.*?)<\/dd><\/dl>/g)].map(m => ({ name: m[1], value: m[2] }));
  assert.deepEqual(claims, result.selected.claims);
  return result.selected;
}

test("capability cards and supplier header emit identical canonical facts and inert HTML", () => {
  const result = capture(modern().root), selected = equalClaims(result);
  assert.equal(selected.company_name, supplier);
  assert.deepEqual(selected.claims, [{ name: "Business type", value: "Custom Manufacturer" },
    { name: "No. of Production Lines", value: "2" }, { name: "Factory Size", value: "5000 square metres" }]);
  assert.doesNotMatch(result.html!.html, /data-module|script|factoryCapability/);
});

test("hidden duplicates, contact widgets, recommendations and industry comparisons cannot become claims", () => {
  const f = modern();
  const hidden = row("Number of production line", "99"); hidden.style.display = "none"; f.rows.append(hidden);
  const transparent = row("Floor space(㎡)", "8888"); transparent.style.opacity = "0"; f.rows.append(transparent);
  const aria = row("Floor space(㎡)", "7777"); aria.attributes["aria-hidden"] = "true"; f.rows.append(aria);
  const popup = e().append(e("h2", "Hidden supplier", { class: "cp-name" }),
    e("div", "", { class: "company-type" }).append(e("span", "Trading Company", { class: "business-type" })));
  popup.style.display = "none"; f.header.append(popup);
  for (const module of ["supplierPerformance", "productCategories", "contactInfo"]) {
    const foreign = modern().capability; foreign.attributes["data-module-name"] = module;
    foreign.querySelectorAll("span").filter(n => n.ownText === "2").forEach(n => n.ownText = "999");
    f.content.append(foreign);
  }
  f.root.append(row("Floor space(㎡)", "PRIVATE_SENTINEL"));
  f.root.append(e("table").append(tableRow("Factory Size", "9000 square metres"), tableRow("Business type", "Trading Company")));
  assert.deepEqual(equalClaims(capture(f.root)).claims, equalClaims(capture(modern().root)).claims);
});

test("floor-space measurements reject missing, nonpositive and oversized values without truncating numbers", () => {
  for (const value of ["N/A", "--", "0", "0 m²", "-1", "1-0", "0-5000", "1000000000", "9".repeat(500),
    "1".repeat(240) + " square metres", "0".repeat(200) + "1", "5000 widgets", "5000 m² unavailable"]) {
    const f = modern(); f.rows.children[1].lastElementChild!.ownText = value;
    const claims = equalClaims(capture(f.root)).claims;
    assert.ok(!claims.some(c => c.name === "Factory Size"), value);
    f.content.append(table(tableRow("Factory Size", value)));
    assert.ok(!equalClaims(capture(f.root)).claims.some(c => c.name === "Factory Size"), `table ${value}`);
  }
});

test("floor space appends square metres only to bare quantities and preserves explicit area units", () => {
  for (const [value, expected] of [["5,000", "5,000 square metres"], ["1000-5000", "1000-5000 square metres"],
    ["5,000 ft²", "5,000 ft²"], ["1000–5000 square feet", "1000–5000 square feet"], ["2 acres", "2 acres"], ["5000 m²", "5000 m²"]]) {
    const f = modern(); f.rows.children[1].lastElementChild!.ownText = value;
    assert.equal(equalClaims(capture(f.root)).claims.find(c => c.name === "Factory Size")?.value, expected);
  }
});

test("equivalent bounded quantities and units coalesce while preserving the first displayed form", () => {
  const f = modern();
  f.rows.children[0].lastElementChild!.ownText = "2000";
  f.content.append(table(tableRow("No. of Production Lines", "2,000"), tableRow("Factory Size", "5,000 m²")));
  const claims = equalClaims(capture(f.root)).claims;
  assert.equal(claims.find(c => c.name === "No. of Production Lines")?.value, "2,000");
  assert.equal(claims.find(c => c.name === "Factory Size")?.value, "5,000 m²");
  assert.equal(claims.length, 3);
  f.rows.children[1].lastElementChild!.ownText = "5,001 square metres";
  assert.deepEqual(capture(f.root), { selected: null, html: null });
});

test("different measurement quantities or units still conflict", () => {
  for (const [key, value] of [["No. of Production Lines", "3"], ["Factory Size", "5000 square feet"], ["Factory Size", "5001 square metres"]]) {
    const f = modern(); f.content.append(table(tableRow(key, value)));
    assert.deepEqual(capture(f.root), { selected: null, html: null });
  }
});

test("visible header and table business types allow comma spacing differences", () => {
  const f = modern(); f.header.children[1].firstElementChild!.ownText = "Manufacturer,Trading Company";
  f.content.append(table(tableRow("Business type", "Manufacturer, Trading Company")));
  assert.equal(equalClaims(capture(f.root)).claims.find(c => c.name === "Business type")?.value, "Manufacturer, Trading Company");
});

test("multiple visible supplier role badges retain every explicit business role", () => {
  const f = modern(); f.header.children[1].firstElementChild!.ownText = "Manufacturer";
  f.header.children[1].append(e("span", "Trading Company", { class: "business-type" }));
  assert.equal(equalClaims(capture(f.root)).claims.find(c => c.name === "Business type")?.value, "Manufacturer, Trading Company");
  f.content.append(table(tableRow("Business type", "Trading Company,Manufacturer")));
  assert.equal(equalClaims(capture(f.root)).claims.find(c => c.name === "Business type")?.value, "Trading Company,Manufacturer");
  f.content.lastElementChild!.firstElementChild!.lastElementChild!.firstElementChild!.ownText = "Trading Company";
  assert.deepEqual(capture(f.root), { selected: null, html: null });
});

test("uncertain ranges retain their units and bounded values without inventing numerical precision", () => {
  const f = modern(); f.rows.children[0].lastElementChild!.ownText = "2-4"; f.rows.children[1].lastElementChild!.ownText = "1,000–3,000";
  assert.deepEqual(equalClaims(capture(f.root)).claims.slice(1), [{ name: "No. of Production Lines", value: "2-4" }, { name: "Factory Size", value: "1,000–3,000 square metres" }]);
  f.rows.children[1].lastElementChild!.ownText = "5,000 m²";
  assert.equal(equalClaims(capture(f.root)).claims[2].value, "5,000 m²");
  f.rows.children[1].lastElementChild!.ownText = "9".repeat(500);
  assert.ok(equalClaims(capture(f.root)).claims.every(c => Array.from(c.value).length <= 240));
});

test("legacy Yiheng table selection remains the same 15 public claims with identical HTML", () => {
  const fixture = JSON.parse(readFileSync("../backend/tests/fixtures/alibaba_guided_yiheng.json", "utf8"));
  const f = modern(); f.content.children = []; f.header.children[1].children = [];
  f.content.append(table(...fixture.factory.claims.map((pair: { name: string; value: string }) => tableRow(pair.name, pair.value))));
  assert.deepEqual(equalClaims(capture(f.root)).claims, fixture.factory.claims);
  assert.equal(fixture.factory.claims.length, 15);
});

test("conflicting claims, visible company names and foreign canonical identities reject both captures", () => {
  for (const change of ["claim", "table", "type", "name", "canonical", "duplicate-canonical", "foreign-source"]) {
    const f = modern();
    if (change === "claim") f.rows.append(row("Number of production line", "3"));
    if (change === "table") f.content.append(table(tableRow("Factory Size", "7000 square metres")));
    if (change === "type") {
      f.header.children[1].append(e("span", "Trading Company", { class: "business-type" }));
      f.content.append(table(tableRow("Business type", "Custom Manufacturer")));
    }
    if (change === "name") f.header.append(e("h2", "Foreign supplier", { class: "cp-name" }));
    if (change.includes("canonical")) f.root.append(e("link", "", { rel: "canonical", href: change === "canonical" ? "https://foreign.en.alibaba.com/company_profile.html" : source }));
    if (change === "duplicate-canonical") f.root.append(e("link", "", { rel: "canonical", href: source }));
    assert.deepEqual(capture(f.root, change === "foreign-source" ? "https://evil.test/company_profile.html" : source), { selected: null, html: null }, change);
  }
});

test("empty, loading and challenge-only profiles offer no successful company capture", () => {
  const normalHeader = modern(); normalHeader.content.children = [e("p", "Loading company profile…")];
  for (const root of [e().append(e("p", "Loading…")), e().append(e("p", "Please complete verification")),
    e().append(e("h2", supplier, { class: "cp-name" })), normalHeader.root]) assert.deepEqual(capture(root), { selected: null, html: null });
});

test("company name or claims changing between selection and HTML reject the snapshot", () => {
  for (const change of ["name", "value", "missing-claim", "new-claim"]) {
    const f = modern();
    const result = capture(f.root, source, selected => {
      assert.ok(selected);
      if (change === "name") f.header.firstElementChild!.ownText = "Different supplier";
      if (change === "value") f.rows.children[0].lastElementChild!.ownText = "3";
      if (change === "missing-claim") f.rows.children.pop();
      if (change === "new-claim") f.content.append(table(tableRow("Year established", "2020")));
    });
    assert.ok(result.selected); assert.equal(result.html, null, change);
  }
});
