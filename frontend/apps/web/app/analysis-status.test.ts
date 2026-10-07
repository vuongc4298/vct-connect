import assert from "node:assert/strict";
import test from "node:test";
import type { ExtractionStatus } from "@vct/contracts";

import { analysisPresentation, extractionRecovery } from "./analysis-status";

test("server public browser evidence preserves partial and terminal presentation", () => {
  const source_url = "https://detail.1688.com/offer/987654321012.html";
  for (const extraction_status of ["PARTIAL", "BLOCKED", "AUTH_REQUIRED"] as const) {
    const view = analysisPresentation({status: "COMPLETED", attempt_count: 1, failure_code: null,
      extraction_method: "PUBLIC_BROWSER", result: {source_url, extraction_status}});
    assert.equal(view.shouldPoll, false);
    assert.equal(view.complete, extraction_status === "PARTIAL");
    assert.equal(view.final, extraction_status !== "PARTIAL");
  }
});

test("Alibaba terminal outcomes name the source and disclose unsupported recovery", () => {
  const source_url = "https://dgxuandele.en.alibaba.com/company_profile.html";
  for (const extraction_status of ["AUTH_REQUIRED", "BLOCKED", "TIMEOUT", "UNSUPPORTED_PAGE", "PARSE_FAILED"] as const) {
    const view = analysisPresentation({ status: "COMPLETED", attempt_count: 1, failure_code: null,
      source_url, extraction_method: "PUBLIC_HTTP", result: { source_url, extraction_status } });
    assert.equal(view.shouldPoll, false); assert.equal(view.final, true);
    assert.match(view.headline, /Alibaba/); assert.match(view.detail, /hiện chưa được hỗ trợ/);
    assert.doesNotMatch(view.detail, /1688|Taobao|dùng tiện ích VCT Connect/);
  }
  assert.equal(extractionRecovery("PARTIAL", undefined, source_url), null);
});

test("Taobao terminal guidance names the source and offers capture and saved HTML recovery", () => {
  const url = "https://item.taobao.com/item.htm?id=1076425861755";
  const view = analysisPresentation({ status: "COMPLETED", attempt_count: 1, failure_code: null,
    source_url: url, extraction_method: "PUBLIC_HTTP",
    result: { source_url: url, extraction_status: "BLOCKED", reason: "ACCESS_CHALLENGE" } });
  assert.equal(view.shouldPoll, false);
  assert.match(view.headline, /Taobao/);
  assert.match(view.detail, /tiện ích VCT Connect.*HTML/);
  for (const status of ["TIMEOUT", "PARSE_FAILED", "AUTH_REQUIRED", "UNSUPPORTED_PAGE"] as const) {
    assert.match(extractionRecovery(status, "HTTP_ERROR", url)!, /tiện ích VCT Connect.*HTML/);
  }
});

for (const reason of ["UNSAFE_DESTINATION", "UNSAFE_REDIRECT", "SOURCE_MISMATCH", "REDIRECT_LOOP", "REDIRECT_LIMIT"]) {
  test(`Taobao ${reason} selects safety guidance before access guidance`, () => {
    const recovery = extractionRecovery("BLOCKED", reason, "https://shop159450000.taobao.com/")!;
    assert.match(recovery, /không thể xác minh an toàn/);
    assert.match(recovery, /đúng mã sản phẩm \/ cửa hàng/);
    assert.doesNotMatch(recovery, /Taobao yêu cầu đăng nhập hoặc xác minh truy cập/);
  });
}


test("retryable state keeps polling and presents the durable attempt", () => {
  const view = analysisPresentation({
    status: "FAILED_RETRYABLE",
    attempt_count: 2,
    failure_code: "PROCESSING_ERROR",
  });
  assert.equal(view.shouldPoll, true);
  assert.equal(view.terminal, false);
  assert.equal(view.pillLabel, "SẼ THỬ LẠI");
  assert.match(view.detail, /Lần thử 2/);
});

test("final state stops polling and uses a nonworking terminal orb", () => {
  const view = analysisPresentation({
    status: "FAILED_FINAL",
    attempt_count: 5,
    failure_code: "PROCESSING_ERROR",
  });
  assert.equal(view.shouldPoll, false);
  assert.equal(view.terminal, true);
  assert.equal(view.orbClass, "failed");
  assert.notEqual(view.orbClass, "working");
  assert.equal(view.orbSymbol, "!");
});

test("blocked extraction stops polling without claiming a report is ready", () => {
  const view = analysisPresentation({
    status: "COMPLETED", attempt_count: 1, failure_code: null,
    extraction_method: "PUBLIC_HTTP",
    result: { source_url: "https://detail.1688.com/offer/996518024136.html", extraction_status: "BLOCKED" },
  });
  assert.equal(view.shouldPoll, false);
  assert.equal(view.complete, false);
  assert.equal(view.orbClass, "failed");
  assert.match(view.headline, /Chưa thể trích xuất/);
});

