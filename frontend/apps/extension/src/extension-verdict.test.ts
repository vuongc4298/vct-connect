import assert from "node:assert/strict";
import test from "node:test";
import type { Analysis, ReportV1 } from "@vct/contracts";
import { extensionVerdict } from "./extension-verdict";

const base = { id: "owned-analysis", status: "ASSESSING", result: null, failure_code: null } as Analysis;
test("extension polls nonterminal states and stops on final states", () => {
  for (const status of ["QUEUED","PROCESSING","ASSESSING","REPORTING","FAILED_RETRYABLE"] as const) {
    assert.equal(extensionVerdict({ ...base, status }, null).poll, true);
  }
  for (const status of ["FAILED_FINAL","COMPLETED"] as const) {
    assert.equal(extensionVerdict({ ...base, status }, null).poll, false);
  }
});
test("missing report never implies low risk", () => {
  const v = extensionVerdict({ ...base, status: "COMPLETED" }, null);
  assert.equal(v.riskLabel, null);
  assert.equal(v.confidence, null);
  assert.equal(v.coverage, null);
});
test("insufficient information stays distinct from low risk", () => {
  const report = { analysis_id: "owned-analysis", risk: { label: "INSUFFICIENT_INFORMATION", overall_risk: null, confidence: 0.32, coverage: 0.21 }} as ReportV1;
  const v = extensionVerdict({ ...base, status: "COMPLETED" }, report);
  assert.equal(v.riskLabel, "Insufficient information");
  assert.equal(v.confidence, 0.32);
  assert.equal(v.coverage, 0.21);
});
test("blocked extraction remains an unscored terminal state", () => {
  const v = extensionVerdict({ ...base, status: "COMPLETED", result: { source_url: "https://detail.1688.com/offer/996518024136.html", extraction_status: "BLOCKED", reason: "ACCESS_CHALLENGE" } }, null);
  assert.equal(v.poll, false);
  assert.equal(v.headline, "Source evidence unavailable");
  assert.equal(v.riskLabel, null);
});

test("foreign or stale reports never display a verdict", () => {
  const foreign = {
    analysis_id: "someone-else",
    risk: { label: "LOW", overall_risk: 2, confidence: 0.95, coverage: 0.9 },
  } as ReportV1;
  const wrongOwner = extensionVerdict({ ...base, status: "COMPLETED" }, foreign);
  assert.equal(wrongOwner.riskLabel, null);
  assert.equal(wrongOwner.confidence, null);
  const stale = extensionVerdict({ ...base, status: "ASSESSING" }, { ...foreign, analysis_id: base.id });
  assert.equal(stale.riskLabel, null);
  assert.equal(stale.coverage, null);
});
