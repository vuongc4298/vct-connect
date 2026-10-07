import assert from "node:assert/strict";
import test from "node:test";

import { ApiError, getAccountState, getAnalysis, getAnalysisHistory, getGuestAnalysis, getGuestPreview, importSavedPage, submitAnalysis, submitGuestAnalysis } from "./index";

test("saved page import sends the file with bearer authorization and rejects oversized files", async () => {
  const originalFetch = globalThis.fetch;
  let sent: { url: string; headers: Headers; body: BodyInit | null | undefined } | undefined;
  globalThis.fetch = async (input, init) => {
    sent = { url: String(input), headers: new Headers(init?.headers), body: init?.body };
    return Response.json({ id: "uploaded", status: "COMPLETED" }, { status: 201 });
  };
  try {
    const file = new File(["<html></html>"], "offer.html", { type: "text/html" });
    const result = await importSavedPage(
      "https://detail.1688.com/offer/996518024136.html", file,
      { getToken: async () => "upload-token" },
    );
    assert.equal(result.status, "COMPLETED");
    assert.match(sent?.url ?? "", /^\/api\/v1\/analyses\/import\?source_url=/);
    assert.equal(sent?.headers.get("Authorization"), "Bearer upload-token");
    assert.equal(sent?.headers.get("Content-Type"), "text/html");
    assert.equal(sent?.body, file);
    await assert.rejects(
      importSavedPage("https://detail.1688.com/offer/996518024136.html",
        new File([new Uint8Array(2_000_001)], "large.html"), { getToken: async () => "upload-token" }),
      (error: unknown) => error instanceof ApiError && error.status === 413,
    );
    await assert.rejects(
      importSavedPage("https://detail.1688.com/offer/996518024136.html",
        new File(["not an HTML page"], "image.jpg", { type: "image/jpeg" }),
        { getToken: async () => "upload-token" }),
      (error: unknown) => error instanceof ApiError && error.status === 415,
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});


test("adds a fresh bearer token to submission and polling requests", async () => {
  const originalFetch = globalThis.fetch;
  const requests: Array<{ url: string; headers: Headers }> = [];
  let tokenCalls = 0;
  globalThis.fetch = async (input, init) => {
    requests.push({ url: String(input), headers: new Headers(init?.headers) });
    const body = init?.method === "POST"
      ? { id: "00000000-0000-0000-0000-000000000001", status: "QUEUED" }
      : {
          id: "00000000-0000-0000-0000-000000000001",
          source_url: "https://detail.1688.com/offer/123456789012.html",
          status: "QUEUED",
          created_at: "2026-09-28T00:00:00Z",
          completed_at: null,
          result: null,
        };
    return new Response(JSON.stringify(body), {
      status: init?.method === "POST" ? 202 : 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const auth = {
      getToken: async () => {
        tokenCalls += 1;
        return "session-token";
      },
    };
    const submitted = await submitAnalysis(
      { source_url: "https://detail.1688.com/offer/123456789012.html" },
      auth,
    );
    await getAnalysis(submitted.id, auth);
  } finally {
    globalThis.fetch = originalFetch;
  }

  assert.equal(tokenCalls, 2);
  assert.deepEqual(requests.map(request => request.url), [
    "/api/v1/analyses",
    "/api/v1/analyses/00000000-0000-0000-0000-000000000001",
  ]);
  assert.deepEqual(
    requests.map(request => request.headers.get("Authorization")),
    ["Bearer session-token", "Bearer session-token"],
  );
});


test("account state requires a fresh bearer token and never sends guest credentials", async () => {
  const originalFetch = globalThis.fetch;
  let sent: { url: string; headers: Headers; credentials?: RequestCredentials } | undefined;
  globalThis.fetch = async (input, init) => {
    sent = { url: String(input), headers: new Headers(init?.headers), credentials: init?.credentials };
    return Response.json({
      user: { id: "user-id", email: "owner@example.test", role: "CUSTOMER" },
      plan: "FREE",
      trial: { active: false, starts_at: null, expires_at: null, status: null },
      usage: {
        used: 2, limit: 20, remaining: 18, window_seconds: 86400,
        starts_at: "2026-10-07T00:00:00Z", resets_at: "2026-10-08T00:00:00Z",
      },
    });
  };
  try {
    const state = await getAccountState({ getToken: async () => "account-token" });
    assert.equal(state.plan, "FREE");
    assert.equal(state.usage.remaining, 18);
  } finally {
    globalThis.fetch = originalFetch;
  }
  assert.equal(sent?.url, "/api/v1/me");
  assert.equal(sent?.headers.get("Authorization"), "Bearer account-token");
  assert.equal(sent?.headers.get("x-vct-guest-key"), null);
  assert.equal(sent?.credentials, undefined);
});


test("analysis history uses bearer identity and returns the owner list", async () => {
  const originalFetch = globalThis.fetch;
  let sent: { url: string; headers: Headers } | undefined;
  globalThis.fetch = async (input, init) => {
    sent = { url: String(input), headers: new Headers(init?.headers) };
    return Response.json([{
      id: "history-1",
      source_url: "https://detail.1688.com/offer/123456789012.html",
      status: "COMPLETED",
      created_at: "2026-10-08T00:00:00Z",
      completed_at: "2026-10-08T00:01:00Z",
      mode: "ACCOUNT_PUBLIC",
      extraction_method: "PUBLIC_HTTP",
      scoring_version: "v0.1.0",
      supplier_name: "Fixture Supplier",
      platform: "1688",
      report_available: true,
      risk_label: "MODERATE",
      overall_risk: 58,
      confidence: 0.72,
      coverage: 0.75,
    }]);
  };
  try {
    const items = await getAnalysisHistory({ getToken: async () => "history-token" });
    assert.equal(items.length, 1);
    assert.equal(items[0]?.report_available, true);
  } finally {
    globalThis.fetch = originalFetch;
  }
  assert.equal(sent?.url, "/api/v1/analyses");
  assert.equal(sent?.headers.get("Authorization"), "Bearer history-token");
  assert.equal(sent?.headers.get("x-vct-guest-key"), null);
});

test("guest submission and polling use cookie credentials without bearer identity", async () => {
  const originalFetch = globalThis.fetch;
  const requests: Array<{ url: string; headers: Headers; credentials?: RequestCredentials }> = [];
  globalThis.fetch = async (input, init) => {
    requests.push({ url: String(input), headers: new Headers(init?.headers), credentials: init?.credentials });
    return Response.json({ id: "guest-id", status: "QUEUED" }, { status: init?.method === "POST" ? 202 : 200 });
  };
  try {
    await submitGuestAnalysis({ source_url: "https://detail.1688.com/offer/123456789012.html" });
    await getGuestAnalysis("guest-id");
    await getGuestPreview("guest-id");
  } finally {
    globalThis.fetch = originalFetch;
  }
  assert.deepEqual(requests.map(request => request.url), [
    "/api/v1/guest-analyses", "/api/v1/guest-analyses/guest-id", "/api/v1/guest-analyses/guest-id/preview",
  ]);
  assert.deepEqual(requests.map(request => request.credentials), ["same-origin", "same-origin", "same-origin"]);
  assert.ok(requests.every(request => !request.headers.has("Authorization")));
});

test("does not replay a failed submission", async () => {
  const originalFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return new Response(JSON.stringify({ detail: "Queue or database unavailable" }), {
      status: 503,
      headers: { "Content-Type": "application/json" },
    });
  };
  try {
    await assert.rejects(
      submitAnalysis({ source_url: "https://detail.1688.com/offer/123456789012.html" }),
      (error: unknown) => error instanceof ApiError && error.status === 503,
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
  assert.equal(calls, 1);
});

test("aborts a polling request at the client timeout", async () => {
  const originalFetch = globalThis.fetch;
  const originalSetTimeout = globalThis.setTimeout;
  globalThis.setTimeout = ((handler: TimerHandler) => {
    if (typeof handler === "function") queueMicrotask(() => handler());
    return 1;
  }) as typeof globalThis.setTimeout;
  globalThis.fetch = async (_input, init) => new Promise((_resolve, reject) => {
    init?.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
  });
  try {
    await assert.rejects(
      getAnalysis("00000000-0000-0000-0000-000000000001"),
      (error: unknown) => error instanceof ApiError && error.status === 408,
    );
  } finally {
    globalThis.fetch = originalFetch;
    globalThis.setTimeout = originalSetTimeout;
  }
});

test("timeout covers token acquisition and never starts a late submission", async () => {
  const originalFetch = globalThis.fetch;
  const originalSetTimeout = globalThis.setTimeout;
  let fetchCalls = 0;
  globalThis.setTimeout = ((handler: TimerHandler) => {
    if (typeof handler === "function") queueMicrotask(() => handler());
    return 1;
  }) as typeof globalThis.setTimeout;
  globalThis.fetch = async () => {
    fetchCalls += 1;
    throw new Error("fetch must not start after authentication times out");
  };
  try {
    await assert.rejects(
      submitAnalysis(
        { source_url: "https://detail.1688.com/offer/123456789012.html" },
        { getToken: () => new Promise(() => undefined) },
      ),
      (error: unknown) => error instanceof ApiError && error.status === 408,
    );
  } finally {
    globalThis.fetch = originalFetch;
    globalThis.setTimeout = originalSetTimeout;
  }
  assert.equal(fetchCalls, 0);
});

test("timeout remains active while the response body is parsed", async () => {
  const originalFetch = globalThis.fetch;
  const originalSetTimeout = globalThis.setTimeout;
  let expire: (() => void) | undefined;
  globalThis.setTimeout = ((handler: TimerHandler) => {
    if (typeof handler === "function") expire = () => handler();
    return 1;
  }) as typeof globalThis.setTimeout;
  globalThis.fetch = async () => ({
    ok: true,
    status: 200,
    json: () => {
      queueMicrotask(() => expire?.());
      return new Promise(() => undefined);
    },
  }) as Response;
  try {
    await assert.rejects(
      getAnalysis("00000000-0000-0000-0000-000000000001"),
      (error: unknown) => error instanceof ApiError && error.status === 408,
    );
  } finally {
    globalThis.fetch = originalFetch;
    globalThis.setTimeout = originalSetTimeout;
  }
});
