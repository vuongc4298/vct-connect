import assert from "node:assert/strict";
import test from "node:test";
import { proxyBackend } from "./_backend";
import { OPTIONS as captureOptions } from "./v1/analyses/capture/route";
import { OPTIONS as statusOptions } from "./v1/analyses/[analysisId]/route";

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

test("extension capture proxy caps JSON and allows only its stable origin", async () => {
  const originalFetch = globalThis.fetch;
  const origin = "chrome-extension://klggcepemjjbphjclpiabgpfgdbgiljj";
  let forwarded: { authorization: string | null; body: string } | undefined;
  globalThis.fetch = async (_input, init) => {
    forwarded = { authorization: new Headers(init?.headers).get("authorization"),
      body: await new Response(init?.body).text() };
    return Response.json({ id: "captured", status: "COMPLETED" }, { status: 201 });
  };
  try {
    const path = "/api/v1/analyses/capture";
    const body = JSON.stringify({ source_url: "https://detail.1688.com/offer/996518024136.html" });
    const response = await proxyBackend(new Request(`http://localhost${path}`, {
      method: "POST", headers: { origin, authorization: "Bearer extension-token",
        "content-type": "application/json" }, body,
    }), path);
    assert.equal(response.status, 201);
    assert.equal(response.headers.get("access-control-allow-origin"), origin);
    assert.deepEqual(forwarded, { authorization: "Bearer extension-token", body });
    const preflight = await captureOptions(new Request(`http://localhost${path}`, {
      method: "OPTIONS", headers: { origin },
    }));
    assert.equal(preflight.status, 204);
    assert.equal(preflight.headers.get("access-control-allow-origin"), origin);
    const statusPreflight = await statusOptions(new Request("http://localhost/api/v1/analyses/any-id", {
      method: "OPTIONS", headers: { origin, "access-control-request-headers": "authorization" },
    }));
    assert.equal(statusPreflight.status, 204);
    assert.equal(statusPreflight.headers.get("access-control-allow-origin"), origin);
    assert.match(statusPreflight.headers.get("access-control-allow-headers") ?? "", /authorization/);
    const foreign = await captureOptions(new Request(`http://localhost${path}`, {
      method: "OPTIONS", headers: { origin: "https://evil.example" },
    }));
    assert.equal(foreign.status, 403);
    const oversized = await proxyBackend(new Request(`http://localhost${path}`, {
      method: "POST", headers: { origin, "content-type": "application/json" }, body: "x".repeat(16_385),
    }), path);
    assert.equal(oversized.status, 413);
    assert.equal(oversized.headers.get("access-control-allow-origin"), origin);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
