import assert from "node:assert/strict";
import test from "node:test";

import {
  REPORT_DIMENSION_LABELS,
  optionalReportPercent,
  reportBarWidth,
  reportEvidenceAnchor,
  reportFindingTitle,
  reportPercent,
  reportRiskLabel,
} from "./report-presentation";

test("report presentation helpers preserve frozen labels and formatting", () => {
  assert.equal(REPORT_DIMENSION_LABELS.PRICING, "Giá và điều khoản");
  assert.equal(REPORT_DIMENSION_LABELS.COMMUNICATION, "Giao tiếp");
  assert.equal(reportPercent(0.724), "72%");
  assert.equal(optionalReportPercent(undefined), "Chưa xác định");
  assert.equal(reportBarWidth(1.5), "100%");
  assert.equal(reportBarWidth(-0.2), "0%");
  assert.equal(reportEvidenceAnchor("review:0/media"), "evidence-review-0-media");
});

test("report risk labels and finding titles keep existing buyer semantics", () => {
  assert.deepEqual(reportRiskLabel("INSUFFICIENT_INFORMATION"), {
    text: "CHƯA ĐỦ THÔNG TIN",
    tone: "neutral",
  });
  assert.equal(reportFindingTitle({
    finding_key: "f-1",
    finding_type: "SUPPLIER_RISK",
    dimension: "DELIVERY",
    severity: 70,
    confidence: 0.8,
    evidence_ids: [],
    payload: {},
  }), "Giao hàng");
  assert.equal(reportFindingTitle({
    finding_key: "f-2",
    finding_type: "REVIEW_FINDING",
    dimension: "PRODUCT_QUALITY",
    severity: 60,
    confidence: 0.7,
    evidence_ids: [],
    payload: { statement_vi: "Có phản ánh lỗi sản phẩm." },
  }), "Có phản ánh lỗi sản phẩm.");
});
