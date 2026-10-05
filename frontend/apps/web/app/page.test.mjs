import assert from "node:assert/strict";
import test from "node:test";
import { createRequire } from "node:module";
import { mkdtemp, rm } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import React, { act } from "react";
import { JSDOM } from "jsdom";
import { build } from "esbuild";

for (const method of ["USER_UPLOAD", "PUBLIC_HTTP", "EXTENSION_DOM"]) {
for (const version of ["v1", "v2"]) {
test(`mounted buyer Page reopens ${method} ${version} report with its source, citations and extraction fallback`, async () => {
  const directory = dirname(fileURLToPath(import.meta.url));
  const temporary = await mkdtemp(join(resolve(directory, "../../../node_modules"), ".page-test-"));
  const bundle = join(temporary, "page.cjs");
  const id = "00000000-0000-0000-0000-000000000001";
  const source = "https://detail.1688.com/offer/996518024136.html";
  const dom = new JSDOM('<div id="root"></div>', { url: `http://localhost/?analysis=${id}` });
  const previous = new Map(["window", "document", "IS_REACT_ACT_ENVIRONMENT", "fetch"].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
  let root;
  try {
    // Bundle the real Page and its children with the Next.js JSX transform.
    // Only the external identity boundary is replaced; React hooks, DOM mounting,
    // Page effects, the API client and the report/evidence render paths remain real.
    await build({
      entryPoints: [join(directory, "page.tsx")], outfile: bundle, bundle: true,
      platform: "node", format: "cjs", jsx: "automatic",
      external: ["react", "react/*", "@vct/api-client"],
      plugins: [{ name: "test-identity", setup(builder) {
        builder.onResolve({ filter: /^@clerk\/nextjs$/ }, () => ({ path: "identity", namespace: "test-identity" }));
        builder.onLoad({ filter: /.*/, namespace: "test-identity" }, () => ({ loader: "js", contents: `
          import React from "react";
          const auth = {isLoaded: true, isSignedIn: true, userId: "owned-user", getToken: async () => "owned-token"};
          export const useAuth = () => auth;
          export const UserButton = () => React.createElement("span", null, "Owned account");
          export const SignInButton = ({children}) => children;
          export const SignUpButton = ({children}) => children;
        ` }));
      } }],
    });
    globalThis.window = dom.window;
    globalThis.document = dom.window.document;
    globalThis.IS_REACT_ACT_ENVIRONMENT = true;
    const requests = [];
    globalThis.fetch = async (url, init) => {
      requests.push(String(url));
      assert.equal(String(url), `/api/v1/analyses/${id}`);
      assert.equal(new Headers(init.headers).get("authorization"), "Bearer owned-token");
      return Response.json({
        id, source_url: source, status: "COMPLETED", actor_type: "CUSTOMER", attempt_count: 1,
        extraction_method: method, result: { source_url: source, extraction_status: "PARTIAL" },
        supplier_data: { supplier_name: "Owned supplier evidence", source_url: source, platform: "1688",
          products: [{ title: "Original source product" }], completeness: 0.25,
          completeness_denominator: ["supplier_name", "products", "rating", "reviews"], missing_fields: ["rating"],
          extracted_at: "2026-10-05T00:00:00Z", extraction_method: method, extractor_version: "test.v1" },
        raw_evidence: null, reviews: [],
        text_report: { state: "READY", failure_code: null, generated_at: "2026-10-05T01:00:00Z", report: {
          summary: "Báo cáo đã lưu cho người mua.",
          ...(version === "v2" ? { self_reported_confidence: { score: 0.65,
            basis: "Dữ liệu nguồn còn thiếu; cần xác minh độc lập.",
            provenance: "model_self_reported", calibration: "uncalibrated" } } : {}),
          findings: [{ kind: "observation", text: "Nguồn hiển thị sản phẩm.", citations: ["E1"] }],
          limitations: ["Chưa xác minh độc lập."], actions: ["Yêu cầu mẫu trước đặt cọc."],
          evidence: [{ id: "E1", path: "products", value: "中国商品" }], source_url: source,
          snapshot_id: "owned-snapshot", extracted_at: "2026-10-05T00:00:00Z", capture_freshness: "unknown",
          metadata: { model: "pinned", model_version: "v1", prompt_version: `vi-text.${version}`, schema_version: `text-report.${version}`,
            pipeline_version: "saved-evidence.v1", actual_cost_usd: null, cost_provenance: "unknown" },
        } },
      });
    };
    const Page = createRequire(import.meta.url)(bundle).default;
    const { createRoot } = await import("react-dom/client");
    const container = document.getElementById("root");
    root = createRoot(container);
    await act(async () => { root.render(React.createElement(Page)); });
    assert.ok(requests.length >= 1, "Page must poll the owned analysis itself");
    assert.equal(container.querySelector('#source-url').value, source);
    assert.ok(!container.querySelector('#url-help').textContent.includes('Dữ liệu fixture'));
    assert.ok(container.textContent.includes("Báo cáo đã lưu cho người mua."));
    const confidence = container.querySelector('[aria-label="Độ tin cậy do mô hình tự báo cáo"]');
    if (version === "v2") {
      assert.ok(confidence?.textContent.includes("chưa được hiệu chuẩn"));
      assert.ok(confidence?.textContent.includes("0.65 / 1"));
      assert.ok(confidence?.textContent.includes("Dữ liệu nguồn còn thiếu; cần xác minh độc lập."));
    } else assert.equal(confidence, null);
    const citation = container.querySelector(`a[href="#report-${id}-E1"]`);
    assert.equal(citation?.textContent, "E1");
    assert.ok(container.querySelector(`[id="report-${id}-E1"]`).textContent.includes("中国商品"));
    const fallback = container.querySelector('[aria-label="Bằng chứng trích xuất 1688"]');
    assert.ok(fallback?.textContent.includes("Owned supplier evidence"));
    assert.ok(fallback?.textContent.includes("Original source product"));
    assert.equal(container.querySelector('[aria-label="Báo cáo rủi ro minh hoạ"]'), null);
  } finally {
    if (root) await act(async () => { root.unmount(); });
    dom.window.close();
    for (const [key, descriptor] of previous) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else delete globalThis[key];
    }
    assert.equal(dirname(temporary), resolve(directory, "../../../node_modules"));
    await rm(temporary, { recursive: true, force: true });
  }
});
}
}
