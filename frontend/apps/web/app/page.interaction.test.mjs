import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { act, create } from "react-test-renderer";
import { component, deferred, text, windowState } from "../../../tests/mount-component.mjs";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { default: Page } = await component("apps/web/app/page.tsx");
const id = "00000000-0000-0000-0000-000000000123";
const source = "https://detail.1688.com/offer/996518024136.html";
const typed = "https://item.taobao.com/item.htm?id=1076425861755";
const getToken = async () => "owner-token";
const base = { id, source_url: source, attempt_count: 1, failure_code: null, extraction_method: "PUBLIC_HTTP", result: null };
const history = { ...base, status: "PROCESSING", created_at: "2026-10-10T00:00:00Z", supplier_name: "Saved supplier", platform: "1688", report_available: false, risk_label: null, confidence: null, coverage: null };

for (const view of ["history", "watchlist"]) {
  test(`mounted Page reopens ${view} with matching ID/source and clears file while later polls preserve edits`, async () => {
    const original = globalThis.fetch;
    const clock = windowState();
    globalThis.window = clock.state;
    globalThis.__mountedAuth = { isLoaded: true, isSignedIn: true, userId: "owner", getToken };
    const requests = [];
    let polls = 0;
    globalThis.fetch = async (url, init) => {
      requests.push(String(url));
      if (String(url) === "/api/v1/analyses") return Response.json([history]);
      if (String(url) === "/api/v1/watchlist") return Response.json([{ ...history, id: "saved-entry", analysis_id: id, name: "Saved supplier", overall_risk: null, analysis_status: "PROCESSING" }]);
      if (String(url) === `/api/v1/analyses/${id}`) return Response.json({ ...base, status: ++polls === 1 ? "PROCESSING" : "ASSESSING" });
      throw new Error(`Unexpected request ${url}`);
    };
    let fileNode;
    let mounted;
    try {
      await act(async () => { mounted = create(React.createElement(Page), { createNodeMock: element => element.props.id === "saved-page" ? (fileNode = { value: "" }) : null }); });
      fileNode.value = "saved.html";
      await act(async () => mounted.root.findByProps({ id: "saved-page" }).props.onChange({ target: { files: [new File(["saved"], "saved.html")] } }));
      assert.match(text(mounted), /Nhập trang đã lưu/);
      const label = view === "history" ? "Lịch sử," : "Theo dõi,";
      await act(async () => mounted.root.findAllByType("button").find(button => button.props["aria-label"]?.startsWith(label)).props.onClick());
      const open = view === "history"
        ? mounted.root.findByProps({ className: "button button-ghost history-open-button" })
        : mounted.root.findAllByType("button").find(button => button.children.some(child => typeof child === "string" && child.includes("Mở phân tích")));
      await act(async () => open.props.onClick());
      assert.equal(mounted.root.findByProps({ id: "source-url" }).props.value, source);
      assert.equal(fileNode.value, "");
      assert.doesNotMatch(text(mounted), /Nhập trang đã lưu/);
      assert.equal(new URL(clock.state.location.href).searchParams.get("analysis"), id);
      assert.ok(requests.includes(`/api/v1/analyses/${id}`));
      await act(async () => mounted.root.findByProps({ id: "source-url" }).props.onChange({ target: { value: typed } }));
      await act(async () => clock.tick(1500));
      assert.equal(polls, 2);
      assert.equal(mounted.root.findByProps({ id: "source-url" }).props.value, typed);
    } finally {
      if (mounted) await act(async () => mounted.unmount());
      globalThis.fetch = original;
    }
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
      assert.equal(mounted.root.findByProps({ id: "source-url" }).props.value, source);
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
    for (const title of ["Đánh giá", "Báo cáo"]) {
      const step = mounted.root.findAllByType("strong").find(node => node.children[0] === title).parent;
      assert.equal(step.props.className, "");
      assert.notEqual(step.findByType("span").children[0], "✓");
    }
  } finally {
    if (mounted) await act(async () => mounted.unmount());
    globalThis.fetch = original;
  }
});

test("mounted Landing completes synthetic tracer without requesting a preview", async () => {
  const original = globalThis.fetch;
  globalThis.window = windowState().state;
  globalThis.__mountedAuth = { isLoaded: true, isSignedIn: false, userId: null, getToken };
  const requests = [];
  globalThis.fetch = async (url, init) => {
    requests.push(String(url));
    if (init?.method === "POST") return Response.json({ id, status: "QUEUED" }, { status: 202 });
    return Response.json({ ...base, status: "COMPLETED", extraction_method: "FIXTURE", result: { fixture: true, source_url: source } });
  };
  let mounted;
  try {
    await act(async () => { mounted = create(React.createElement(Page)); });
    assert.equal(mounted.root.findByProps({ id: "guest-source-url" }).props.value, "");
    await act(async () => mounted.root.findByProps({ id: "guest-source-url" }).props.onChange({ target: { value: "https://detail.1688.com/offer/123456789012.html" } }));
    await act(async () => mounted.root.findByType("form").props.onSubmit({ preventDefault() {} }));
    assert.match(text(mounted), /Đã hoàn tất tracer tổng hợp/);
    assert.doesNotMatch(text(mounted), /Preview not found|Báo cáo đã sẵn sàng/);
    assert.equal(requests.some(url => url.endsWith("/preview")), false);
  } finally {
    if (mounted) await act(async () => mounted.unmount());
    globalThis.fetch = original;
  }
});

test("mounted Landing submits chosen live URL, labels initial extraction and displays returned preview", async () => {
  const original = globalThis.fetch;
  globalThis.window = windowState().state;
  globalThis.__mountedAuth = { isLoaded: true, isSignedIn: false, userId: null, getToken };
  const status = deferred();
  const requests = [];
  globalThis.fetch = async (url, init) => {
    requests.push(String(url));
    if (init?.method === "POST") {
      assert.equal(JSON.parse(init.body).source_url, typed);
      return Response.json({ id, status: "QUEUED" }, { status: 202 });
    }
    if (String(url).endsWith("/preview")) return Response.json({ schema_version: "guest-preview.v1", analysis_id: id, supplier_name: "Test supplier preview", platform: "TAOBAO", extracted_at: "2026-10-10T00:00:00Z", confidence: 0.5, coverage: 0.5, information_state: "LIMITED_PREVIEW", missing_source_fields: [], missing_risk_dimensions: [], uncertainties_vi: [], limitations_vi: [], registration_required: true });
    return status.promise;
  };
  let mounted;
  try {
    await act(async () => { mounted = create(React.createElement(Page)); });
    await act(async () => mounted.root.findByProps({ id: "guest-source-url" }).props.onChange({ target: { value: typed } }));
    await act(async () => mounted.root.findByType("form").props.onSubmit({ preventDefault() {} }));
    assert.match(text(mounted), /"Trích xuất"/);
    assert.doesNotMatch(text(mounted), /Kết quả tracer/);
    await act(async () => status.resolve(Response.json({ ...base, source_url: typed, status: "COMPLETED", result: { source_url: typed, extraction_status: "PARTIAL" } })));
    assert.ok(requests.includes(`/api/v1/guest-analyses/${id}/preview`));
    assert.match(text(mounted), /Test supplier preview/);
    assert.match(text(mounted), /gửi lại URL hoặc bằng chứng/);
    assert.match(text(mounted), /không được chuyển vào tài khoản/);
  } finally {
    if (mounted) await act(async () => mounted.unmount());
    globalThis.fetch = original;
  }
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
