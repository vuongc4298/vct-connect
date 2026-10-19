import assert from "node:assert/strict";
import test from "node:test";
import { assertPermittedEvidence, captureSelectedDom, supportedOffer, type LegacyCapture, type TaobaoCapture } from "./capture";
import { captureLinkedDom } from "./linked-capture";
import { showCompanyGuidance } from "./company-guidance";

test("Alibaba cues highlight the clickable storefront, not Company Overview, and restore styles", () => {
  const previous = globalThis.document;
  const previousStyle = globalThis.getComputedStyle;
  const shop = "https://supplier-example.en.alibaba.com/";
  const nodes = new Map<string, any>();
  const element = (textContent = "", href = "", shown = true) => {
    const attributes = new Map<string, string>();
    const handlers = new Map<string, () => void>();
    return { textContent, href, children: [] as any[], classList: { contains: () => false, add() {} },
      renderStyle: { display: "block", visibility: "visible", opacity: "1" }, parentElement: null as any,
      closest: () => null,
      style: { setProperty(name: string, value: string) { attributes.set("style", `${attributes.get("style") ?? ""}${name}:${value};`); } },
      getClientRects: () => shown ? [{}] : [], querySelector: () => null,
      setAttribute(name: string, value: string) { attributes.set(name, value); },
      getAttribute: (name: string) => attributes.get(name) ?? null,
      removeAttribute(name: string) { attributes.delete(name); }, scrollIntoView() {},
      append(child: any) { this.children.push(child); },
      addEventListener(name: string, handler: () => void) { handlers.set(name, handler); },
      dispatchEvent(event: Event) { handlers.get(event.type)?.(); },
      remove() { if ((this as any).id) nodes.delete((this as any).id); },
    };
  };
  const overview = element("Company Overview", shop + "company_profile.html");
  const logo = element("", shop);
  const supplier = element("Example supplier", "https://supplier-example.m.en.alibaba.com/?productId=123");
  const hidden = element("Hidden company", shop, false);
  const foreign = element("Another supplier", "https://other.en.alibaba.com/");
  const invisible = element("Invisible supplier", shop);
  invisible.renderStyle.visibility = "hidden";
  const transparent = element("Transparent supplier", shop);
  transparent.parentElement = element();
  transparent.parentElement.renderStyle.opacity = "0";
  const decoy = element("Company Overview");
  supplier.setAttribute("style", "color:red");
  let anchors = [overview, hidden, foreign, invisible, transparent, logo, supplier];
  try {
    Object.defineProperty(globalThis, "getComputedStyle", { configurable: true, value: (node: any) => node.renderStyle });
    Object.defineProperty(globalThis, "document", { configurable: true, value: {
      getElementById: (id: string) => nodes.get(id),
      querySelectorAll: (selector: string) => selector.includes("div,") ? [decoy] : anchors,
      createElement: () => element(), body: { append: (item: any) => nodes.set(item.id, item) },
    } });
    assert.equal(showCompanyGuidance("SHOP", shop), true);
    assert.match(supplier.getAttribute("style")!, /box-shadow/);
    for (const other of [overview, hidden, foreign, invisible, transparent, logo, decoy]) assert.equal(other.getAttribute("style"), null);
    assert.equal(nodes.get("vct-company-guidance").children.find((n: any) => n.href)?.href, shop);
    // Replacing product guidance with the next stage must restore the original supplier style.
    assert.equal(showCompanyGuidance("FACTORY", shop), true);
    assert.equal(supplier.getAttribute("style"), "color:red");
    assert.match(overview.getAttribute("style")!, /box-shadow/);
    nodes.get("vct-company-guidance").dispatchEvent(new Event("vct-dismiss"));
    assert.equal(overview.getAttribute("style"), null);
    for (const path of ["/", "/index.html"]) {
      anchors = [element("Company Overview", shop + "company_profile.html"), element("Supplier name", new URL(path, shop).href)];
      assert.equal(showCompanyGuidance("SHOP", shop, "en"), true);
      assert.equal(anchors[0].getAttribute("style"), null);
      assert.match(anchors[1].getAttribute("style")!, /box-shadow/);
    }
    // Missing/hidden/wrong-shop storefronts cannot turn a profile link into a shop cue.
    anchors = [overview, hidden, foreign, invisible, transparent];
    assert.equal(showCompanyGuidance("SHOP", shop), false);
    assert.equal(overview.getAttribute("style"), null);
    assert.equal(nodes.get("vct-company-guidance").children.find((n: any) => n.href)?.href, shop);
  } finally {
    Object.defineProperty(globalThis, "document", { configurable: true, value: previous });
    Object.defineProperty(globalThis, "getComputedStyle", { configurable: true, value: previousStyle });
  }
});

