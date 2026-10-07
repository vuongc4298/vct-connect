import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import type { AccountState } from "@vct/contracts";
import { AccountStateView } from "./account-state";

const free: AccountState = {
  user: { id: "user-1", email: "owner@example.test", role: "CUSTOMER" },
  plan: "FREE",
  trial: { active: false, starts_at: null, expires_at: null, status: null },
  usage: {
    used: 2, limit: 20, remaining: 18, window_seconds: 86400,
    starts_at: "2026-10-07T00:00:00Z", resets_at: "2026-10-08T00:00:00Z",
  },
};

test("account state renders free plan and real usage without inventing a trial", () => {
  const html = renderToStaticMarkup(<AccountStateView state={free} />);
  assert.match(html, /owner@example.test/);
  assert.match(html, />Free</);
  assert.match(html, /2/);
  assert.match(html, /20/);
  assert.match(html, /Còn 18 lượt/);
  assert.match(html, /không tự động thu phí/);
});

test("active MVP trial is visibly distinct from free", () => {
  const html = renderToStaticMarkup(<AccountStateView state={{
    ...free,
    plan: "MVP_TRIAL",
    trial: {
      active: true,
      starts_at: "2026-10-01T00:00:00Z",
      expires_at: "2026-10-31T00:00:00Z",
      status: "ACTIVE",
    },
  }} />);
  assert.match(html, /MVP Trial/);
  assert.match(html, /Đang hoạt động/);
  assert.match(html, /ACTIVE/);
  assert.doesNotMatch(html, />Free</);
});
