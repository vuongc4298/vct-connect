import assert from "node:assert/strict";
import test from "node:test";
import { proxyBackend } from "./_backend";

test("backend outage returns a 503 JSON response", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => { throw new Error("connection failed"); };
  try {
    const response = await proxyBackend(
      new Request("http://localhost/api/v1/analyses", { method: "GET" }),
      "/api/v1/analyses",
    );
    assert.equal(response.status, 503);
    assert.match(response.headers.get("content-type") ?? "", /application\/json/);
    assert.deepEqual(await response.json(), {
      detail: "Backend unavailable. Check the FastAPI process and API_INTERNAL_ORIGIN.",
    });
  } finally {
    globalThis.fetch = originalFetch;
  }
});
