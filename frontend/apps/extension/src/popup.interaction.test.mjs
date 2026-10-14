import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { act, create } from "react-test-renderer";
import { component, deferred, text } from "../../../tests/mount-component.mjs";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
globalThis.document = { getElementById: () => null };
const { App } = await component("apps/extension/src/popup.tsx");
const source = "https://detail.1688.com/offer/996518024136.html";
const id = "00000000-0000-0000-0000-000000000123";
const record = { ownerId: "owner-one", analysisId: id, sourceUrl: source };
const getToken = async () => "token";
const analysis = { id, status: "COMPLETED", source_url: source, result: { source_url: source, extraction_status: "PARTIAL" }, supplier_data: { supplier_name: "First owner supplier", completeness: 0.5 } };
const report = { analysis_id: id, risk: { label: "HIGH", confidence: 0.7, coverage: 0.5 } };

test("Alibaba Company overview is recognized, localized and bound to the pending supplier", async () => {
  environment();
  const sourceUrl = "https://www.alibaba.com/product-detail/Yiheng-Paddle_1601711788226.html";
  const companyUrl = "https://yihengsportinggoods.en.alibaba.com/", factoryUrl = companyUrl + "company_profile.html";
  chrome.storage.local.get = async () => ({ collectionJob: { id, ownerId: record.ownerId, sourceUrl, startedAt: Date.now(), expiresAt: Date.now()+1800000, stage: "WAITING_FACTORY", companyUrl, factoryUrl } });
  chrome.tabs.query = async () => [{id:3,url:"https://yihengsportinggoods.m.en.alibaba.com/company_profile.html"}];
  chrome.runtime = {sendMessage:async()=>({ok:true})};
  let mounted;
  try {
    await act(async()=>{mounted=create(React.createElement(App));});
    assert.match(text(mounted),/Hồ sơ công ty/);
    assert.match(text(mounted),/Company overview \/ Company profile/);
    const action = mounted.root.findAllByType("button").find(b=>b.children.join("")==="Lưu HTML hồ sơ công ty và phân tích");
    assert.equal(action.props.disabled,false);
    assert.doesNotMatch(text(mounted),/Lưu HTML nhà máy/);
    await act(async()=>mounted.unmount());mounted=null;
    chrome.tabs.query = async()=>[{id:3,url:"https://other.m.en.alibaba.com/company_profile.html"}];
    await act(async()=>{mounted=create(React.createElement(App));});
    assert.equal(mounted.root.findAllByType("button").find(b=>b.children.join("")==="Lưu HTML hồ sơ công ty và phân tích").props.disabled,true);
  } finally {if(mounted)await act(async()=>mounted.unmount());}
});

test("Vietnamese default recognizes the named factory; language preference survives reopening", async () => {
  environment();
  let stored = { collectionJob: { id, ownerId: record.ownerId, sourceUrl: source, startedAt: Date.now(),
    expiresAt: Date.now() + 1800000, stage: "WAITING_FACTORY", companyUrl: "https://hztxsy.1688.com/",
    factoryUrl: "https://www.1688.com/factory/hztxsy.html" } };
  chrome.tabs.query = async () => [{ id: 3, url: "https://sale.1688.com/factory/card.html?memberId=hztxsy&facMemId=hztxsy" }];
  chrome.runtime = { sendMessage: async () => ({ ok: true }) };
  chrome.storage.local = { get: async () => stored, set: async value => { stored = { ...stored, ...value }; } };
  let mounted;
  try {
    await act(async () => { mounted = create(React.createElement(App)); });
    assert.match(text(mounted), /Đã lưu cửa hàng · tiếp theo là nhà máy/);
    assert.equal(mounted.root.findAllByType("button").find(b => b.children.join("") === "Lưu HTML nhà máy và phân tích").props.disabled, false);
    await act(async () => mounted.root.findAllByType("button").find(b => b.children.join("") === "EN").props.onClick());
    assert.equal(stored.uiLanguage, "en");
    assert.equal(stored.collectionJob.stage, "WAITING_FACTORY");
    await act(async () => mounted.unmount()); mounted = null;
    await act(async () => { mounted = create(React.createElement(App)); });
    assert.match(text(mounted), /Shop saved · factory next/);
  } finally { if (mounted) await act(async () => mounted.unmount()); }
});

