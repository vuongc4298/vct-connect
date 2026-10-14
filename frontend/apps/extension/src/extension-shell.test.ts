import assert from "node:assert/strict";
import test from "node:test";

import { canSubmitEnhancedEvidence, classifyExtensionPage, extensionGate } from "./extension-shell";
import { errorText, uiText } from "./ui-language";
import { restoreCollectionJob } from "./linked-capture";

test("Alibaba product, mobile storefront and Company overview share canonical identities", () => {
  const source = "https://www.alibaba.com/product-detail/2026-New-GEN5-Yiheng-Customized-Thermoforming_1601711788226.html";
  const shop = "https://yihengsportinggoods.en.alibaba.com/";
  const product = classifyExtensionPage(source + "?priceId=tracking");
  assert.equal(product.status === "supported" && product.kind, "alibaba");
  assert.equal(product.status === "supported" && product.sourceUrl, source);
  const mobile = classifyExtensionPage("https://yihengsportinggoods.m.en.alibaba.com/?productId=1601711788226");
  assert.equal(mobile.status === "supported" && mobile.kind, "alibaba-company");
  assert.equal(mobile.status === "supported" && mobile.sourceUrl, shop);
  const profile = classifyExtensionPage("https://yihengsportinggoods.m.en.alibaba.com/company_profile.html?spm=tracking");
  assert.equal(profile.status === "supported" && profile.kind, "alibaba-profile");
  assert.equal(profile.status === "supported" && profile.sourceUrl, shop + "company_profile.html");
  for (const value of ["http://yihengsportinggoods.en.alibaba.com/", "https://user@yihengsportinggoods.en.alibaba.com/", "https://yihengsportinggoods.en.alibaba.com:443/", "https://yihengsportinggoods.m.en.alibaba.com.evil.test/", "https://yihengsportinggoods.m.en.alibaba.com/contactinfo.html", "https://yihengsportinggoods.m.en.alibaba.com/company_profile.html#private"])
    assert.equal(classifyExtensionPage(value).status, "unsupported");
  const job = { id: "00000000-0000-0000-0000-000000000123", ownerId: "user_one", sourceUrl: source, startedAt: Date.now(), stage: "WAITING_FACTORY", companyUrl: shop, factoryUrl: shop + "company_profile.html" };
  assert.ok(restoreCollectionJob(job, "user_one"));
  assert.equal(restoreCollectionJob(job, "user_other"), null);
  assert.equal(uiText("Save company HTML & analyze", "vi"), "Lưu HTML hồ sơ công ty và phân tích");
});

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
  const named = classifyExtensionPage("https://hztxsy.1688.com/?offerId=778418840629");
  assert.equal(named.status === "supported" && named.kind, "1688-company");
  for (const url of ["https://detail.1688.com/", "https://sale.1688.com/", "https://login.1688.com/", "https://hztxsy.1688.com.evil.test/"])
    assert.deepEqual(classifyExtensionPage(url), { status: "unsupported" });
  const factory = classifyExtensionPage("https://sale.1688.com/factory/card.html?memberId=hztxsy&facMemId=hztxsy");
  assert.equal(factory.status === "supported" && factory.kind, "1688-factory");
  assert.equal(factory.status === "supported" && factory.sourceUrl, "https://www.1688.com/factory/hztxsy.html");
  for (const url of ["https://sale.1688.com/factory/card.html?memberId=hztxsy&facMemId=other",
    "https://sale.1688.com/factory/card.html?memberId=hztxsy&memberId=",
    "https://www.1688.com/factory/..%2Fhztxsy.html"])
    assert.deepEqual(classifyExtensionPage(url), { status: "unsupported" });
});

test("Vietnamese capture and processing messages preserve the safe failure code", () => {
  assert.equal(uiText("Save factory HTML & analyze", "vi"), "Lưu HTML nhà máy và phân tích");
  assert.equal(uiText("Save factory HTML & analyze", "en"), "Save factory HTML & analyze");
  assert.equal(uiText("Processing stopped (PROCESSING_ERROR).", "vi"), "Đã dừng xử lý (PROCESSING_ERROR).");
  assert.match(errorText("Factory company evidence is not visible or belongs to another supplier", "vi"), /không khớp nhà cung cấp/);
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
