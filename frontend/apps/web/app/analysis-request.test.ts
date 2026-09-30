import assert from "node:assert/strict";
import test from "node:test";
import { getAnalysis } from "@vct/api-client";
import { submitSelectedAnalysis } from "./analysis-request";

test("selecting a saved file submits its bytes and polls the imported analysis", async () => {
  const originalFetch = globalThis.fetch;
  const calls: Array<{ url: string; method: string; body?: BodyInit | null }> = [];
  globalThis.fetch = async (input, init) => {
    calls.push({ url: String(input), method: init?.method ?? "GET", body: init?.body });
    return Response.json(init?.method === "POST"
      ? { id: "imported-id", status: "COMPLETED" }
      : { id: "imported-id", status: "COMPLETED", extraction_method: "USER_UPLOAD",
          result: { extraction_status: "PARTIAL" } },
    { status: init?.method === "POST" ? 201 : 200 });
  };
  try {
    const file = new File(["<html>saved offer</html>"], "saved.html");
    const auth = { getToken: async () => "customer-token" };
    const submitted = await submitSelectedAnalysis(
      "https://detail.1688.com/offer/996518024136.html", file, auth,
    );
    const polled = await getAnalysis(submitted.id, auth);
    assert.deepEqual(calls.map(call => [call.method, call.url.split("?")[0]]), [
      ["POST", "/api/v1/analyses/import"], ["GET", "/api/v1/analyses/imported-id"],
    ]);
    assert.equal(calls[0].body, file);
    assert.equal(polled.extraction_method, "USER_UPLOAD");
    assert.equal(polled.result && "extraction_status" in polled.result
      ? polled.result.extraction_status : null, "PARTIAL");
  } finally {
    globalThis.fetch = originalFetch;
  }
});