test("partial extraction is presented as evidence without a risk report", () => {
  const view = analysisPresentation({
    status: "COMPLETED", attempt_count: 1, failure_code: null,
    extraction_method: "PUBLIC_HTTP",
    result: { source_url: "https://detail.1688.com/offer/996518024136.html", extraction_status: "PARTIAL" },
  });
  assert.equal(view.complete, true);
  assert.equal(view.pillLabel, "TRÍCH XUẤT MỘT PHẦN");
  assert.match(view.headline, /Bằng chứng/);
});

for (const [status, reason, guidance] of [
  ["AUTH_REQUIRED", "LOGIN_REQUIRED", /đăng nhập.*tiện ích VCT Connect/],
  ["BLOCKED", "ACCESS_CHALLENGE", /xác minh.*tiện ích VCT Connect/],
  ["BLOCKED", "UNSAFE_DESTINATION", /URL HTTPS.*detail\.1688\.com/],
  ["BLOCKED", "UNSAFE_REDIRECT", /chuyển hướng.*an toàn/],
  ["PARSE_FAILED", "OFFER_MISMATCH", /sản phẩm này/],
  ["UNSUPPORTED_PAGE", "HTTP_ERROR", /sản phẩm còn tồn tại/],
  ["TIMEOUT", "HTTP_TIMEOUT", /lần trích xuất này đã kết thúc/],
  ["PARSE_FAILED", "UPSTREAM_UNAVAILABLE", /lần trích xuất này đã kết thúc/],
  ["PARSE_FAILED", "DNS_ERROR", /lần trích xuất này đã kết thúc/],
  ["PARSE_FAILED", "MALFORMED_PAGE", /Nội dung trang.*tiện ích VCT Connect/],
] as const) {
  test(`terminal ${status}/${reason} stops polling and gives recovery guidance`, () => {
    const view = analysisPresentation({
      status: "COMPLETED", attempt_count: 1, failure_code: null,
      extraction_method: "PUBLIC_HTTP", result: {
        source_url: "https://detail.1688.com/offer/996518024136.html", extraction_status: status, reason,
      },
    });
    assert.equal(view.terminal, true);
    assert.equal(view.shouldPoll, false);
    assert.equal(view.complete, false);
    assert.equal(view.retrying, false);
    assert.match(view.nextAction ?? "", guidance);
    assert.ok(view.detail.includes(reason));
    assert.doesNotMatch(view.nextAction ?? "", /Hệ thống sẽ tự động thử lại/);
    assert.equal(extractionRecovery(status, reason), view.nextAction);
  });
}

for (const status of ["SUCCESS", "PARTIAL"] satisfies ExtractionStatus[]) {
  test(`shared ${status} evidence outcome is accepted as terminal without a risk report`, () => {
    const view = analysisPresentation({
      status: "COMPLETED", attempt_count: 1, failure_code: null,
      result: { source_url: "https://detail.1688.com/offer/996518024136.html", extraction_status: status },
    });
    assert.equal(view.complete, true);
    assert.equal(view.shouldPoll, false);
    assert.match(view.detail, /Báo cáo đánh giá đã lưu/);
    assert.doesNotMatch(view.detail, /chưa có điểm rủi ro/);
    assert.equal(extractionRecovery(status), null);
  });
}


test("assessment and reporting states expose the real durable pipeline phases", () => {
  const assessing = analysisPresentation({
    status: "ASSESSING", attempt_count: 1, failure_code: null,
    extraction_method: "PUBLIC_HTTP",
  });
  assert.equal(assessing.shouldPoll, true);
  assert.equal(assessing.progressStep, 2);
  assert.equal(assessing.pillLabel, "ĐANG ĐÁNH GIÁ");
  assert.match(assessing.headline, /đánh giá bằng chứng/i);
  assert.match(assessing.detail, /độ tin cậy.*độ phủ/i);

  const reporting = analysisPresentation({
    status: "REPORTING", attempt_count: 1, failure_code: null,
    extraction_method: "PUBLIC_HTTP",
  });
  assert.equal(reporting.shouldPoll, true);
  assert.equal(reporting.progressStep, 3);
  assert.equal(reporting.pillLabel, "ĐANG LẬP BÁO CÁO");
  assert.match(reporting.detail, /lưu báo cáo.*đánh dấu hoàn tất/i);
});

test("queued, retryable, and final states give an explicit next action without pretending completion", () => {
  const queued = analysisPresentation({ status: "QUEUED", attempt_count: 0, failure_code: null });
  assert.equal(queued.progressStep, 0);
  assert.equal(queued.pillLabel, "ĐANG CHỜ");
  assert.match(queued.detail, /Không cần gửi lại/);

  const retrying = analysisPresentation({ status: "FAILED_RETRYABLE", attempt_count: 2, failure_code: "UPSTREAM" });
  assert.match(retrying.nextAction ?? "", /Không cần gửi lại/);
  assert.equal(retrying.complete, false);

  const failed = analysisPresentation({ status: "FAILED_FINAL", attempt_count: 5, failure_code: "PROCESSING_ERROR" });
  assert.match(failed.nextAction ?? "", /Tạo một phân tích mới/);
  assert.equal(failed.complete, false);
});
