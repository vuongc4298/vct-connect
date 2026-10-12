import assert from "node:assert/strict";
import test from "node:test";
import { runCollection, type RunnerDependencies } from "./collection-runner";
import { factoryUrl, shopUrl, type CollectionJob, type SupplierBundle } from "./linked-capture";

const source = "https://detail.1688.com/offer/1027322610455.html";
const shop = "https://shopabcdef123.1688.com/";
const factory = "https://www.1688.com/factory/b2b-abcdef123.html";
const job: CollectionJob = { id: "00000000-0000-0000-0000-000000000001", ownerId: "user_one", sourceUrl: source, startedAt: 0, stage: "STARTING" };

function harness(overrides: Partial<RunnerDependencies> = {}) {
  const stages: string[] = [], submissions: SupplierBundle[] = [];
  let begins = 0, accepted = 0, cleanup = 0;
  const dependencies: RunnerDependencies = {
    now: () => 0,
    product: async () => ({ product: { source_url: source, offer_id: "1027322610455", fields: { product_title: "Shirt" } }, shopLink: shop }),
    begin: async () => { begins++; }, finish: async b => { submissions.push(b); },
    permitted: async () => true,
    shop: async () => ({ source_url: shop, credit_url: shop + "page/creditdetail.html", factory_url: factory }),
    factory: async () => ({ source_url: factory, canonical_url: factory, shop_url: shop, claims: [{ name: "成立时间", value: "2025.07.14" }] }),
    save: async j => { stages.push(j.stage); }, accepted: async () => { accepted++; }, cleanup: async () => { cleanup++; },
    ...overrides,
  };
  return { dependencies, stages, submissions, counts: () => ({ begins, accepted, cleanup }) };
}

test("one durable reservation and one combined submission survive popup disappearance", async () => {
  const h = harness(); await runCollection(job, h.dependencies);
  assert.deepEqual(h.counts(), { begins: 1, accepted: 1, cleanup: 1 });
  assert.deepEqual(h.stages, ["STARTING", "SHOP", "FACTORY", "ASSESSING"]);
  assert.equal(h.submissions.length, 1);
  assert.deepEqual(h.submissions[0].outcomes, [{ page: "SHOP", status: "OK" }, { page: "FACTORY", status: "OK" }]);
  assert.equal(h.submissions[0].factory?.shop_url, shop);
});

test("denied optional permission submits only product without linked navigation", async () => {
  const h = harness({ permitted: async () => false, shop: async () => { throw new Error("must not run"); } });
  await runCollection(job, h.dependencies);
  assert.equal(h.submissions[0].shop, undefined);
  assert.equal(h.submissions[0].outcomes[0].status, "NO_PERMISSION");
  assert.deepEqual(h.counts(), { begins: 1, accepted: 1, cleanup: 1 });
});

test("blocked shop is partial and factory mismatch is discarded", async () => {
  const blocked = harness({ shop: async () => { throw new Error("blocked"); } });
  await runCollection(job, blocked.dependencies);
  assert.equal(blocked.submissions[0].outcomes[0].status, "UNAVAILABLE");
  const mismatch = harness({ factory: async () => ({ source_url: factory, canonical_url: factory,
    shop_url: "https://shopdifferent123.1688.com/", claims: [] }) });
  await runCollection(job, mismatch.dependencies);
  assert.equal(mismatch.submissions[0].factory, undefined);
});

test("final submission failure keeps reserved analysis and always cleans up", async () => {
  const h = harness({ finish: async () => { throw new Error("network"); } });
  await runCollection(job, h.dependencies);
  assert.equal(h.stages.at(-1), "ERROR");
  assert.equal(h.counts().begins, 1);
  assert.equal(h.counts().cleanup, 1);
});

test("URL identities reject foreign hosts and conflicting member IDs", () => {
  assert.equal(shopUrl("https://evil.test/?shop=shopabcdef123.1688.com"), null);
  assert.equal(factoryUrl("https://sale.1688.com/factory/card.html?memberId=b2b-abcdef123&memberId=b2b-other123"), null);
  assert.equal(factoryUrl("https://sale.1688.com/factory/card.html?memberId=b2b-abcdef123&facMemId=b2b-other123"), null);
  assert.equal(factoryUrl("https://sale.1688.com/factory/card.html?memberId=b2b-abcdef123"), factory);
});

test("HTML snapshots upload in the same reservation, with shop captured before factory navigation", async () => {
  const pages: string[] = [];
  const h = harness({ html: async (page, source_url) => { pages.push(page); return { page, source_url, html: '<div>public</div>' }; } });
  let initial: SupplierBundle | undefined;
  h.dependencies.begin = async bundle => { initial = structuredClone(bundle); };
  await runCollection(job, h.dependencies);
  assert.ok(initial);
  assert.deepEqual(pages, ['PRODUCT', 'SHOP', 'FACTORY']);
  assert.equal(initial.html_sources?.length, 1);
  assert.equal(h.submissions[0].html_sources?.length, 3);
  assert.equal(h.submissions[0].job_id, initial.job_id);
});

test("optional HTML failure preserves the selected evidence and final submission", async () => {
  const h = harness({ html: async () => { throw new Error('Too large'); } });
  await runCollection(job, h.dependencies);
  assert.equal(h.submissions.length, 1);
  assert.equal(h.submissions[0].html_capture_requested, true);
  assert.ok(h.submissions[0].factory);
  assert.equal(h.submissions[0].html_sources, undefined);
});
