import assert from "node:assert/strict";
import test from "node:test";
import { extensionDownload } from "./_download";

test("download denies anonymous and malformed credentials without backend or archive access", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => { throw new Error("Must not call backend"); };
  try {
    const handler = extensionDownload(async () => { assert.fail("Must not read archive"); });
    for (const authorization of [undefined, "Basic token", "Bearer ", "Bearer a b"]) {
      const response = await handler(new Request("https://vct.example/api/v1/extension-download", { headers: authorization ? { authorization } : {} }));
      assert.equal(response.status, 401);
      assert.equal(response.headers.get("cache-control"), "private, no-store");
    }
  } finally { globalThis.fetch = original; }
});

test("download preserves authentication denial and fails closed on backend faults", async () => {
  const original = globalThis.fetch;
  try {
    const handler = extensionDownload(async () => { assert.fail("Must not read archive"); });
    for (const status of [401, 403, 404, 500, 503]) {
      globalThis.fetch = async () => Response.json({ detail: "Internal detail" }, { status });
      const response = await handler(new Request("https://vct.example/api/v1/extension-download", { headers: { authorization: "Bearer owner" } }));
      assert.equal(response.status, [401, 403].includes(status) ? status : 503);
      assert.doesNotMatch(await response.text(), /Internal detail/);
      assert.notEqual(response.headers.get("content-type"), "application/zip");
    }
    globalThis.fetch = async () => { throw new Error("Network unavailable"); };
    assert.equal((await handler(new Request("https://vct.example/api/v1/extension-download", { headers: { authorization: "Bearer owner" } }))).status, 503);
  } finally { globalThis.fetch = original; }
});

test("verified customer receives only the private archive with download headers", async () => {
  const original = globalThis.fetch;
  let reads = 0;
  globalThis.fetch = async (input, init) => {
    assert.match(String(input), /\/api\/v1\/me$/);
    assert.equal(new Headers(init?.headers).get("authorization"), "Bearer owner");
    assert.equal(new Headers(init?.headers).get("x-vct-guest-key"), null);
    return Response.json({ plan: "FREE" });
  };
  try {
    const bytes = Uint8Array.from([80, 75, 3, 4]);
    const request = new Request("https://vct.example/api/v1/extension-download?file=../../.env", { headers: { authorization: "Bearer owner", "x-vct-guest-key": "spoof" } });
    const response = await extensionDownload(async () => { reads++; return bytes; })(request);
    assert.equal(reads, 1); assert.equal(response.status, 200);
    assert.deepEqual(new Uint8Array(await response.arrayBuffer()), bytes);
    assert.equal(response.headers.get("content-type"), "application/zip");
    assert.equal(response.headers.get("content-disposition"), 'attachment; filename="vct-connect-extension.zip"');
    assert.equal(response.headers.get("cache-control"), "private, no-store");
    assert.equal(response.headers.get("x-content-type-options"), "nosniff");
    assert.equal(response.headers.get("content-length"), "4");
    const missing = await extensionDownload(async () => { throw new Error("ENOENT private path"); })(request);
    assert.equal(missing.status, 503); assert.doesNotMatch(await missing.text(), /private path/);
  } finally { globalThis.fetch = original; }
});
