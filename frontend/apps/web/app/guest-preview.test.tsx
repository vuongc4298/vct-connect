import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import type { GuestPreviewV1 } from "@vct/contracts";
import { GuestPreview } from "./guest-preview";

const base: GuestPreviewV1 = {
  schema_version: "guest-preview.v1",
  language: "vi",
  analysis_id: "analysis-1",
  platform: "1688",
  supplier_name: "Guest Supplier",
  extracted_at: "2026-10-07T00:00:00Z",
  confidence: 0.62,
  coverage: 0.48,
  information_state: "LIMITED_PREVIEW",
  missing_source_fields: ["certifications"],
  missing_risk_dimensions: ["AFTER_SALES"],
  uncertainties_vi: [],
  limitations_vi: ["Dữ liệu công khai có giới hạn."],
  registration_required: true,
};

test("guest preview shows confidence and coverage without a risk score", () => {
  const html = renderToStaticMarkup(<GuestPreview preview={base} />);
  assert.match(html, /62%/);
  assert.match(html, /48%/);
  assert.match(html, /BẢN XEM TRƯỚC GIỚI HẠN/);
  assert.doesNotMatch(html, /\/100/);
  assert.doesNotMatch(html, /RỦI RO THẤP/);
});

test("guest insufficient state explicitly refuses a low-risk interpretation", () => {
  const html = renderToStaticMarkup(<GuestPreview preview={{
    ...base,
    information_state: "INSUFFICIENT_INFORMATION",
    confidence: 0.35,
    coverage: 0.4,
  }} />);
  assert.match(html, /CHƯA ĐỦ THÔNG TIN/);
  assert.match(html, /Không có kết luận rủi ro thấp/);
});