test("factory cue defaults to Vietnamese and protects its entire body from page translation", () => {
  const previous = globalThis.document;
  const appended: any[] = [];
  const element = () => ({ attributes: {} as Record<string, string>, children: [] as any[],
    style: {}, classList: {add() {}}, setAttribute(name: string, value: string) {this.attributes[name] = value;},
    append(child: any) {this.children.push(child);}, addEventListener() {}, remove() {} });
  try {
    Object.defineProperty(globalThis, "document", {configurable: true, value: {
      getElementById: () => null, querySelectorAll: () => [], createElement: element,
      body: { append: (item: any) => appended.push(item) },
    }});
    showCompanyGuidance("FACTORY", "https://hztxsy.1688.com/");
    const cue = appended[0];
    assert.equal(cue.lang, "vi");
    assert.equal(cue.attributes.translate, "no");
    assert.match(cue.children[1].textContent, /Đã lưu cửa hàng.*Lưu HTML nhà máy và phân tích/);
    assert.doesNotMatch(cue.children[1].textContent, /Saved store|choose Save/);
  } finally {
    Object.defineProperty(globalThis, "document", {configurable: true, value: previous});
  }
});

test("product shop discovery accepts wrapper markup but rejects ambiguous supplier identities", () => {
  const before = [globalThis.location, globalThis.document, globalThis.getComputedStyle];
  let anchors: unknown[] = [];
  const anchor = (href: string, shown = true) => ({ href, getClientRects: () => shown ? [{}] : [],
    closest: () => null, parentElement: null });
  try {
    Object.defineProperty(globalThis, "location", { configurable: true, value: new URL(OFFER_URL) });
    Object.defineProperty(globalThis, "document", { configurable: true, value: {
      querySelectorAll: (selector: string) => selector === "#shopNavigation a[href]" ? anchors : [],
    } });
    Object.defineProperty(globalThis, "getComputedStyle", { configurable: true,
      value: () => ({ visibility: "visible", display: "block", opacity: "1" }) });
    const shop = "https://shopabcdef123.1688.com/";
    anchors = [anchor(shop + "?offerId=996518024136"), anchor(shop), anchor("https://evil.test/"),
      anchor("https://shopother123.1688.com/", false)];
    assert.equal(captureLinkedDom("PRODUCT_LINK", OFFER_URL), shop);
    anchors.push(anchor("https://shopother123.1688.com/"));
    assert.equal(captureLinkedDom("PRODUCT_LINK", OFFER_URL), null);
    anchors = [anchor("https://hztxsy.1688.com/?offerId=778418840629&td_page_id=PC-DEFAULT-2026")];
    assert.equal(captureLinkedDom("PRODUCT_LINK", OFFER_URL), "https://hztxsy.1688.com/");
    anchors = [anchor("https://detail.1688.com/"), anchor("https://sale.1688.com/"), anchor("https://hztxsy.1688.com.evil.test/")];
    assert.equal(captureLinkedDom("PRODUCT_LINK", OFFER_URL), null);
    anchors = [];
    assert.equal(captureLinkedDom("PRODUCT_LINK", OFFER_URL), null);
  } finally {
    for (const [index, key] of ["location", "document", "getComputedStyle"].entries())
      Object.defineProperty(globalThis, key, { configurable: true, value: before[index] });
  }
});

const OFFER_URL = "https://detail.1688.com/offer/996518024136.html";

