import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import type { ReportV1 } from "@vct/contracts";
import { FullReport } from "./full-report";

function reportFixture(label: ReportV1["risk"]["label"] = "MODERATE"): ReportV1 {
  const insufficient = label === "INSUFFICIENT_INFORMATION";
  return {
    schema_version: "report.v1",
    language: "vi",
    analysis_id: "00000000-0000-0000-0000-000000000123",
    source_url: "https://detail.1688.com/offer/996518024136.html",
    platform: "1688",
    extracted_at: "2026-10-07T12:30:00+00:00",
    supplier_name: "Fixture Supplier",
    platform_supplier_id: "supplier-1",
    supplier_summary_vi: "Nhà cung cấp có bằng chứng hoạt động nhưng vẫn cần xác minh trước khi đặt cọc.",
    risk: {
      overall_risk: insufficient ? null : 58,
      label,
      confidence: insufficient ? 0.35 : 0.72,
      coverage: insufficient ? 0.4 : 0.75,
      scoring_version: "v0.1.0",
      dimensions: [
        {
          dimension: "PRODUCT_QUALITY",
          configured_weight: 0.25,
          risk: 70,
          base_confidence: 0.8,
          effective_confidence: 0.7,
          review_derived_share: 1,
          review_manipulation_adjustment: 0,
          evidence_ids: ["review:0"],
        },
        {
          dimension: "DELIVERY",
          configured_weight: 0.15,
          risk: null,
          base_confidence: 0,
          effective_confidence: 0,
          review_derived_share: 0,
          review_manipulation_adjustment: 0,
          evidence_ids: [],
        },
        {
          dimension: "PRICING",
          configured_weight: 0.10,
          risk: 42,
          base_confidence: 0.6,
          effective_confidence: 0.6,
          review_derived_share: 0,
          review_manipulation_adjustment: 0,
          evidence_ids: [],
        },
        {
          dimension: "COMMUNICATION",
          configured_weight: 0.05,
          risk: 35,
          base_confidence: 0.55,
          effective_confidence: 0.55,
          review_derived_share: 0,
          review_manipulation_adjustment: 0,
          evidence_ids: [],
        },
      ],
    },
    factory_trader: {
      classification: "UNCERTAIN",
      factory_likelihood: 0.6,
      trader_likelihood: 0.2,
      confidence: 0.55,
      uncertainty_reasons: ["self_claim_only"],
    },
    review_summary: {
      mode: "semantic",
      confidence: 0.8,
      review_reliability: 0.7,
      findings: [{ category: "QUALITY" }],
      suspicious_patterns: [],
    },
    key_risks: [
      {
        finding_key: "review:0:QUALITY:review:0",
        finding_type: "REVIEW_FINDING",
        dimension: "PRODUCT_QUALITY",
        severity: 80,
        confidence: 0.9,
        evidence_ids: ["review:0"],
        payload: {
          statement_vi: "Đánh giá mô tả lỗi chất lượng cần được kiểm tra.",
          category: "QUALITY",
        },
      },
    ],
    positive_signals: [
      {
        finding_key: "supplier_positive:0",
        finding_type: "SUPPLIER_POSITIVE",
        dimension: null,
        severity: null,
        confidence: 0.8,
        evidence_ids: ["supplier:years_active"],
        payload: {
          statement_vi: "Có thông tin hoạt động nhiều năm.",
          evidence_fields: ["years_active"],
        },
      },
    ],
    other_findings: [],
    evidence: [
      {
        evidence_id: "review:0",
        source_kind: "REVIEW",
        source_field: "reviews",
        payload: {
          text: "Poor stitching quality",
          source_url: "https://detail.1688.com/offer/996518024136.html",
        },
      },
      {
        evidence_id: "supplier:years_active",
        source_kind: "SUPPLIER_DATA",
        source_field: "years_active",
        payload: { field: "years_active" },
      },
    ],
    missing_data: {
      source_fields: ["certifications"],
      risk_dimensions: ["DELIVERY"],
      uncertainties_vi: ["Chưa có chứng nhận được xác minh."],
    },
    limitations_vi: [
      insufficient
        ? "Thông tin hiện có chưa đủ để đưa ra mức rủi ro đáng tin cậy; không được diễn giải trạng thái này thành rủi ro thấp."
        : "Báo cáo phản ánh bằng chứng đã thu thập tại thời điểm phân tích.",
    ],
    recommended_actions_vi: [
      "Xác minh giấy phép kinh doanh trước khi đặt cọc.",
      "Yêu cầu mẫu hoặc lô thử trước khi đặt đơn lớn.",
    ],
  };
}

