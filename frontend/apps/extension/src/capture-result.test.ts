import assert from "node:assert/strict";
import test from "node:test";
import { restoreLastCapture, saveOpenAndLoadResult, type LastCapture } from "./capture-result";

const record: LastCapture = { analysisId: "6c93a530-9914-4ead-89ee-c8083f5effb8",
  sourceUrl: "https://item.taobao.com/item.htm?id=1076425861755", ownerId: "owner-one" };

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
});
