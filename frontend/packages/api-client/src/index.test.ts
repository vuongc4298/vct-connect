import assert from "node:assert/strict";
import test from "node:test";

import { ApiError, getAnalysis, submitAnalysis } from "./index";


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
