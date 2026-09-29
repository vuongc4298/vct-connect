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
