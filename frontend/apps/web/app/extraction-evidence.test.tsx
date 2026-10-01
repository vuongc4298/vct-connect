import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import type { Analysis } from "@vct/contracts";

import { ExtractionEvidence, isFixtureResult } from "./extraction-evidence";
import { safeSourceUrl } from "./source-url";

test("Alibaba product quotation renders its USD range, unit and primary MOQ", () => {
  const source_url = "https://www.alibaba.com/product-detail/Public-shirt_1600147809763.html";
  const analysis = { result: { source_url, extraction_status: "PARTIAL" }, supplier_data: {
    platform: "ALIBABA", source_url, offer_id: "1600147809763", supplier_name: "Public supplier", years_active: 6,
    company_information: null, categories: null, certifications: null, rating: 4.7,
    products: [{ offer_id: "1600147809763", title: "Public shirt", source_url, attributes: [{ name: "MOQ", value: "10 Piece" }] }],
    price_information: { minimum: "3.26", maximum: "4.59", currency: "USD", unit: "piece", minimum_order_quantity: 2 },
    transaction_signals: { review_count: 214 }, delivery_information: null,
    completeness: 0.8333, completeness_denominator: Array(12).fill("field"), missing_fields: ["certifications", "activity_history"],
    extraction_method: "PUBLIC_HTTP", analysis_mode: "ACCOUNT_PUBLIC", extractor_version: "alibaba-http.v1", extracted_at: "2026-10-01T00:00:00Z",
  }, reviews: [] } as unknown as Analysis;
  const html = renderToStaticMarkup(<ExtractionEvidence analysis={analysis} />);
  assert.match(html, /Giá chào sản phẩm: 3\.26–4\.59 USD \/ piece · MOQ: 2/);
  assert.match(html, /MOQ: 10 Piece/);
});

test("Alibaba claims retain price and metric scopes, certificate kinds and qualified tenure", () => {
  const source_url = "https://dgxuandele.en.alibaba.com/company_profile.html";
  const product_url = "https://www.alibaba.com/product-detail/Public-shirt_1600147809763.html";
  const analysis = { result: { source_url, extraction_status: "PARTIAL" }, supplier_data: {
    platform: "ALIBABA", source_url, offer_id: null, supplier_name: "Public supplier", years_active: 6,
    company_information: { "Total employees": "43" }, categories: ["Shirts"],
    certifications: ["RoHS (PRODUCT)", "AZO (INSPECTION_REPORT)"], rating: 4.7,
    products: [{ offer_id: "1600147809763", title: "Public shirt", source_url: product_url, price_display_text: "$3.26", minimum_order_display_text: "MOQ:2 pieces" },
      { offer_id: "1", title: "Wrong identity", source_url: product_url }],
    price_information: null,
    transaction_signals: { review_count: 39, source_metrics: [{ label: "Online revenue", value: "US $100K − $200K", scope: "supplier performance" }] },
    delivery_information: { source_metrics: [{ label: "Average dispatch time", value: "25.6d", scope: "supplier performance" }] },
    completeness: 0.75, completeness_denominator: Array(12).fill("field"), missing_fields: ["reviews", "price_information", "activity_history"],
    extraction_method: "PUBLIC_HTTP", analysis_mode: "ACCOUNT_PUBLIC", extractor_version: "alibaba-http.v1", extracted_at: "2026-10-01T00:00:00Z",
  }, reviews: [] } as unknown as Analysis;
  const html = renderToStaticMarkup(<ExtractionEvidence analysis={analysis} />);
  for (const expected of ["Bằng chứng Alibaba", "Total employees: 43", "6 năm; chưa xác minh tuổi pháp nhân", "RoHS (PRODUCT)", "AZO (INSPECTION_REPORT)", "4.7/5", "supplier performance", "25.6d", "MOQ:2 pieces", "chưa được xác minh độc lập"]) assert.ok(html.includes(expected), expected);
  assert.match(html, /href="https:\/\/www\.alibaba\.com\/product-detail\/Public-shirt_1600147809763\.html"[^>]*>Public shirt/);
  assert.doesNotMatch(html, /<a[^>]*>Wrong identity/);
  assert.equal(safeSourceUrl(source_url), source_url); assert.equal(safeSourceUrl(product_url), product_url);
  for (const unsafe of [product_url + "?tracking=1", source_url.replace(".en.", ".m.en."), product_url.replace("www.alibaba.com", "www.alibaba.com:443"), product_url.replace("1600147809763", "0")]) assert.equal(safeSourceUrl(unsafe), null);
});

