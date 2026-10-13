import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import type { ReportV1 } from "@vct/contracts";
import { FullReport } from "./full-report";
import { capturedReviewSummary, dimensionEvidence } from "./dimension-evidence";

test("captured review sample and lower-bound platform total remain distinct from authenticity", () => {
  const evidence: ReportV1["evidence"] = [
    { evidence_id: "supplier:reviews", source_kind: "SUPPLIER_DATA", source_field: "reviews", payload: { value: Array.from({length: 10}, () => ({text: "good"})) } },
    { evidence_id: "supplier:transaction_signals", source_kind: "SUPPLIER_DATA", source_field: "transaction_signals", payload: { value: { review_count_display_text: "4.8 6000+条评价" } } },
    { evidence_id: "supplier:price_information", source_kind: "SUPPLIER_DATA", source_field: "price_information", payload: { value: {display_text: "¥3.60 ¥23.80 1件起批"} } },
  ];
  assert.deepEqual(capturedReviewSummary(evidence), {count: 10, totalDisplay: "4.8 6000+条评价"});
  assert.match(dimensionEvidence("REVIEW_MANIPULATION", evidence).explanation, /10 đánh giá.*6000\+.*không tự xác minh/);
  const report = reportFixture("INSUFFICIENT_INFORMATION");
  report.risk.dimensions = [{ ...report.risk.dimensions[2], risk: null }];
  report.evidence.push(...evidence);
  const html = renderToStaticMarkup(<FullReport report={report} />);
  assert.match(html, /Đã có dữ liệu · chưa thể kết luận/);
  assert.match(html, /Đã thu thập giá và điều kiện/);
  assert.match(html, /href="#evidence-supplier-price_information"/);
});

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
        payload: { field: "years_active", value: 5 },
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
  assert.doesNotMatch(html, /<strong>Giao hàng<\/strong>/);
  assert.match(html, /Giá và điều khoản/);
  assert.doesNotMatch(html, /<strong>Giao tiếp<\/strong>/);
  assert.doesNotMatch(html, />PRICING</);
  assert.doesNotMatch(html, />COMMUNICATION</);
  assert.match(html, /mô hình cũ/);
  assert.match(html, /href="#evidence-review-0"/);
  assert.match(html, /id="evidence-review-0"/);
  assert.match(html, /review:0/);
  assert.match(html, /Poor stitching quality/);
  assert.match(html, /Nội dung nguồn:/);
  assert.match(html, /<pre[^>]*>5<\/pre>/);
  assert.match(html, /Độ mới:/);
  assert.match(html, /Mở trang nguồn 1688/);
});

test("supplier dimension scores show their assessment reason and captured source quotes", () => {
  const report = reportFixture("INSUFFICIENT_INFORMATION");
  report.risk.dimensions[1] = {
    ...report.risk.dimensions[1], dimension: "PRICING", risk: 55, effective_confidence: 0.6,
    evidence_ids: ["supplier-dimension:delivery"],
  };
  report.evidence.push({evidence_id: "supplier-dimension:delivery",
    source_kind: "MODEL_INTERPRETATION", source_field: null,
    payload: {statement_vi: "Tỷ lệ thực hiện đơn cần xác minh.",
      evidence_quotes: {transaction_signals: "45%"}}});
  const html = renderToStaticMarkup(<FullReport report={report} />);
  assert.match(html, /55\/100/);
  const chart = html.slice(html.indexOf('class="report-dimension-list"'), html.indexOf('class="report-grid"'));
  assert.match(chart, /Tỷ lệ thực hiện đơn cần xác minh/);
  assert.match(chart, /href="#evidence-supplier-dimension-delivery"/);
  assert.match(html, /Trích dẫn nguồn:/);
  assert.match(html, /45%/);
  assert.match(html, /CHƯA ĐỦ THÔNG TIN/);
});

test("absent supplier source values stay explicitly unknown", () => {
  const report = reportFixture();
  report.evidence[1].payload.value = null;
  const html = renderToStaticMarkup(<FullReport report={report} />);
  assert.match(html, /<pre[^>]*>Chưa xác định<\/pre>/);
});

