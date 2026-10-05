import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import type { Analysis, TextReportState } from "@vct/contracts";
import { TextReport } from "./text-report";
import { analysisPresentation } from "./analysis-status";

function analysis(state: TextReportState["state"]): Analysis {
  return { id: "owned", status: "COMPLETED", actor_type: "CUSTOMER", result: { extraction_status: "PARTIAL" },
    extraction_method: "USER_UPLOAD", text_report: { state, failure_code: null, generated_at: null, report: null } } as Analysis;
}

test("polling continues for interpretation after completed extraction", () => {
  for (const state of ["QUEUED", "PROCESSING"] as const) {
    const value = analysis(state);
    assert.equal(analysisPresentation(value).shouldPoll, true);
    assert.equal(analysisPresentation(value).complete, true);
    assert.equal(value.status, "COMPLETED");
    assert.match(renderToStaticMarkup(<TextReport analysis={value} />), /Bằng chứng trích xuất vẫn có thể xem/);
  }
});

test("terminal report states stop polling and keep evidence fallback", () => {
  for (const state of ["UNAVAILABLE", "INSUFFICIENT", "FAILED", "UNCERTAIN"] as const) {
    const value = analysis(state);
    assert.equal(analysisPresentation(value).shouldPoll, false);
    assert.match(renderToStaticMarkup(<TextReport analysis={value} />), /Bằng chứng trích xuất vẫn có thể xem/);
  }
});

test("validated report renders citations, inference, actions, limitations, dates and unknown cost", () => {
  const value = analysis("READY");
  value.text_report = { state: "READY", failure_code: null, generated_at: "2026-10-05T01:00:00Z", report: {
    summary: "Cần kiểm tra mẫu.", findings: [{ kind: "inference", text: "Cần xác minh.", citations: ["E1"] }],
    limitations: ["Thiếu dữ liệu."], actions: ["Yêu cầu mẫu."], evidence: [{ id: "E1", path: "products", value: "中国商品" }],
    extracted_at: "2026-10-04T00:00:00Z", source_url: "https://detail.1688.com/offer/996518024136.html",
    snapshot_id: "snapshot", capture_freshness: "unknown", metadata: { model: "pinned", model_version: "v1",
      prompt_version: "vi.v1", schema_version: "text.v1", pipeline_version: "saved.v1", actual_cost_usd: null, cost_provenance: "unknown" },
  } };
  const html = renderToStaticMarkup(<TextReport analysis={value} />);
  for (const text of ["Suy luận cần xác minh", "Thiếu dữ liệu", "Yêu cầu mẫu", "中国商品", "2026-10-05", "2026-10-04", "Chi phí thực tế: chưa xác định"])
    assert.ok(html.includes(text));
  assert.match(html, /href="#report-owned-E1"/);
  assert.match(html, /id="report-owned-E1"/);
  assert.equal(analysisPresentation(value).shouldPoll, false);
  assert.doesNotMatch(html, /64|72%|risk-ring/);
});

test("fixture and guest cannot display full reports", () => {
  const value = analysis("READY");
  assert.equal(renderToStaticMarkup(<TextReport analysis={{ ...value, actor_type: "GUEST" }} />), "");
  assert.equal(renderToStaticMarkup(<TextReport analysis={{ ...value, result: { fixture: true, source_url: "fixture", supplier_name: "demo" } }} />), "");
});
