import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { act, create } from "react-test-renderer";
import { component, deferred, text, windowState } from "../../../tests/mount-component.mjs";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { default: Page } = await component("apps/web/app/page.tsx");
const id = "00000000-0000-0000-0000-000000000123";
const source = "https://detail.1688.com/offer/996518024136.html";
const getToken = async () => "owner-token";
const base = { id, source_url: source, attempt_count: 1, failure_code: null, extraction_method: "PUBLIC_HTTP", result: null };
const history = { ...base, status: "PROCESSING", created_at: "2026-10-10T00:00:00Z", supplier_name: "Saved supplier", platform: "1688", report_available: false, risk_label: null, confidence: null, coverage: null };

test("signed-in workspace opens the guide without an extraction form or background submissions", async () => {
  const original = globalThis.fetch;
  globalThis.window = windowState().state;
  globalThis.__mountedAuth = { isLoaded: true, isSignedIn: true, userId: "owner", getToken };
  const requests = [];
  globalThis.fetch = async url => { requests.push(String(url)); throw new Error("Unexpected request"); };
  let mounted;
  try {
    await act(async () => { mounted = create(React.createElement(Page)); });
    assert.match(text(mounted), /Thu thập ngay trên trang nhà cung cấp/);
    assert.equal(mounted.root.findAllByType("form").length, 0);
    assert.equal(mounted.root.findAllByType("input").length, 0);
    assert.deepEqual(requests, []);
  } finally { if (mounted) await act(async () => mounted.unmount()); globalThis.fetch = original; }
});

for (const view of ["history", "watchlist"]) {
  test(`mounted Page reopens ${view} and polls its matching report with a read-only source`, async () => {
    const original = globalThis.fetch;
    const clock = windowState();
    globalThis.window = clock.state;
    globalThis.__mountedAuth = { isLoaded: true, isSignedIn: true, userId: "owner", getToken };
    let polls = 0;
    globalThis.fetch = async url => {
      if (String(url) === "/api/v1/analyses") return Response.json([history]);
      if (String(url) === "/api/v1/watchlist") return Response.json([{ ...history, id: "entry", analysis_id: id, name: "Saved supplier", analysis_status: "PROCESSING" }]);
      assert.equal(String(url), `/api/v1/analyses/${id}`);
      return Response.json({ ...base, status: ++polls === 1 ? "PROCESSING" : "ASSESSING" });
    };
    let mounted;
    try {
      await act(async () => { mounted = create(React.createElement(Page)); });
      const label = view === "history" ? "Lịch sử," : "Theo dõi,";
      await act(async () => mounted.root.findAllByType("button").find(button => button.props["aria-label"]?.startsWith(label)).props.onClick());
      const open = view === "history" ? mounted.root.findByProps({ className: "button button-ghost history-open-button" }) : mounted.root.findAllByType("button").find(button => button.children.some(child => typeof child === "string" && child.includes("Mở phân tích")));
      await act(async () => open.props.onClick());
      assert.equal(new URL(clock.state.location.href).searchParams.get("analysis"), id);
      assert.equal(mounted.root.findAllByType("input").length, 0);
      assert.ok(mounted.root.findAllByType("a").some(link => link.props.href === source));
      await act(async () => clock.tick(1500));
      assert.equal(polls, 2);
      await act(async () => mounted.root.findByProps({ "aria-label": "Tiện ích & hướng dẫn" }).props.onClick());
      assert.equal(new URL(clock.state.location.href).searchParams.has("analysis"), false);
      assert.match(text(mounted), /Thu thập ngay trên trang nhà cung cấp/);
    } finally { if (mounted) await act(async () => mounted.unmount()); globalThis.fetch = original; }
  });
}

for (const view of ["history", "watchlist"]) {
  test(`mounted Page refetches a completed analysis when reopening the same ID from ${view}`, async () => {
    const original = globalThis.fetch;
    const clock = windowState();
    clock.state.location.href += `?analysis=${id}`;
    clock.state.location.search = `?analysis=${id}`;
    globalThis.window = clock.state;
    globalThis.__mountedAuth = { isLoaded: true, isSignedIn: true, userId: "owner", getToken };
    let polls = 0;
    globalThis.fetch = async url => {
      if (String(url) === "/api/v1/analyses") return Response.json([{ ...history, status: "COMPLETED" }]);
      if (String(url) === "/api/v1/watchlist") return Response.json([{ ...history, id: "entry", analysis_id: id, name: "Saved supplier", analysis_status: "COMPLETED" }]);
      if (String(url).endsWith("/report")) return Response.json({ detail: "Report not found" }, { status: 404 });
      polls++;
      return Response.json({ ...base, status: "COMPLETED", result: { source_url: source, extraction_status: "PARTIAL" } });
    };
    let mounted;
    try {
      await act(async () => { mounted = create(React.createElement(Page)); });
      assert.equal(polls, 1);
      const label = view === "history" ? "Lịch sử," : "Theo dõi,";
      await act(async () => mounted.root.findAllByType("button").find(button => button.props["aria-label"]?.startsWith(label)).props.onClick());
      const open = view === "history"
        ? mounted.root.findByProps({ className: "button button-ghost history-open-button" })
        : mounted.root.findAllByType("button").find(button => button.children.some(child => typeof child === "string" && child.includes("Mở phân tích")));
      await act(async () => open.props.onClick());
      assert.equal(polls, 2);
      assert.match(text(mounted), /Chưa có báo cáo đánh giá đầy đủ/);
      assert.ok(mounted.root.findAllByType("a").some(link => link.props.href === source));
    } finally {
      if (mounted) await act(async () => mounted.unmount());
      globalThis.fetch = original;
    }
  });
}

