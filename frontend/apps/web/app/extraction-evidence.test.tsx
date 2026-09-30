import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import type { Analysis } from "@vct/contracts";

import { ExtractionEvidence, isFixtureResult } from "./extraction-evidence";

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
