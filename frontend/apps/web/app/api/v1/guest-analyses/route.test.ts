import assert from "node:assert/strict";
import test from "node:test";
import { NextRequest } from "next/server";

import { POST } from "./route";
import { GET } from "./[analysisId]/route";
import { GET as PREVIEW_GET } from "./[analysisId]/preview/route";

test("guest route issues an opaque HttpOnly cookie and forwards only its key", async () => {
  const originalFetch = globalThis.fetch;
  let forwarded: Headers | undefined;
  globalThis.fetch = async (_input, init) => {
    forwarded = new Headers(init?.headers);
    return Response.json({ id: "guest-id", status: "QUEUED" }, { status: 202 });
  };
  try {
    const response = await POST(new NextRequest("https://example.org/api/v1/guest-analyses", {
      method: "POST",
      headers: { "x-vct-guest-key": "browser-spoof", "Content-Type": "application/json" },
      body: JSON.stringify({ source_url: "https://detail.1688.com/offer/123456789012.html" }),
    }));
    assert.equal(response.status, 202);
    const cookie = response.headers.get("set-cookie") ?? "";
    assert.match(cookie, /^vct_guest=[0-9a-f]{64};/);
    assert.match(cookie, /HttpOnly/);
    assert.match(cookie, /SameSite=Lax/);
    assert.match(cookie, /Secure/);
    assert.equal(forwarded?.get("x-vct-guest-key"), cookie.match(/^vct_guest=([0-9a-f]{64})/)?.[1]);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("guest status without a cookie never contacts the backend", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => { throw new Error("unexpected backend call"); };
  try {
    const response = await GET(
      new NextRequest("https://example.org/api/v1/guest-analyses/guest-id"),
      { params: Promise.resolve({ analysisId: "guest-id" }) },
    );
    assert.equal(response.status, 404);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("guest status forwards the valid cookie key and preserves the private response", async () => {
  const originalFetch = globalThis.fetch;
  const key = "b".repeat(64);
  let forwarded: Headers | undefined;
  let forwardedUrl = "";
  globalThis.fetch = async (input, init) => {
    forwardedUrl = String(input);
    forwarded = new Headers(init?.headers);
    return Response.json({ id: "guest-id", status: "COMPLETED" }, { status: 200 });
  };
  try {
    const response = await GET(
      new NextRequest("https://example.org/api/v1/guest-analyses/guest-id", {
        headers: { Cookie: `vct_guest=${key}`, "x-vct-guest-key": "browser-spoof" },
      }),
      { params: Promise.resolve({ analysisId: "guest-id" }) },
    );
    assert.equal(forwardedUrl, "http://127.0.0.1:8000/api/v1/guest-analyses/guest-id");
    assert.equal(forwarded?.get("x-vct-guest-key"), key);
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("cache-control"), "private, no-store");
    assert.deepEqual(await response.json(), { id: "guest-id", status: "COMPLETED" });
  } finally {
    globalThis.fetch = originalFetch;
  }
});


test("guest preview route requires the cookie and forwards only the opaque guest key", async () => {
  const originalFetch = globalThis.fetch;
  const key = "c".repeat(64);
  let forwarded: Headers | undefined;
  let forwardedUrl = "";
  globalThis.fetch = async (input, init) => {
    forwardedUrl = String(input);
    forwarded = new Headers(init?.headers);
    return Response.json({ schema_version: "guest-preview.v1", confidence: 0.5, coverage: 0.4 }, { status: 200 });
  };
  try {
    const denied = await PREVIEW_GET(
      new NextRequest("https://example.org/api/v1/guest-analyses/guest-id/preview"),
      { params: Promise.resolve({ analysisId: "guest-id" }) },
    );
    assert.equal(denied.status, 404);
    const response = await PREVIEW_GET(
      new NextRequest("https://example.org/api/v1/guest-analyses/guest-id/preview", {
        headers: { Cookie: `vct_guest=${key}`, "x-vct-guest-key": "browser-spoof" },
      }),
      { params: Promise.resolve({ analysisId: "guest-id" }) },
    );
    assert.equal(forwardedUrl, "http://127.0.0.1:8000/api/v1/guest-analyses/guest-id/preview");
    assert.equal(forwarded?.get("x-vct-guest-key"), key);
    assert.equal(response.headers.get("cache-control"), "private, no-store");
  } finally {
    globalThis.fetch = originalFetch;
  }
});