test("full report renders real score, identity, review, actions and evidence traceability", () => {
  const html = renderToStaticMarkup(<FullReport report={reportFixture()} />);

  assert.match(html, /Fixture Supplier/);
  assert.match(html, /58/);
  assert.match(html, /72%/);
  assert.match(html, /75%/);
  assert.match(html, /v0\.1\.0/);
  assert.match(html, /Khả năng nhà máy/);
  assert.match(html, /60%/);
  assert.match(html, /Độ tin cậy đánh giá/);
  assert.match(html, /Đánh giá mô tả lỗi chất lượng/);
  assert.match(html, /Có thông tin hoạt động nhiều năm/);
  assert.match(html, /Xác minh giấy phép kinh doanh trước khi đặt cọc/);
  assert.match(html, /Chưa có chứng nhận được xác minh/);
  assert.match(html, /Chất lượng sản phẩm/);
  assert.match(html, /Giao hàng/);
  assert.match(html, /Giá và điều khoản/);
  assert.match(html, /Giao tiếp/);
  assert.doesNotMatch(html, />PRICING</);
  assert.doesNotMatch(html, />COMMUNICATION</);
  assert.match(html, /Chưa đủ bằng chứng/);
  assert.match(html, /href="#evidence-review-0"/);
  assert.match(html, /id="evidence-review-0"/);
  assert.match(html, /Độ mới: bằng chứng thuộc ảnh chụp ngày/);
  assert.match(html, /Mở trang nguồn 1688/);
});

test("insufficient information is visibly distinct from low risk", () => {
  const html = renderToStaticMarkup(
    <FullReport report={reportFixture("INSUFFICIENT_INFORMATION")} />,
  );

  assert.match(html, /CHƯA ĐỦ THÔNG TIN/);
  assert.match(html, /chưa đủ dữ liệu/);
  assert.match(html, /Không có điểm rủi ro thấp mặc định/);
  assert.match(html, /35%/);
  assert.match(html, /40%/);
  assert.match(html, /không được diễn giải trạng thái này thành rủi ro thấp/);
  assert.doesNotMatch(html, /RỦI RO THẤP/);
});

test("unsafe report source URL is never rendered as an outbound link", () => {
  const report = reportFixture();
  report.source_url = "https://127.0.0.1/private";
  const html = renderToStaticMarkup(<FullReport report={report} />);

  assert.doesNotMatch(html, /href="https:\/\/127\.0\.0\.1/);
  assert.doesNotMatch(html, /Mở trang nguồn 1688/);
});


test("stale report snapshots are visibly labeled before buyer decisions", () => {
  const report = reportFixture();
  report.extracted_at = "2020-01-01T00:00:00Z";
  const html = renderToStaticMarkup(<FullReport report={report} />);
  assert.match(html, /Dữ liệu nguồn đã cũ/);
  assert.match(html, /DỮ LIỆU CŨ/);
  assert.match(html, /xác minh lại các thông tin có thể thay đổi/);
});

test("dangling historical evidence ids render as missing source, not fake anchors", () => {
  const report = reportFixture();
  report.key_risks[0].evidence_ids = ["missing:evidence"];
  const html = renderToStaticMarkup(<FullReport report={report} />);
  assert.match(html, /missing:evidence · thiếu nguồn/);
  assert.doesNotMatch(html, /href="#evidence-missing-evidence"/);
});
