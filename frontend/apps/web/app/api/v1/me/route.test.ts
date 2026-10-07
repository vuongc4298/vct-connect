import assert from "node:assert/strict";
import test from "node:test";

import { GET } from "./route";

test("me proxy forwards bearer authorization and remains private", async () => {
  const originalFetch = globalThis.fetch;
  let sentUrl = "";
  let sentHeaders: Headers | undefined;
  globalThis.fetch = async (input, init) => {
    sentUrl = String(input);
    sentHeaders = new Headers(init?.headers);
    return Response.json({ plan: "FREE" }, { status: 200 });
  };
  try {
    const response = await GET(new Request("https://example.org/api/v1/me", {
      headers: {
        Authorization: "Bearer account-token",
        "x-vct-guest-key": "spoofed-guest-key",
      },
    }));
    assert.equal(sentUrl, "http://127.0.0.1:8000/api/v1/me");
    assert.equal(sentHeaders?.get("authorization"), "Bearer account-token");
    assert.equal(sentHeaders?.get("x-vct-guest-key"), null);
    assert.equal(response.headers.get("cache-control"), "private, no-store");
  } finally {
    globalThis.fetch = originalFetch;
  }
});