function selected1688(elements: Map<string, unknown[]>): LegacyCapture {
  const before = [globalThis.location, globalThis.document, globalThis.getComputedStyle];
  try {
    Object.defineProperty(globalThis, "location", { configurable: true, value: new URL(OFFER_URL) });
    Object.defineProperty(globalThis, "document", { configurable: true, value: {
      get cookie() { throw new Error("Cookie read"); },
      get documentElement() { throw new Error("Full document read"); },
      querySelector: () => null,
      querySelectorAll: (selector: string) => elements.get(selector) ?? [],
    }});
    Object.defineProperty(globalThis, "getComputedStyle", { configurable: true,
      value: () => ({ visibility: "visible", display: "block", opacity: "1" }) });
    return captureSelectedDom() as LegacyCapture;
  } finally {
    for (const [index, key] of ["location", "document", "getComputedStyle"].entries())
      Object.defineProperty(globalThis, key, { configurable: true, value: before[index] });
  }
}

const selectedNode = (text: string, selectors = new Map<string, unknown[]>(), shown = true) => ({
  innerText: text, getClientRects: () => shown ? [{}] : [],
  querySelectorAll: (selector: string) => selectors.get(selector) ?? [],
});

test("1688 preserves qualified prices and both SKU price and inventory, excluding hidden rows", () => {
  const sku = selectedNode("", new Map([
    [".item-label", [selectedNode("Mixed sizes")]],
    [".item-price-stock", [selectedNode("¥8.7"), selectedNode("Inventory790pc"), selectedNode("PRIVATE_SENTINEL", undefined, false)]],
  ]));
  const capture = selected1688(new Map([
    ["#mainPrice .price-component", [selectedNode("After coupon ¥0.10 first item"), selectedNode("¥8.70 Minimum order 1 piece"), selectedNode("PRIVATE_SENTINEL", undefined, false)]],
    ["#skuSelection .expand-view-item", [sku]],
  ]));
  assert.equal(capture.fields.price_details, "After coupon ¥0.10 first item | ¥8.70 Minimum order 1 piece");
  assert.deepEqual(capture.fields.sku_options, [{name: "Mixed sizes", value: "¥8.7 · Inventory790pc"}]);
  assert.ok(!JSON.stringify(capture).includes("PRIVATE_SENTINEL"));
});

test("1688 captures later attributes and distinct repeated labels without unbounded tables", () => {
  const labels = Array.from({length: 55}, (_, index) => ({
    ...selectedNode(index < 2 ? "Style" : `Attribute ${index}`),
    nextElementSibling: {...selectedNode(`Value ${index}`), classList: {contains: () => true}},
  }));
  const capture = selected1688(new Map([["#productAttributes th.ant-descriptions-item-label", labels]]));
  assert.equal(capture.fields.product_attributes?.length, 50);
  assert.deepEqual(capture.fields.product_attributes?.slice(0, 2), [{name:"Style",value:"Value 0"},{name:"Style",value:"Value 1"}]);
  assert.equal(capture.fields.product_attributes?.[40].value, "Value 40");
});

test("1688 bounds UTF-8 capture size while retaining review extents and exact zero rating", () => {
  const capture = selected1688(new Map([
    ["#productEvaluation .header-label-desc em.hl", [selectedNode("0")]],
    ["#productEvaluation .evaluation-content .content-text", Array.from({length:25}, (_, i) => selectedNode(`${i} ${"厚".repeat(3000)}`))],
  ]));
  assert.equal(capture.fields.rating, 0);
  assert.ok(new TextEncoder().encode(JSON.stringify(capture)).length <= 16384);
  assert.ok(capture.fields.reviews!.length > 0 && capture.fields.reviews!.length < 20);
  assert.equal(capture.fields.reviews![0].original_length, 3002);
  assert.equal(Array.from(capture.fields.reviews![0].text).length, 2000);
});

