import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { act, create } from "react-test-renderer";
import { component, deferred, text } from "../../../tests/mount-component.mjs";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { ExtensionGuide } = await component("apps/web/app/extension-guide.tsx");
function downloadButton(mounted) { return mounted.root.findAllByType("button").find(button => button.children.some(value => typeof value === "string" && /Tải tiện ích|Đang tải/.test(value))); }

test("guide has five installation steps and switches to the correct supplier capture path", async () => {
  globalThis.__mountedAuth = { getToken: async () => "token" };
  let history = 0, mounted;
  try {
    await act(async () => { mounted = create(React.createElement(ExtensionGuide, { getToken: globalThis.__mountedAuth.getToken, onHistory: () => history++ })); });
    assert.equal(mounted.root.findAllByType("ol")[0].findAllByType("li").length, 5);
    for (const list of mounted.root.findAllByType("ol")) assert.ok(list.findAllByType("li").length <= 5);
    assert.deepEqual(mounted.root.findByProps({ "aria-label": "Chọn nền tảng" }).findAllByType("button").map(button => button.children[0]), ["1688", "Alibaba"]);
    assert.doesNotMatch(text(mounted), /Taobao/);
    for (const [platform, expected] of [["1688", /工厂档案/], ["Alibaba", /Company overview/]]) {
      await act(async () => mounted.root.findAllByType("button").find(button => button.children[0] === platform).props.onClick());
      assert.match(text(mounted), expected);
      assert.equal(mounted.root.findByProps({ "aria-label": `Các bước thu thập ${platform}` }).findAllByType("li").length, 4);
    }
    await act(async () => mounted.root.findAllByType("button").find(button => button.children[0] === "Mở lịch sử →").props.onClick());
    assert.equal(history, 1);
  } finally { if (mounted) await act(async () => mounted.unmount()); }
});

test("download uses a fresh bearer token and cleans up its Blob link", async () => {
  const original = { fetch: globalThis.fetch, document: globalThis.document, create: URL.createObjectURL, revoke: URL.revokeObjectURL };
  let clicked = 0, removed = 0, revoked = 0, fetched = 0, mounted;
  globalThis.__mountedAuth = { getToken: async options => { assert.deepEqual(options, { skipCache: true }); return "owner"; } };
  globalThis.document = { createElement: () => ({ click() { clicked++; }, remove() { removed++; } }), body: { appendChild(link) { assert.equal(link.download, "vct-connect-extension.zip"); } } };
  URL.createObjectURL = blob => { assert.equal(blob.type, "application/zip"); return "blob:test"; };
  URL.revokeObjectURL = url => { assert.equal(url, "blob:test"); revoked++; };
  const wait = deferred();
  globalThis.fetch = async (url, init) => { fetched++; assert.equal(url, "/api/v1/extension-download"); assert.equal(init.headers.Authorization, "Bearer owner"); assert.equal(init.cache, "no-store"); return wait.promise; };
  try {
    await act(async () => { mounted = create(React.createElement(ExtensionGuide, { getToken: globalThis.__mountedAuth.getToken, onHistory() {} })); });
    await act(async () => { downloadButton(mounted).props.onClick(); downloadButton(mounted).props.onClick(); });
    assert.equal(fetched, 1); assert.equal(downloadButton(mounted).props.disabled, true);
    await act(async () => wait.resolve(new Response(new Uint8Array([80, 75]), { headers: { "content-type": "application/zip" } })));
    assert.equal(clicked, 1); assert.equal(removed, 1); assert.equal(revoked, 0);
    assert.match(text(mounted), /Đã bắt đầu tải/); assert.equal(downloadButton(mounted).props.disabled, false);
  } finally {
    if (mounted) await act(async () => mounted.unmount());
    assert.equal(revoked, 1);
    globalThis.fetch = original.fetch; globalThis.document = original.document; URL.createObjectURL = original.create; URL.revokeObjectURL = original.revoke;
  }
});

test("session and network errors allow a localized retry, without downloading an error body", async () => {
  const original = globalThis.fetch;
  let mounted;
  try {
    for (const status of [401, 403, 503, 200]) {
      globalThis.__mountedAuth = { getToken: async () => "owner" };
      globalThis.fetch = async () => Response.json({ detail: "private server path" }, { status });
      await act(async () => { mounted = create(React.createElement(ExtensionGuide, { getToken: globalThis.__mountedAuth.getToken, onHistory() {} })); });
      await act(async () => downloadButton(mounted).props.onClick());
      assert.match(text(mounted), status === 401 || status === 403 ? /Phiên đăng nhập đã hết hạn/ : /Chưa thể tải tiện ích/);
      assert.doesNotMatch(text(mounted), /private server path/);
      assert.equal(downloadButton(mounted).props.disabled, false);
      await act(async () => mounted.unmount()); mounted = null;
    }
    globalThis.__mountedAuth = { getToken: async () => null };
    globalThis.fetch = async () => { assert.fail("Tokenless download must not fetch"); };
    await act(async () => { mounted = create(React.createElement(ExtensionGuide, { getToken: globalThis.__mountedAuth.getToken, onHistory() {} })); });
    await act(async () => downloadButton(mounted).props.onClick());
    assert.match(text(mounted), /Phiên đăng nhập đã hết hạn/);
  } finally { if (mounted) await act(async () => mounted.unmount()); globalThis.fetch = original; }
});

test("leaving the guide cancels a pending token/download before it can save a file", async () => {
  const original = globalThis.fetch;
  const token = deferred();
  globalThis.__mountedAuth = { getToken: () => token.promise };
  let mounted, fetched = false;
  globalThis.fetch = async () => { fetched = true; return new Response(); };
  try {
    await act(async () => { mounted = create(React.createElement(ExtensionGuide, { getToken: globalThis.__mountedAuth.getToken, onHistory() {} })); });
    await act(async () => downloadButton(mounted).props.onClick());
    await act(async () => mounted.unmount()); mounted = null;
    await act(async () => token.resolve("old-account"));
    assert.equal(fetched, false);
  } finally { if (mounted) await act(async () => mounted.unmount()); globalThis.fetch = original; }
});

test("a stalled token request times out and allows retry without using its eventual stale token", async () => {
  const originalFetch = globalThis.fetch, originalTimer = globalThis.setTimeout;
  const token = deferred();
  let timeout, fetched = false, mounted;
  globalThis.setTimeout = (callback, delay, ...args) => delay === 45_000 ? (timeout = callback, 123) : originalTimer(callback, delay, ...args);
  globalThis.fetch = async () => { fetched = true; return Response.json({}); };
  try {
    await act(async () => { mounted = create(React.createElement(ExtensionGuide, { getToken: () => token.promise, onHistory() {} })); });
    await act(async () => downloadButton(mounted).props.onClick());
    await act(async () => timeout());
    assert.match(text(mounted), /Tải tiện ích mất quá lâu/);
    assert.equal(downloadButton(mounted).props.disabled, false);
    await act(async () => token.resolve("late-token"));
    assert.equal(fetched, false);
  } finally { if (mounted) await act(async () => mounted.unmount()); globalThis.fetch = originalFetch; globalThis.setTimeout = originalTimer; }
});