function environment() {
  globalThis.__mountedAuth = { isLoaded: true, isSignedIn: true, userId: record.ownerId, getToken };
  globalThis.chrome = {
    tabs: { query: async () => [{ url: source }] },
    storage: { local: { get: async () => ({ lastCapture: record }) } },
  };
}

test("guided popup enables company capture only for the product's linked company", async () => {
  const original = globalThis.fetch;
  environment();
  const company = "https://shopabcdef123.1688.com/";
  const job = { id, ownerId: record.ownerId, sourceUrl: source, startedAt: Date.now(), expiresAt: Date.now() + 1800000,
    stage: "WAITING_COMPANY", companyUrl: company };
  globalThis.chrome.tabs.query = async () => [{ id: 2, url: company }];
  globalThis.chrome.storage.local.get = async () => ({ collectionJob: job });
  globalThis.fetch = async () => { throw new Error("No report yet"); };
  let mounted;
  try {
    await act(async () => { mounted = create(React.createElement(App, { initialLanguage: "en" })); });
    assert.match(text(mounted), /Product captured · shop next/);
    assert.match(text(mounted), /close it with X/);
    assert.equal(mounted.root.findAllByType("button").find(b => b.children.join("") === "Save shop HTML").props.disabled, false);
    await act(async () => mounted.unmount());
    mounted = null;
    globalThis.chrome.tabs.query = async () => [{ id: 2, url: "https://shopwrong123.1688.com/" }];
    await act(async () => { mounted = create(React.createElement(App, { initialLanguage: "en" })); });
    assert.equal(mounted.root.findAllByType("button").find(b => b.children.join("") === "Save shop HTML").props.disabled, true);
  } finally {
    if (mounted) await act(async () => mounted.unmount());
    globalThis.fetch = original;
  }
});

test("reopened popup restores supplier collection progress only for its owner", async () => {
  const original = globalThis.fetch;
  environment();
  globalThis.chrome.storage.local.get = async () => ({ collectionJob: {
    id, ownerId: record.ownerId, sourceUrl: source, startedAt: Date.now(), stage: "FACTORY",
  } });
  globalThis.fetch = async () => { throw new Error("No completed result should be fetched"); };
  let mounted;
  try {
    await act(async () => { mounted = create(React.createElement(App, { initialLanguage: "en" })); });
    assert.match(text(mounted), /Reading factory profile/);
    assert.match(text(mounted), /You can close this popup/);
    globalThis.__mountedAuth = { ...globalThis.__mountedAuth, userId: "owner-two" };
    await act(async () => mounted.update(React.createElement(App, { initialLanguage: "en" })));
    assert.doesNotMatch(text(mounted), /Reading factory profile/);
  } finally {
    if (mounted) await act(async () => mounted.unmount());
    globalThis.fetch = original;
  }
});

test("mounted popup automatically restores report without Reload and suppresses premature no-report copy", async () => {
  const original = globalThis.fetch;
  environment();
  const full = deferred();
  const requests = [];
  globalThis.fetch = async url => {
    requests.push(String(url));
    return String(url).endsWith("/report") ? full.promise : Response.json(analysis);
  };
  let mounted;
  try {
    await act(async () => { mounted = create(React.createElement(App, { initialLanguage: "en" })); });
    assert.deepEqual(requests, [`https://vct.example/api/v1/analyses/${id}`, `https://vct.example/api/v1/analyses/${id}/report`]);
    assert.match(text(mounted), /Loading saved assessment report/);
    assert.doesNotMatch(text(mounted), /No scored report available|full assessment report is not available/);
    await act(async () => full.resolve(Response.json(report)));
    assert.match(text(mounted), /High/);
    assert.doesNotMatch(text(mounted), /Loading saved assessment report|No scored report available/);
  } finally {
    if (mounted) await act(async () => mounted.unmount());
    globalThis.fetch = original;
  }
});