test("1688 prefers the visible review drawer and preserves repeated review cards", () => {
  const drawer = selectedNode("PRIVATE_BUYER_AVATAR_SENTINEL", new Map([
    [".evaluate-panel-title-star", [selectedNode("4.6 40+Number of reviews")]],
    [".evaluate-panel-title-star em.hl", [selectedNode("4.6")]],
    [".evaluate-panel-list .evaluation-content .content-info .content-text", [selectedNode("Good fabric"), selectedNode("Good fabric"), selectedNode("Different review"), selectedNode("PRIVATE_SENTINEL", undefined, false)]],
  ]));
  const capture = selected1688(new Map([
    [".ant-drawer-body .evaluate-panel-content", [drawer]],
    ["#productEvaluation .evaluation-content .content-text", [selectedNode("INLINE_DUPLICATE")]],
  ]));
  assert.equal(capture.fields.rating, 4.6);
  assert.equal(capture.fields.review_summary, "4.6 40+Number of reviews");
  assert.deepEqual(capture.fields.reviews?.map(x => x.text), ["Good fabric", "Good fabric", "Different review"]);
  assert.ok(!JSON.stringify(capture).includes("PRIVATE"));
  assert.ok(!JSON.stringify(capture).includes("INLINE_DUPLICATE"));
});

test("1688 ignores closed drawers and rejects multiple visible review panels", () => {
  const capture = selected1688(new Map([
    [".ant-drawer-body .evaluate-panel-content", [selectedNode("", undefined, false)]],
    ["#productEvaluation .evaluation-content .content-text", [selectedNode("Inline review")]],
  ]));
  assert.deepEqual(capture.fields.reviews?.map(x => x.text), ["Inline review"]);
  assert.throws(() => selected1688(new Map([[".ant-drawer-body .evaluate-panel-content", [selectedNode(""), selectedNode("")]]])), /Ambiguous/);
});

test("only a canonical HTTPS 1688 offer is supported", () => {
  assert.deepEqual(supportedOffer(`${OFFER_URL}?spm=home`), {
    sourceUrl: OFFER_URL, offerId: "996518024136",
  });
  for (const url of [
    "http://detail.1688.com/offer/996518024136.html",
    "https://evil.example/offer/996518024136.html",
    "https://detail.1688.com/offer/not-an-id.html",
    "https://detail.1688.com/offer/996518024136.html#changed",
  ]) assert.equal(supportedOffer(url), null);
});

test("capture selects bounded visible text without touching page session data", () => {
  const originalLocation = globalThis.location;
  const originalDocument = globalThis.document;
  const originalStyle = globalThis.getComputedStyle;
  const node = (text: string, visible = true) => ({
    innerText: text,
    querySelectorAll: () => [],
    getClientRects: () => visible ? [{}] : [],
  });
  const elements = new Map<string, unknown[]>([
    ["#shopNavigation .shop-company-name h1", [node("  Visible supplier \n")]],
    [".title-content h1", [node(" Dress  ")]],
    [".price", [node("unrelated price")]],
    [".company-name", [node("unrelated company")]],
    ["#mainPrice .price-info", [node("hidden price", false), node("39.00")]],
  ]);
  try {
    Object.defineProperty(globalThis, "location", { configurable: true, value: new URL(OFFER_URL) });
    Object.defineProperty(globalThis, "document", { configurable: true, value: {
      get cookie() { throw new Error("cookie was read"); },
      querySelector: () => ({ href: OFFER_URL }),
      querySelectorAll: (selectors: string) => selectors.split(", ").flatMap(s => elements.get(s) ?? []),
    } });
    Object.defineProperty(globalThis, "getComputedStyle", { configurable: true,
      value: () => ({ visibility: "visible", display: "block" }) });
    assert.deepEqual(captureSelectedDom(), {
      source_url: OFFER_URL,
      canonical_url: OFFER_URL,
      offer_id: "996518024136",
      fields: { supplier_name: "Visible supplier", product_title: "Dress", price_text: "39.00" },
    });
  } finally {
    Object.defineProperty(globalThis, "location", { configurable: true, value: originalLocation });
    Object.defineProperty(globalThis, "document", { configurable: true, value: originalDocument });
    Object.defineProperty(globalThis, "getComputedStyle", { configurable: true, value: originalStyle });
  }
});