test("mounted Page completed extraction-only result does not mark assessment/report done", async () => {
  const original = globalThis.fetch;
  const clock = windowState();
  clock.state.location.href += `?analysis=${id}`;
  clock.state.location.search = `?analysis=${id}`;
  globalThis.window = clock.state;
  globalThis.__mountedAuth = { isLoaded: true, isSignedIn: true, userId: "owner", getToken };
  globalThis.fetch = async url => String(url).endsWith("/report")
    ? Response.json({ detail: "Report not found" }, { status: 404 })
    : Response.json({ ...base, status: "COMPLETED", result: { source_url: source, extraction_status: "PARTIAL" }, supplier_data: null });
  let mounted;
  try {
    await act(async () => { mounted = create(React.createElement(Page)); });
    assert.match(text(mounted), /Chưa có báo cáo đánh giá đầy đủ/);
    const progress = mounted.root.findByProps({ "aria-label": "Tiến độ phân tích" });
    for (const title of ["Đánh giá", "Báo cáo"]) {
      const step = progress.findAllByType("strong").find(node => node.children[0] === title).parent;
      assert.equal(step.props.className, "");
      assert.notEqual(step.findByType("span").children[0], "✓");
    }
  } finally {
    if (mounted) await act(async () => mounted.unmount());
    globalThis.fetch = original;
  }
});

test("signed-out landing has no URL form, download or analysis requests", async () => {
  const original = globalThis.fetch;
  globalThis.window = windowState().state;
  globalThis.__mountedAuth = { isLoaded: true, isSignedIn: false, userId: null, getToken };
  const requests = [];
  globalThis.fetch = async url => { requests.push(String(url)); throw new Error("Unexpected request"); };
  let mounted;
  try {
    await act(async () => { mounted = create(React.createElement(Page)); });
    assert.match(text(mounted), /Đăng nhập/);
    assert.equal(mounted.root.findAllByType("form").length, 0);
    assert.equal(mounted.root.findAllByType("input").length, 0);
    assert.doesNotMatch(text(mounted), /↓ Tải tiện ích|Guangzhou Future Tech|BÁO CÁO MINH HOẠ/);
    assert.deepEqual(requests, []);
  } finally { if (mounted) await act(async () => mounted.unmount()); globalThis.fetch = original; }
});

test("switching workspace accounts cancels the old download and enables the new account", async () => {
  const original = globalThis.fetch;
  globalThis.window = windowState().state;
  const oldToken = deferred(), requests = [];
  globalThis.__mountedAuth = { isLoaded: true, isSignedIn: true, userId: "old-owner", getToken: () => oldToken.promise };
  globalThis.fetch = async (url, init) => { requests.push(init.headers.Authorization); return Response.json({ detail: "Sign in" }, { status: 401 }); };
  const button = mounted => mounted.root.findAllByType("button").find(item => item.children.some(value => typeof value === "string" && /Tải tiện ích|Đang tải/.test(value)));
  let mounted;
  try {
    await act(async () => { mounted = create(React.createElement(Page)); });
    await act(async () => button(mounted).props.onClick());
    assert.equal(button(mounted).props.disabled, true);
    globalThis.__mountedAuth = { isLoaded: true, isSignedIn: true, userId: "new-owner", getToken: async () => "new-token" };
    await act(async () => mounted.update(React.createElement(Page)));
    assert.equal(button(mounted).props.disabled, false);
    await act(async () => oldToken.resolve("old-token"));
    assert.deepEqual(requests, []);
    await act(async () => button(mounted).props.onClick());
    assert.deepEqual(requests, ["Bearer new-token"]);
    assert.equal(button(mounted).props.disabled, false);
  } finally { if (mounted) await act(async () => mounted.unmount()); globalThis.fetch = original; }
});

const { ReportPages } = await component("apps/web/app/report-visuals.tsx");
test("five-item paging exposes the remaining source text without deleting it", async () => {
  let mounted;
  const values = Array.from({ length: 9 }, (_, i) => `Item ${i + 1}`);
  await act(async () => { mounted = create(React.createElement(ReportPages, { items: values, label: "Test list" }, items => React.createElement("ul", null, items.map(item => React.createElement("li", { key: item }, item))))); });
  try {
    assert.equal(mounted.root.findAllByType("li").length, 5);
    await act(async () => mounted.root.findAllByType("button")[1].props.onClick());
    assert.deepEqual(mounted.root.findAllByType("li").map(item => item.children[0]), values.slice(5));
    await act(async () => mounted.root.findAllByType("button")[0].props.onClick());
    assert.equal(mounted.root.findAllByType("li").length, 5);
  } finally { await act(async () => mounted.unmount()); }
});
