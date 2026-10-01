import assert from "node:assert/strict";
import test from "node:test";
import type { ExtractionStatus } from "@vct/contracts";

import { analysisPresentation, extractionRecovery } from "./analysis-status";

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
    assert.match(view.detail, guidance);
    assert.ok(view.detail.includes(reason));
    assert.doesNotMatch(view.detail, /Hệ thống sẽ tự động thử lại/);
    assert.equal(extractionRecovery(status, reason), view.detail.split("URL này. ")[1]);
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
    assert.match(view.detail, /chưa có điểm rủi ro/);
    assert.equal(extractionRecovery(status), null);
  });
}