test("capture truncates by code points without splitting a surrogate pair", () => {
  const originalLocation = globalThis.location;
  const originalDocument = globalThis.document;
  const originalStyle = globalThis.getComputedStyle;
  try {
    Object.defineProperty(globalThis, "location", { configurable: true, value: new URL(OFFER_URL) });
    Object.defineProperty(globalThis, "document", { configurable: true, value: {
      querySelector: () => null,
      querySelectorAll: (selector: string) => selector === "#shopNavigation .shop-company-name h1" ? [{
        innerText: "a".repeat(239) + "😀" + "b",
        querySelectorAll: () => [],
        getClientRects: () => [{}],
      }] : [],
    } });
    Object.defineProperty(globalThis, "getComputedStyle", { configurable: true,
      value: () => ({ visibility: "visible", display: "block" }) });
    const name = captureSelectedDom().fields.supplier_name;
    assert.equal(name, "a".repeat(239) + "😀");
    assert.equal(Array.from(name ?? "").length, 240);
  } finally {
    Object.defineProperty(globalThis, "location", { configurable: true, value: originalLocation });
    Object.defineProperty(globalThis, "document", { configurable: true, value: originalDocument });
    Object.defineProperty(globalThis, "getComputedStyle", { configurable: true, value: originalStyle });
  }
});

test("Taobao new capture admission is paused while retained adapters remain testable", () => {
  assert.equal(supportedOffer("https://item.taobao.com/item.htm?id=1076425861755&spm=track"), null);
  assert.equal(supportedOffer("https://shop159450000.world.taobao.com/category.htm?spm=track"), null);
  for (const url of ["https://item.taobao.com/item.htm?id=1&id=2", "https://item.taobao.com:443/item.htm?id=1",
    "https://user@item.taobao.com/item.htm?id=1", "https://item.taobao.com/item.htm?id=0", "https://item.taobao.com/item.htm?id=1#x",
    "https://detail.tmall.com/item.htm?id=1", "https://m.taobao.com/item.htm?id=1", "https://shop159450000.taobao.com/other.htm",
    "https://e.tb.cn/test", "https://shop0.taobao.com/", " https://item.taobao.com/item.htm?id=1"])
    assert.equal(supportedOffer(url), null, url);
});

class Element {
  parentElement: Element | null = null;
  children: Element[] = [];
  attributes: Record<string, string> = {};
  visible = true;
  nodeType = 1;
  textNodes?: (Element | { nodeType?: number; parentElement: Element; textContent: string })[];
  style = { display: "block", visibility: "visible", opacity: "1" };
  constructor(readonly classes = "", readonly innerText = "", readonly tagName = "div") {}
  get classList() { return this.classes.split(" "); }
  get href() { return this.attributes.href; }
  getAttribute(name: string) { return this.attributes[name] ?? null; }
  matches(selector: string) { return selector === "a[href]" && this.tagName === "a" && !!this.attributes.href; }
  getClientRects() { return this.visible ? [{}] : []; }
  append(...children: Element[]) { for (const child of children) { child.parentElement = this; this.children.push(child); } return this; }
  closest(_selector: string): Element | null {
    for (let node: Element | null = this; node; node = node.parentElement)
      if (["template", "noscript"].includes(node.tagName) || "hidden" in node.attributes || node.attributes["aria-hidden"] === "true") return node;
    return null;
  }
  querySelectorAll(selector: string): Element[] {
    const all = this.children.flatMap(child => [child, ...child.querySelectorAll("*")]);
    const prefix = /^\[class\*="(.+)"\]$/.exec(selector)?.[1];
    return all.filter(node => prefix ? node.classes.includes(prefix) : selector === ".shop-item-card" ? node.classList.includes("shop-item-card")
      : selector === "a[href]" ? node.tagName === "a" && !!node.attributes.href
        : selector === "link[rel]" ? node.tagName === "link" && "rel" in node.attributes : true);
  }
}

