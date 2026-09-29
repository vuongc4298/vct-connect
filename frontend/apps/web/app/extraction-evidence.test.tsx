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
