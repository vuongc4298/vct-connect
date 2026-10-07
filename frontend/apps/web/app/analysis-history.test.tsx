import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import type { AnalysisHistoryItem } from "@vct/contracts";
import { AnalysisHistory } from "./analysis-history";

const completed: AnalysisHistoryItem = {
  id: "00000000-0000-0000-0000-000000000001",
  source_url: "https://detail.1688.com/offer/123456789012.html",
  status: "COMPLETED",
  created_at: "2026-10-08T00:00:00Z",
  completed_at: "2026-10-08T00:01:00Z",
  mode: "ACCOUNT_PUBLIC",
  extraction_method: "PUBLIC_HTTP",
  scoring_version: "v0.1.0",
  supplier_name: "Fixture Supplier",
  platform: "1688",
  report_available: true,
  risk_label: "INSUFFICIENT_INFORMATION",
  overall_risk: null,
  confidence: 0.4,
  coverage: 0.35,
};

test("history shows persisted report summary without turning insufficiency into low risk", () => {
  const html = renderToStaticMarkup(<AnalysisHistory
    items={[completed]} loading={false} error="" onOpen={() => undefined} onNewAnalysis={() => undefined}
  />);
  assert.match(html, /Fixture Supplier/);
  assert.match(html, /Chưa đủ thông tin/);
  assert.match(html, /40% tin cậy/);
  assert.match(html, /35% độ phủ/);
  assert.match(html, /Mở báo cáo/);
  assert.doesNotMatch(html, /Rủi ro thấp/);
});

test("pending history uses status and progress action without fabricated risk", () => {
  const pending = { ...completed, id: "pending", status: "ASSESSING" as const, report_available: false,
    risk_label: null, overall_risk: null, confidence: null, coverage: null };
  const html = renderToStaticMarkup(<AnalysisHistory
    items={[pending]} loading={false} error="" onOpen={() => undefined} onNewAnalysis={() => undefined}
  />);
  assert.match(html, /Đang đánh giá/);
  assert.match(html, /Chưa có đánh giá rủi ro/);
  assert.match(html, /Xem tiến độ/);
});