test("review source cards preserve safe review URLs and reject unsafe URLs", () => {
  const report = reportFixture();
  const reviewUrl = "https://item.taobao.com/item.htm?id=1076425861755";
  report.evidence[0].payload.source_url = reviewUrl;
  let html = renderToStaticMarkup(<FullReport report={report} />);
  assert.match(html, /Mở nguồn đánh giá/);
  assert.ok(html.includes(`href="${reviewUrl.replaceAll("&", "&amp;")}"`));
  report.evidence[0].payload.source_url = "https://127.0.0.1/private";
  html = renderToStaticMarkup(<FullReport report={report} />);
  assert.doesNotMatch(html, /Mở nguồn đánh giá|href="https:\/\/127\.0\.0\.1/);
});

test("saved HTML processing time is displayed separately from unknown original capture age", () => {
  const report = reportFixture();
  report.extracted_at = new Date().toISOString();
  const html = renderToStaticMarkup(<FullReport report={report} extractionMethod="USER_UPLOAD" />);
  assert.match(html, /Tuổi ảnh chụp trang đã lưu chưa xác định/);
  assert.match(html, /Thời điểm xử lý HTML/);
  assert.match(html, /Tuổi ảnh chụp trang: Chưa xác định/);
  assert.doesNotMatch(html, /<small>Thu thập|Độ mới:/);
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

test("preliminary sample policy discloses confidence caps without modifying archived reports", () => {
  const report = reportFixture();
  report.risk.scoring_version = "v0.2.1";
  const html = renderToStaticMarkup(<FullReport report={report} />);
  assert.match(html, /Mẫu 10 đánh giá đủ cho kiểm tra ban đầu/);
  assert.match(html, /tối đa 60%/);
  assert.match(html, /riêng lẻ tối đa 40%/);
  assert.match(html, /mẫu được chọn có thể thiên lệch/);
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


test("internal scorer references are labeled without pretending to be source anchors", () => {
  const report = reportFixture();
  report.risk.dimensions[0].evidence_ids = ["review-finding:quality"];
  const html = renderToStaticMarkup(<FullReport report={report} />);
  assert.match(html, /review-finding:quality · tham chiếu chấm điểm/);
  assert.doesNotMatch(html, /href="#evidence-review-finding-quality"/);
});

test("insufficient reports suppress a contradictory numeric risk in the overview chart", () => {
  const report = reportFixture("INSUFFICIENT_INFORMATION");
  report.risk.overall_risk = 12;
  report.risk.dimensions[2].risk = null;
  const html = renderToStaticMarkup(<FullReport report={report} />);
  assert.match(html, /Rủi ro tổng thể: chưa đủ dữ liệu/);
  assert.doesNotMatch(html, /12\/100/);
  assert.match(html, /risk-chart-track unknown/);
});

test("each text section presents at most five items with remaining items accessible by paging", () => {
  const report = reportFixture();
  report.recommended_actions_vi = Array.from({ length: 8 }, (_, i) => `Action ${i + 1}`);
  report.limitations_vi = Array.from({ length: 8 }, (_, i) => `Limit ${i + 1}`);
  report.missing_data.uncertainties_vi = Array.from({ length: 8 }, (_, i) => `Uncertain ${i + 1}`);
  const html = renderToStaticMarkup(<FullReport report={report} />);
  for (const prefix of ["Action", "Limit", "Uncertain"]) {
    assert.match(html, new RegExp(`${prefix} 5`));
    assert.doesNotMatch(html, new RegExp(`${prefix} 6`));
  }
  assert.match(html, /Hành động đề xuất: tiếp/);
  assert.match(html, /Giới hạn: tiếp/);
  assert.match(html, /<details><summary class="report-source-head"/);
});


test("captured page context renders readable source excerpts with safe links and five-item paging", () => {
  const report = reportFixture();
  report.evidence.push({evidence_id: "supplier:page_context", source_kind: "SUPPLIER_DATA",
    source_field: "page_context", payload: {value: {truncated: true, sections: Array.from({length: 8}, (_, i) => ({
      section_id: "shop:" + i, heading: "Returns policy",
      text: "Context paragraph " + i,
      source_url: i === 0 ? "javascript:alert(1)" : "https://hztxsy.1688.com/",
    }))}}});
  const html = renderToStaticMarkup(<FullReport report={report} />);
  assert.match(html, /Ngữ cảnh trang đã thu thập/);
  assert.match(html, /Ngữ cảnh được giới hạn dung lượng/);
  assert.match(html, /Context paragraph 4/);
  assert.doesNotMatch(html, /Context paragraph 5/);
  assert.match(html, /href="https:\/\/hztxsy\.1688\.com\//);
  assert.doesNotMatch(html, /href="javascript:/);
});
