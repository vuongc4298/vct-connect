import assert from "node:assert/strict";
import test from "node:test";

import { analysisPresentation } from "./analysis-status";


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