function auditedName(text: string, item = false, sticky = false): Element {
  const name = new Element("shopName--test", text);
  if (item) return new Element("leftWrap--test").append(new Element("shopNameLevelWrapper--test").append(new Element("shopNameWrap--test").append(name)));
  if (sticky) return new Element("stickyHeaderContent--test").append(new Element("leftContainer--test").append(new Element("shopInfo--test").append(name)));
  return new Element("shopInfo--test").append(new Element("leftContainer--test").append(new Element("shopNameContainer--test").append(name)));
}

function taobaoDom(url: string, root: Element, check: (capture: TaobaoCapture) => void) {
  const locationBefore = globalThis.location, documentBefore = globalThis.document, styleBefore = globalThis.getComputedStyle;
  const nodeFilterBefore = globalThis.NodeFilter;
  try {
    Object.defineProperty(globalThis, "location", { configurable: true, value: new URL(url) });
    Object.defineProperty(globalThis, "document", { configurable: true, value: {
      get cookie() { throw new Error("Source cookie read"); },
      get documentElement() { throw new Error("Full HTML read"); },
      querySelectorAll: (selector: string) => root.querySelectorAll(selector),
      createTreeWalker: (element: Element) => {
        const texts = element.textNodes ?? [{ parentElement: element, textContent: element.innerText }];
        let index = 0;
        return { nextNode: () => texts[index++] ?? null };
      },
    } });
    Object.defineProperty(globalThis, "NodeFilter", { configurable: true, value: { SHOW_TEXT: 4, SHOW_ELEMENT: 1 } });
    Object.defineProperty(globalThis, "getComputedStyle", { configurable: true, value: (node: Element) => node.style });
    check(captureSelectedDom() as TaobaoCapture);
  } finally {
    Object.defineProperty(globalThis, "location", { configurable: true, value: locationBefore });
    Object.defineProperty(globalThis, "document", { configurable: true, value: documentBefore });
    Object.defineProperty(globalThis, "getComputedStyle", { configurable: true, value: styleBefore });
    Object.defineProperty(globalThis, "NodeFilter", { configurable: true, value: nodeFilterBefore });
  }
}

test("Taobao item capture scopes title/reviews and excludes inactive or hidden evidence", () => {
  const title = new Element("ItemTitle--test").append(new Element("MainTitle--test").append(new Element("mainTitle--test", "  Paper  ")));
  const review = (text: string) => new Element("Comment--test").append(new Element("contentWrapper--test").append(new Element("content--test", text)));
  const hidden = new Element("", "", "template").append(review("INACTIVE_PRIVATE_SENTINEL"));
  const cssHidden = review("HIDDEN_PRIVATE_SENTINEL"); cssHidden.style.visibility = "hidden";
  const comments = new Element("Comments--test").append(review("  Public review  "), hidden, cssHidden);
  const shop = new Element("leftWrap--test").append(new Element("shopNameLevelWrapper--test").append(new Element("shopNameWrap--test").append(new Element("shopName--test", "  Shop  "))),
    new Element("starNum--test", " 4.9 "), new Element("storeLabelItem--test", " 平均23小时发货 "));
  const root = new Element().append(title, comments, shop, new Element("MainTitle--unrelated").append(new Element("mainTitle--unrelated", "UNRELATED_TITLE")),
    new Element("content--unrelated", "UNRELATED_REVIEW"));
  taobaoDom("https://item.taobao.com/item.htm?id=1076425861755", root, capture => {
    assert.equal(capture.source_kind, "item"); assert.equal(capture.source_id, "1076425861755");
    assert.equal(capture.fields.product_title, "  Paper  "); assert.equal(capture.fields.supplier_name, "  Shop  ");
    assert.deepEqual(capture.fields.reviews, [{ text: "  Public review  ", original_length: 17 }]);
    assert.deepEqual(capture.fields.shop_metrics, [" 4.9 ", " 平均23小时发货 "]);
    assert.doesNotMatch(JSON.stringify(capture), /PRIVATE_SENTINEL|UNRELATED/);
  });
});

