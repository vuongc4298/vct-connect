import assert from "node:assert/strict";
import test from "node:test";
import { loadScopedResult, restoreLastCapture, saveOpenAndLoadResult, type LastCapture } from "./capture-result";
import type { Analysis, ReportV1 } from "@vct/contracts";

const record: LastCapture = { analysisId: "6c93a530-9914-4ead-89ee-c8083f5effb8",
  sourceUrl: "https://item.taobao.com/item.htm?id=1076425861755", ownerId: "owner-one" };

test("restored result loads its report and clears previous report while assessment is pending", async () => {
  const result = { id: record.analysisId, status: "COMPLETED" } as Analysis;
  const full = { analysis_id: record.analysisId } as ReportV1;
  const published: unknown[] = [];
  await loadScopedResult(record.analysisId, {
    current: () => true, analysis: async () => result, report: async () => full,
    publish: (analysis, report) => published.push([analysis, report]),
  });
  assert.deepEqual(published, [[result, null], [result, full]]);
});

test("an owner change while an analysis lookup is pending cannot publish or request its report", async () => {
  let current = true;
  let resolve!: (value: Analysis) => void;
  const pending = loadScopedResult(record.analysisId, {
    current: () => current,
    analysis: () => new Promise<Analysis>(done => { resolve = done; }),
    report: async () => { assert.fail("Old owner report must not be requested"); },
    publish: () => assert.fail("Old owner analysis must not be restored"),
  });
  current = false;
  resolve({ status: "COMPLETED" } as Analysis);
  await pending;
});

test("an owner change or newer lookup during report retrieval cannot restore stale report", async () => {
  let current = true;
  let resolve!: (value: ReportV1) => void;
  const published: unknown[] = [];
  const pending = loadScopedResult(record.analysisId, {
    current: () => current, analysis: async () => ({ status: "COMPLETED" } as Analysis),
    report: () => new Promise<ReportV1>(done => { resolve = done; }),
    publish: (_analysis, report) => published.push(report),
  });
  await Promise.resolve();
  current = false;
  resolve({ analysis_id: record.analysisId } as ReportV1);
  await pending;
  assert.deepEqual(published, [null]);
});

test("saved capture opens automatically before lookup; polling failure leaves owner recovery available", async () => {
  const events: string[] = [];
  let stored: LastCapture | undefined;
  await assert.rejects(saveOpenAndLoadResult(record, {
    save: async last => { stored = last; events.push("save"); },
    open: async id => { assert.equal(id, record.analysisId); events.push("open"); },
    load: async id => { assert.equal(id, record.analysisId); events.push("load"); throw new Error("Lookup failed"); },
    storageFailed: () => assert.fail("Storage succeeded"),
  }), /Lookup failed/);
  assert.deepEqual(events, ["save", "open", "load"]);
  assert.deepEqual(restoreLastCapture(stored, "owner-one"), record);
  assert.equal(restoreLastCapture(stored, "owner-two"), null);
  assert.equal(restoreLastCapture(stored, null), null);
});

test("storage failure is reported while the captured result still opens and loads", async () => {
  const events: string[] = [];
  await saveOpenAndLoadResult(record, {
    save: async () => { events.push("save"); throw new Error("Storage failed"); },
    storageFailed: () => { events.push("storage warning"); },
    open: async () => { events.push("open"); },
    load: async () => { events.push("load"); },
  });
  assert.deepEqual(events, ["save", "storage warning", "open", "load"]);
});

test("last result restoration rejects malformed or unsupported sources and keeps legacy 1688 recovery", () => {
  assert.equal(restoreLastCapture({ ...record, sourceUrl: "https://evil.example/" }, record.ownerId), null);
  assert.equal(restoreLastCapture({ ...record, analysisId: 123 }, record.ownerId), null);
  assert.equal(restoreLastCapture({ ...record, sourceUrl: record.sourceUrl + "&id=1" }, record.ownerId), null);
  const legacy = { ...record, sourceUrl: "https://detail.1688.com/offer/996518024136.html" };
  assert.deepEqual(restoreLastCapture(legacy, record.ownerId), legacy);
  const shop = { ...record, sourceUrl: "https://shop159450000.world.taobao.com/category.htm" };
  assert.deepEqual(restoreLastCapture(shop, record.ownerId), shop);
  for (const suffix of ["\n", "\r", "\u2028", "\u2029"]) {
    assert.equal(restoreLastCapture({ ...record, sourceUrl: record.sourceUrl + suffix }, record.ownerId), null);
    assert.equal(restoreLastCapture({ ...shop, sourceUrl: shop.sourceUrl + suffix }, record.ownerId), null);
  }
  for (const sourceUrl of [shop.sourceUrl + "?id=1", "https://shop159450000.taobao.com.evil.test/", "https://item.taobao.com:443/item.htm?id=1", "https://user@item.taobao.com/item.htm?id=1"]) {
    assert.equal(restoreLastCapture({ ...record, sourceUrl }, record.ownerId), null);
  }
});