test("Taobao evidence preserves display context, reviews and safe source links", () => {
  const url = "https://item.taobao.com/item.htm?id=1076425861755";
  const analysis = { result: { source_url: url, extraction_status: "PARTIAL" },
    supplier_data: { platform: "TAOBAO", source_url: url, supplier_name: "Shop", products: [{ title: "Paper" }],
      completeness: 0.5, completeness_denominator: Array(12).fill("field"), missing_fields: Array(6).fill("unknown"),
      extraction_method: "PUBLIC_HTTP", analysis_mode: "ACCOUNT_PUBLIC", extractor_version: "taobao-http.v1",
      extracted_at: "2026-09-30T00:00:00+00:00", years_active: null,
      price_information: { price: { priceText: "3.35", priceTitle: "优惠前", priceUnit: "￥", priceDesc: "起" } },
      transaction_signals: { review_count_display_text: "2万+", sales_display_text: "3万+", positive_review_rate_display_text: "近3个月好评率高达100.0%" } },
    reviews: [{ text: "Public body" }] } as unknown as Analysis;
  const html = renderToStaticMarkup(<ExtractionEvidence analysis={analysis} />);
  assert.match(html, /Bằng chứng Taobao/); assert.match(html, /3\.35/); assert.match(html, /2万\+/);
  assert.match(html, /近3个月/); assert.match(html, /Public body/); assert.match(html, /Mở trang nguồn Taobao/);
  const failed = { result: { source_url: url, extraction_status: "BLOCKED" }, supplier_data: null, reviews: [] } as unknown as Analysis;
  assert.match(renderToStaticMarkup(<ExtractionEvidence analysis={failed} />), /tiện ích VCT Connect.*HTML/);
  for (const unsafe of [url + "&id=1", url + "#frag", "https://item.taobao.com:443/item.htm?id=1", "https://foo.taobao.com/", "javascript:alert(1)"]) assert.equal(safeSourceUrl(unsafe), null);
  assert.equal(safeSourceUrl("https://shop159450000.world.taobao.com/category.htm"), "https://shop159450000.world.taobao.com/category.htm");
});

