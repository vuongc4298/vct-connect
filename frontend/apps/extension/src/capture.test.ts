import assert from "node:assert/strict";
import test from "node:test";
import { captureSelectedDom, supportedOffer } from "./capture";

const OFFER_URL = "https://detail.1688.com/offer/996518024136.html";

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
    getClientRects: () => visible ? [{}] : [],
  });
  const elements = new Map<string, unknown[]>([
    [".shop-company-name h1", [node("  Visible supplier \n")]],
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
      querySelectorAll: (selector: string) => selector === ".shop-company-name h1" ? [{
        innerText: "a".repeat(239) + "😀" + "b",
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
