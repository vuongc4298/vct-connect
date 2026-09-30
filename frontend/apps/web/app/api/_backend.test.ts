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

test("trusted guest key replaces browser supplied identity headers", async () => {
  const originalFetch = globalThis.fetch;
  let sentHeaders: Headers | undefined;
  globalThis.fetch = async (_input, init) => {
    sentHeaders = new Headers(init?.headers);
    return Response.json({ id: "guest-id", status: "QUEUED" }, { status: 202 });
  };
  try {
    const request = new Request("http://localhost/api/v1/guest-analyses", {
      method: "POST",
      headers: {
        Authorization: "Bearer customer-token",
        "x-vct-guest-key": "attacker-supplied",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ source_url: "https://detail.1688.com/offer/123456789012.html" }),
    });
    const response = await proxyBackend(request, "/api/v1/guest-analyses", "a".repeat(64));
    assert.equal(response.status, 202);
    assert.equal(sentHeaders?.get("x-vct-guest-key"), "a".repeat(64));
    assert.equal(sentHeaders?.get("authorization"), null);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("HTML import proxy preserves bytes, authorization, and enforces its size cap", async () => {
  const originalFetch = globalThis.fetch;
  let sent: { headers: Headers; body: string } | undefined;
  globalThis.fetch = async (_input, init) => {
    sent = { headers: new Headers(init?.headers), body: await new Response(init?.body).text() };
    return Response.json({ id: "uploaded", status: "COMPLETED" }, { status: 201 });
  };
  try {
    const path = "/api/v1/analyses/import?source_url=https%3A%2F%2Fdetail.1688.com%2Foffer%2F996518024136.html";
    const imported = await proxyBackend(new Request(`http://localhost${path}`, {
      method: "POST", headers: { authorization: "Bearer upload-token", "content-type": "text/html" },
      body: "<html>Dress</html>",
    }), path);
    assert.equal(imported.status, 201);
    assert.equal(sent?.headers.get("authorization"), "Bearer upload-token");
    assert.equal(sent?.body, "<html>Dress</html>");
    const oversized = await proxyBackend(new Request(`http://localhost${path}`, {
      method: "POST", headers: { "content-type": "text/html" }, body: "x".repeat(2_000_001),
    }), path);
    assert.equal(oversized.status, 413);
    const barePath = "/api/v1/analyses/import";
    const bareOversized = await proxyBackend(new Request(`http://localhost${barePath}`, {
      method: "POST", headers: { "content-type": "text/html" }, body: "x".repeat(2_000_001),
    }), barePath);
    assert.equal(bareOversized.status, 413);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
