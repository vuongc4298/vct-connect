import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import type { WatchlistEntry } from "@vct/contracts";
import { WatchlistView } from "./watchlist";

const item: WatchlistEntry = {
  id: "entry-1",
  created_at: "2026-10-08T00:00:00Z",
  supplier_id: "supplier-1",
  platform: "1688",
  platform_supplier_id: "seller-1",
  name: "Fixture Supplier",
  source_url: "https://detail.1688.com/offer/123456789012.html",
  analysis_id: "analysis-1",
  analysis_status: "COMPLETED",
  report_available: true,
  risk_label: "MODERATE",
  overall_risk: 58,
  confidence: 0.72,
  coverage: 0.75,
};

test("watchlist renders persisted supplier summary and report action", () => {
  const html = renderToStaticMarkup(<WatchlistView
    entries={[item]} loading={false} error="" removingId={null}
    onOpen={() => undefined} onRemove={() => undefined}
  />);
  assert.match(html, /Fixture Supplier/);
  assert.match(html, /58/);
  assert.match(html, /72%/);
  assert.match(html, /75%/);
  assert.match(html, /Mở báo cáo/);
});

test("watchlist empty state explains how to add a supplier", () => {
  const html = renderToStaticMarkup(<WatchlistView
    entries={[]} loading={false} error="" removingId={null}
    onOpen={() => undefined} onRemove={() => undefined}
  />);
  assert.match(html, /Watchlist đang trống/);
  assert.match(html, /Lưu vào Watchlist/);
});
