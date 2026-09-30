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