test("Taobao shop evidence renders bounded products, labeled metrics and qualified shop age", () => {
  const source = "https://shop159450000.world.taobao.com/category.htm";
  const analysis = { result: { source_url: source, extraction_status: "PARTIAL" }, supplier_data: {
    platform: "TAOBAO", source_url: source, offer_id: null, supplier_name: "Shop", years_active: 10,
    products: [
      { offer_id: "1076425861755", title: "Observed paper title", source_url: "https://item.taobao.com/item.htm?id=1076425861755" },
      { offer_id: "998122080593", title: null, source_url: "https://item.taobao.com/item.htm?id=998122080593" },
      { offer_id: "123", title: "Unsafe item", source_url: "https://evil.example/item.htm?id=123" },
      { offer_id: "456", title: "Mismatched item", source_url: "https://item.taobao.com/item.htm?id=789" },
    ],
    completeness: 0.3333, completeness_denominator: Array(12).fill("field"), missing_fields: Array(8).fill("unknown"),
    extraction_method: "PUBLIC_HTTP", analysis_mode: "ACCOUNT_PUBLIC", extractor_version: "taobao-http.v1",
    extracted_at: "2026-09-30T00:00:00+00:00", price_information: null,
    transaction_signals: {
      shop_metrics_display_text: ["4.9", "88VIP好评率97%", "平均23小时发货"],
      shop_evaluations: [
        { type: "desc", title: "描述相符", score: "4.8", levelText: "高于36.33%" },
        { type: "serv", title: "服务态度", score: "4.9", levelText: "高于26.56%" },
        { type: "post", title: "物流服务", score: "4.9", levelText: "高于22.96%" },
      ],
    },
  }, reviews: [] } as unknown as Analysis;
  const html = renderToStaticMarkup(<ExtractionEvidence analysis={analysis} />);
  assert.match(html, /Sản phẩm hiển thị trong cửa hàng \(4\)/);
  assert.match(html, /href="https:\/\/item\.taobao\.com\/item\.htm\?id=1076425861755"[^>]*>Observed paper title/);
  assert.match(html, /Sản phẩm 998122080593/);
  assert.match(html, /Unsafe item/); assert.match(html, /Mismatched item/);
  assert.doesNotMatch(html, /href="https:\/\/evil\.example|href="https:\/\/item\.taobao\.com\/item\.htm\?id=789"/);
  for (const label of ["描述相符: 4.8 (高于36.33%)", "服务态度: 4.9 (高于26.56%)", "物流服务: 4.9 (高于22.96%)", "88VIP好评率97%", "平均23小时发货"]) assert.ok(html.includes(label), label);
  assert.match(html, /Tuổi cửa hàng hiển thị: 10 năm; chưa xác minh tuổi pháp nhân/);
});

const sourceUrl = "https://detail.1688.com/offer/996518024136.html";

test("live evidence displays status, coverage, and accessible review text", () => {
  const analysis = {
    result: { source_url: sourceUrl, extraction_status: "PARTIAL" },
    supplier_data: {
      platform: "1688", source_url: sourceUrl, supplier_name: "Supplier", products: [{ title: "Dress" }],
      completeness: 0.5, completeness_denominator: Array(12).fill("field"),
      missing_fields: Array(6).fill("missing"), extraction_method: "PUBLIC_HTTP",
      analysis_mode: "ACCOUNT_PUBLIC", extractor_version: "1688-http.v1",
      extracted_at: "2026-09-29T00:00:00+00:00", transaction_signals: { review_count: 267 },
    },
    reviews: [{ text: "Accessible review", source_url: sourceUrl }],
  } as unknown as Analysis;
  assert.equal(isFixtureResult(analysis.result), false);
  const html = renderToStaticMarkup(<ExtractionEvidence analysis={analysis} />);
  assert.match(html, /PARTIAL/);
  assert.match(html, /50%/);
  assert.match(html, /Accessible review/);
  assert.match(html, /267/);
  assert.doesNotMatch(html, /Điểm rủi ro:/);
});

test("fixture results keep the separate demo report path", () => {
  const fixture = { source_url: sourceUrl, supplier_name: "Demo", fixture: true } as const;
  assert.equal(isFixtureResult(fixture), true);
  assert.equal(renderToStaticMarkup(<ExtractionEvidence analysis={{ result: fixture } as Analysis} />), "");
});

test("uploaded evidence shows file provenance and unknown original capture time", () => {
  const analysis = {
    extraction_method: "USER_UPLOAD",
    result: { source_url: sourceUrl, extraction_status: "PARTIAL" },
    supplier_data: {
      platform: "1688", source_url: sourceUrl, supplier_name: "Supplier", products: null,
      completeness: 0.25, completeness_denominator: Array(12).fill("field"),
      missing_fields: Array(9).fill("missing"), extraction_method: "USER_UPLOAD",
      analysis_mode: "ACCOUNT_PUBLIC", extractor_version: "1688-user-upload.v1",
      extracted_at: "2026-09-30T00:00:00+00:00", transaction_signals: null,
    },
    raw_evidence: { captured_at: null, imported_at: "2026-09-30T00:00:00+00:00" },
    reviews: [],
  } as unknown as Analysis;
  const html = renderToStaticMarkup(<ExtractionEvidence analysis={analysis} />);
  assert.match(html, /USER_UPLOAD/);
  assert.match(html, /1688-user-upload\.v1/);
  assert.match(html, /Trang HTML do bạn tải lên/);
  assert.match(html, /Thời điểm lưu trang gốc: chưa xác định/);
  assert.match(html, /https:\/\/detail\.1688\.com\/offer\/996518024136\.html/);

  const failed = { extraction_method: "USER_UPLOAD", result: {
    source_url: sourceUrl, extraction_status: "PARSE_FAILED", reason: "PARSER_LIMIT",
  }, supplier_data: null } as unknown as Analysis;
  const failedHtml = renderToStaticMarkup(<ExtractionEvidence analysis={failed} />);
  assert.match(failedHtml, /Trang đã tải lên không cung cấp bằng chứng/);
  assert.doesNotMatch(failedHtml, /bằng chứng công khai/);
});

test("browser evidence identifies user-provided DOM fields without a risk score", () => {
  const analysis = {
    extraction_method: "EXTENSION_DOM",
    result: { source_url: sourceUrl, extraction_status: "PARTIAL" },
    supplier_data: {
      platform: "1688", source_url: sourceUrl, supplier_name: "Visible supplier",
      products: [{ offer_id: "996518024136", title: "Visible dress" }],
      completeness: 0.25, completeness_denominator: Array(12).fill("field"),
      missing_fields: Array(9).fill("missing"), extraction_method: "EXTENSION_DOM",
      analysis_mode: "EXTENSION_ENHANCED", extractor_version: "1688-extension-dom.v1",
      extracted_at: "2026-09-30T00:00:00+00:00", transaction_signals: null,
      price_information: { display_text: "39.00" },
    },
    reviews: [],
  } as unknown as Analysis;
  const html = renderToStaticMarkup(<ExtractionEvidence analysis={analysis} />);
  assert.match(html, /EXTENSION_DOM/);
  assert.match(html, /1688-extension-dom\.v1/);
  assert.match(html, /B\u1eb1ng ch\u1ee9ng tr\u00ecnh duy\u1ec7t do b\u1ea1n cung c\u1ea5p/);
  assert.match(html, /25%/);
  assert.match(html, /39\.00/);
  assert.match(html, /Ch\u01b0a c\u00f3 \u0111i\u1ec3m r\u1ee7i ro/);
});

for (const [status, reason, guidance] of [
  ["AUTH_REQUIRED", "LOGIN_REQUIRED", /đăng nhập.*tiện ích VCT Connect/],
  ["BLOCKED", "ACCESS_CHALLENGE", /xác minh.*tiện ích VCT Connect/],
  ["BLOCKED", "UNSAFE_DESTINATION", /URL HTTPS.*detail\.1688\.com/],
  ["TIMEOUT", "HTTP_TIMEOUT", /lần trích xuất này đã kết thúc/],
  ["UNSUPPORTED_PAGE", "HTTP_ERROR", /sản phẩm còn tồn tại/],
  ["PARSE_FAILED", "MALFORMED_PAGE", /Nội dung trang/],
] as const) {
  test(`failed ${status} evidence renders safe recovery with no supplier claims`, () => {
    const analysis = {
      result: { source_url: sourceUrl, extraction_status: status, reason },
      supplier_data: null, reviews: [], extraction_method: "PUBLIC_HTTP",
    } as unknown as Analysis;
    const html = renderToStaticMarkup(<ExtractionEvidence analysis={analysis} />);
    assert.ok(html.includes(status) && html.includes(reason));
    assert.match(html, guidance);
    assert.match(html, /Mở trang nguồn 1688/);
    assert.match(html, /Chưa có điểm rủi ro/);
    assert.doesNotMatch(html, /Độ phủ:|Supplier|Hệ thống sẽ tự động thử lại/);
  });
}

test("unsafe original source cannot become a source link", () => {
  const analysis = {
    result: { source_url: "https://127.0.0.1/private", extraction_status: "UNSUPPORTED_PAGE", reason: "INVALID_URL" },
    supplier_data: null, reviews: [], extraction_method: "PUBLIC_HTTP",
  } as unknown as Analysis;
  const html = renderToStaticMarkup(<ExtractionEvidence analysis={analysis} />);
  assert.match(html, /URL HTTPS/);
  assert.doesNotMatch(html, /href=|127\.0\.0\.1/);
});

test("sparse evidence keeps absent fields visibly unknown", () => {
  const analysis = {
    result: { source_url: sourceUrl, extraction_status: "PARTIAL" },
    supplier_data: {
      platform: "1688", source_url: sourceUrl, supplier_name: null, products: [{ title: "Dress" }],
      completeness: 1 / 12, completeness_denominator: Array(12).fill("field"),
      missing_fields: Array(11).fill("unknown"), extraction_method: "PUBLIC_HTTP",
      analysis_mode: "ACCOUNT_PUBLIC", extractor_version: "1688-http.v1",
      extracted_at: "2026-09-30T00:00:00+00:00", transaction_signals: null,
    }, reviews: [],
  } as unknown as Analysis;
  const html = renderToStaticMarkup(<ExtractionEvidence analysis={analysis} />);
  assert.match(html, /Chưa có tên nhà cung cấp/);
  assert.match(html, /8%.*1\/12/);
  assert.match(html, /chưa có/);
  assert.match(html, /Thiếu dữ liệu là chưa xác định/);
});