test("Taobao shop captures only visible audited shelf links with observed titles", () => {
  const card = (id: string, title: string) => {
    const link = new Element("shop-item-card", "", "a"); link.attributes.href = `https://item.taobao.com/item.htm?id=${id}&spm=track`;
    const text = new Element("title--test", title); text.attributes.title = title;
    return link.append(text);
  };
  const hidden = card("2", "HIDDEN"); hidden.attributes.hidden = "";
  const shelf = new Element("shopProductShelfArea--test").append(card("1076425861755", "Paper"), hidden);
  const root = new Element().append(auditedName("Shop"), shelf, card("3", "UNRELATED"),
    new Element("starNum--test", "4.9"));
  taobaoDom("https://shop159450000.world.taobao.com/category.htm", root, capture => {
    assert.equal(capture.source_kind, "shop");
    assert.deepEqual(capture.fields.products, [{ source_url: "https://item.taobao.com/item.htm?id=1076425861755", title: "Paper" }]);
    assert.equal(capture.fields.shop_metrics, undefined);
    assert.doesNotMatch(JSON.stringify(capture), /HIDDEN|UNRELATED|4\.9/);
  });
});

test("Taobao review extents and serialized UTF-8 request stay within the byte cap", () => {
  const comments = new Element("Comments--test").append(...Array.from({ length: 20 }, () =>
    new Element("Comment--test").append(new Element("contentWrapper--test").append(new Element("content--test", "中".repeat(3000))))));
  const root = new Element().append(auditedName("Shop", true), comments);
  taobaoDom("https://item.taobao.com/item.htm?id=1076425861755", root, capture => {
    assert.ok(new TextEncoder().encode(JSON.stringify(capture)).length <= 16_384);
    assert.ok(capture.fields.reviews!.length > 0 && capture.fields.reviews!.length < 20);
    assert.equal(capture.fields.reviews![0].text.length, 2000);
    assert.equal(capture.fields.reviews![0].original_length, 3000);
  });
});

test("audited equivalent sticky/main shop names are accepted and conflicting names fail", () => {
  const url = "https://shop159450000.world.taobao.com/category.htm";
  const equivalent = new Element().append(auditedName(" Shop ", false, true), auditedName("Shop"));
  taobaoDom(url, equivalent, capture => assert.equal(capture.fields.supplier_name, " Shop "));
  const conflicting = new Element().append(auditedName("Other shop", false, true), auditedName("Shop"));
  assert.throws(() => taobaoDom(url, conflicting, () => {}), /Ambiguous shop evidence/);
});

test("rendered aria-hidden and transparent descendants are excluded from selected title and review text", () => {
  const hidden = new Element("", "PRIVATE_ARIA_TITLE"); hidden.attributes["aria-hidden"] = "true";
  const title = new Element("mainTitle--test", "Public titlePRIVATE_ARIA_TITLE").append(hidden);
  title.textNodes = [{ parentElement: title, textContent: "Public title" }, { parentElement: hidden, textContent: "PRIVATE_ARIA_TITLE" }];
  const transparent = new Element("", "PRIVATE_TRANSPARENT_REVIEW"); transparent.style.opacity = "0";
  const body = new Element("content--test", "Public reviewPRIVATE_TRANSPARENT_REVIEW").append(transparent);
  body.textNodes = [{ parentElement: body, textContent: "Public review" }, { parentElement: transparent, textContent: "PRIVATE_TRANSPARENT_REVIEW" }];
  const root = new Element().append(new Element("ItemTitle--test").append(new Element("MainTitle--test").append(title)),
    new Element("Comments--test").append(new Element("Comment--test").append(new Element("contentWrapper--test").append(body))));
  taobaoDom("https://item.taobao.com/item.htm?id=1076425861755", root, capture => {
    assert.equal(capture.fields.product_title, "Public title");
    assert.deepEqual(capture.fields.reviews, [{ text: "Public review", original_length: 13 }]);
    assert.doesNotMatch(JSON.stringify(capture), /PRIVATE_/);
  });
});