for (const stage of ["analysis", "report"]) {
  test(`mounted popup owner switch during restored ${stage} lookup cannot restore previous owner's result`, async () => {
    const original = globalThis.fetch;
    environment();
    const pending = deferred();
    const requests = [];
    globalThis.fetch = async url => {
      requests.push(String(url));
      if (stage === "analysis" || String(url).endsWith("/report")) return pending.promise;
      return Response.json(analysis);
    };
    let mounted;
    try {
      await act(async () => { mounted = create(React.createElement(App, { initialLanguage: "en" })); });
      globalThis.__mountedAuth = { ...globalThis.__mountedAuth, userId: "owner-two" };
      await act(async () => mounted.update(React.createElement(App, { initialLanguage: "en" })));
      await act(async () => pending.resolve(Response.json(stage === "analysis" ? analysis : report)));
      assert.doesNotMatch(text(mounted), /First owner supplier|Last page:|High|Reload last result/);
      assert.equal(requests.length, stage === "analysis" ? 1 : 2);
    } finally {
      if (mounted) await act(async () => mounted.unmount());
      globalThis.fetch = original;
    }
  });
}

test("mounted popup successful automatic poll clears a previous lookup error", async () => {
  const original = globalThis.fetch;
  const originalInterval = globalThis.setInterval;
  const originalClear = globalThis.clearInterval;
  environment();
  let interval;
  globalThis.setInterval = callback => { interval = callback; return 1; };
  globalThis.clearInterval = () => {};
  let polls = 0;
  globalThis.fetch = async url => {
    if (String(url).endsWith("/report")) return Response.json(report);
    polls++;
    if (polls === 2) return Response.json({ detail: "Temporary lookup failure" }, { status: 503 });
    return Response.json({ ...analysis, status: polls === 1 ? "ASSESSING" : "COMPLETED" });
  };
  let mounted;
  try {
    await act(async () => { mounted = create(React.createElement(App, { initialLanguage: "en" })); });
    await act(async () => interval());
    assert.match(text(mounted), /Temporary lookup failure/);
    await act(async () => interval());
    assert.match(text(mounted), /High/);
    assert.doesNotMatch(text(mounted), /Temporary lookup failure/);
  } finally {
    if (mounted) await act(async () => mounted.unmount());
    globalThis.fetch = original;
    globalThis.setInterval = originalInterval;
    globalThis.clearInterval = originalClear;
  }
});


test("shop-saved popup offers factory capture or product-shop finish without another product reservation", async () => {
  const original=globalThis.fetch;environment();
  const company="https://shopabcdef123.1688.com/";
  const factory="https://www.1688.com/factory/b2b-abcdef123.html";
  const job={id,ownerId:record.ownerId,sourceUrl:source,startedAt:Date.now(),expiresAt:Date.now()+1800000,stage:"WAITING_FACTORY",companyUrl:company,factoryUrl:factory};
  chrome.tabs.query=async()=>[{id:3,url:factory}];
  chrome.runtime={sendMessage:async()=>({ok:true})};
  chrome.storage.local.get=async()=>({collectionJob:job});
  globalThis.fetch=async()=>{throw new Error("Not reporting yet");};
  let mounted;
  try {
    await act(async()=>{mounted=create(React.createElement(App, { initialLanguage: "en" }));});
    assert.match(text(mounted),/Shop saved · factory next/);
    assert.match(text(mounted),/Finish with captured product & shop/);
    assert.equal(mounted.root.findAllByType("button").find(b=>b.children.join("")==="Save factory HTML & analyze").props.disabled,false);
    await act(async()=>mounted.unmount());mounted=null;
    chrome.tabs.query=async()=>[{id:3,url:"https://www.1688.com/factory/b2b-other123.html"}];
    await act(async()=>{mounted=create(React.createElement(App, { initialLanguage: "en" }));});
    assert.equal(mounted.root.findAllByType("button").find(b=>b.children.join("")==="Save factory HTML & analyze").props.disabled,true);
  } finally {if(mounted)await act(async()=>mounted.unmount());globalThis.fetch=original;}
});
