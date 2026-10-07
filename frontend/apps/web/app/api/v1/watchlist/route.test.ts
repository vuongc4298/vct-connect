import assert from "node:assert/strict";
import test from "node:test";

import { GET } from "./route";
import { POST, DELETE } from "./[id]/route";

test("watchlist proxies bearer auth and remains private", async () => {
  const originalFetch = globalThis.fetch;
  const calls: Array<{ url: string; method: string; headers: Headers }> = [];
  globalThis.fetch = async (input, init) => {
    calls.push({ url: String(input), method: init?.method ?? "GET", headers: new Headers(init?.headers) });
    return Response.json(init?.method === "DELETE" ? { removed: true } : [], { status: 200 });
  };
  try {
    const headers = { Authorization: "Bearer watch-token", "x-vct-guest-key": "spoofed" };
    const list = await GET(new Request("https://example.org/api/v1/watchlist", { headers }));
    const added = await POST(
      new Request("https://example.org/api/v1/watchlist/analysis-id", { method: "POST", headers }),
      { params: Promise.resolve({ id: "analysis-id" }) },
    );
    const removed = await DELETE(
      new Request("https://example.org/api/v1/watchlist/entry-id", { method: "DELETE", headers }),
      { params: Promise.resolve({ id: "entry-id" }) },
    );
    assert.deepEqual(calls.map(call => [call.method, call.url]), [
      ["GET", "http://127.0.0.1:8000/api/v1/watchlist"],
      ["POST", "http://127.0.0.1:8000/api/v1/watchlist/analysis-id"],
      ["DELETE", "http://127.0.0.1:8000/api/v1/watchlist/entry-id"],
    ]);
    assert.ok(calls.every(call => call.headers.get("authorization") === "Bearer watch-token"));
    assert.ok(calls.every(call => !call.headers.has("x-vct-guest-key")));
    assert.equal(list.headers.get("cache-control"), "private, no-store");
    assert.equal(added.headers.get("cache-control"), "private, no-store");
    assert.equal(removed.headers.get("cache-control"), "private, no-store");
  } finally {
    globalThis.fetch = originalFetch;
  }
});