test("canonical rel tokens are case insensitive and conflicts or duplicates fail", () => {
  const url = "https://item.taobao.com/item.htm?id=1076425861755";
  const link = (rel: string, href: string) => {
    const node = new Element("", "", "link"); node.attributes = { rel, href }; return node;
  };
  for (const rel of ["alternate canonical", "CANONICAL alternate", "canonical"]) {
    taobaoDom(url, new Element().append(link(rel, url)), capture => assert.equal(capture.canonical_url, url));
    assert.throws(() => taobaoDom(url, new Element().append(link(rel, url.replace("1076425861755", "1"))), () => {}), /Canonical URL does not match/);
  }
  assert.throws(() => taobaoDom(url, new Element().append(link("canonical", url), link("ALTERNATE CANONICAL", url)), () => {}), /Ambiguous canonical/);
});

test("malformed visible shop links do not discard later valid shelf cards", () => {
  const bad = new Element("shop-item-card", "", "a"); bad.attributes.href = "https://[";
  const good = new Element("shop-item-card", "", "a"); good.attributes.href = "https://item.taobao.com/item.htm?id=1076425861755";
  const root = new Element().append(auditedName("Shop"), new Element("shopProductShelfArea--test").append(bad, good));
  taobaoDom("https://shop159450000.world.taobao.com/category.htm", root, capture => {
    assert.deepEqual(capture.fields.products, [{ source_url: good.attributes.href }]);
  });
});

test("hidden-descendant filtering preserves paragraph and line break boundaries", () => {
  const hidden = new Element("", "PRIVATE"); hidden.attributes["aria-hidden"] = "true";
  const first = new Element("", "First", "p"), second = new Element("", "Second", "p"), br = new Element("", "", "br");
  const body = new Element("content--test", "FirstPRIVATESecond\nThird").append(first, hidden, second, br);
  body.textNodes = [{ parentElement: first, textContent: "First" }, { parentElement: hidden, textContent: "PRIVATE" },
    { parentElement: second, textContent: "Second" }, br, { parentElement: second, textContent: "Third" }];
  const root = new Element().append(new Element("Comments--test").append(new Element("Comment--test").append(new Element("contentWrapper--test").append(body))));
  taobaoDom("https://item.taobao.com/item.htm?id=1076425861755", root, capture => {
    assert.deepEqual(capture.fields.reviews, [{ text: "First\nSecond\nThird", original_length: 18 }]);
  });
});

test("recommended shop names and metrics outside audited supplier ancestry are excluded", () => {
  const url = "https://item.taobao.com/item.htm?id=1076425861755";
  const unrelated = new Element("recommendation--test").append(new Element("shopName--test", "Unrelated supplier"),
    new Element("starNum--test", "UNRELATED_METRIC"));
  taobaoDom(url, new Element().append(auditedName("Actual supplier", true), unrelated), capture => {
    assert.equal(capture.fields.supplier_name, "Actual supplier");
    assert.doesNotMatch(JSON.stringify(capture), /Unrelated|UNRELATED/);
  });
  taobaoDom(url, new Element().append(unrelated), capture => assert.equal(capture.fields.supplier_name, undefined));
  taobaoDom("https://shop159450000.world.taobao.com/category.htm", new Element().append(auditedName("Actual supplier"), unrelated), capture => {
    assert.equal(capture.fields.supplier_name, "Actual supplier");
    assert.doesNotMatch(JSON.stringify(capture), /Unrelated|UNRELATED/);
  });
});


test("client privacy guard rejects credential-shaped selected evidence before submission", () => {
  for (const value of [
    { fields: { product_title: "password=secret" } },
    { fields: { supplier_name: "session=abc123" } },
    { fields: { product_title: "csrftoken=abc123" } },
    { fields: { product_title: "sid=abc123" } },
    { fields: { product_title: "foo=bar; sessionid=secret" } },
    { cookie: "session=secret" },
  ]) {
    assert.throws(() => assertPermittedEvidence(value), /sensitive page state/);
  }
  assert.doesNotThrow(() => assertPermittedEvidence({
    source_url: OFFER_URL,
    offer_id: "996518024136",
    fields: { product_title: "Public title", supplier_name: "Public supplier" },
  }));
});
