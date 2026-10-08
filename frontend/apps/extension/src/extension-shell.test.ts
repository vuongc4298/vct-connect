import assert from "node:assert/strict";
import test from "node:test";

import { canSubmitEnhancedEvidence, classifyExtensionPage, extensionGate } from "./extension-shell";

test("extension shell detects supported 1688 and Taobao pages", () => {
  const offer = classifyExtensionPage("https://detail.1688.com/offer/123456789012.html?spm=tracking");
  const item = classifyExtensionPage("https://item.taobao.com/item.htm?id=123456789");
  const shop = classifyExtensionPage("https://shop123456.taobao.com/");
  assert.deepEqual(offer, {
    status: "supported",
    sourceUrl: "https://detail.1688.com/offer/123456789012.html",
    sourceId: "123456789012",
    kind: "1688",
  });
  assert.equal(item.status, "supported");
  assert.equal(item.status === "supported" && item.kind, "taobao-item");
  assert.equal(shop.status, "supported");
  assert.equal(shop.status === "supported" && shop.kind, "taobao-shop");
  assert.deepEqual(classifyExtensionPage("https://example.org/"), { status: "unsupported" });
});

test("enhanced submission requires loaded auth, sign-in, and a supported page", () => {
  const supported = classifyExtensionPage("https://detail.1688.com/offer/123456789012.html");
  const unsupported = classifyExtensionPage("https://example.org/");
  assert.equal(extensionGate({ authLoaded: false, signedIn: false, page: supported }), "loading-auth");
  assert.equal(extensionGate({ authLoaded: true, signedIn: false, page: supported }), "signed-out");
  assert.equal(extensionGate({ authLoaded: true, signedIn: true, page: { status: "checking" } }), "checking-page");
  assert.equal(extensionGate({ authLoaded: true, signedIn: true, page: unsupported }), "unsupported-page");
  const ready = extensionGate({ authLoaded: true, signedIn: true, page: supported });
  assert.equal(ready, "ready");
  assert.equal(canSubmitEnhancedEvidence(ready), true);
  assert.equal(canSubmitEnhancedEvidence("signed-out"), false);
  assert.equal(canSubmitEnhancedEvidence("unsupported-page"), false);
});
