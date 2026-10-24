# Taobao pause live release

Released October 16, 2026 (Asia/Bangkok) through PR #43: https://github.com/vuongc4298/vct-connect/pull/43.

Main merge: `cbe9f40b384af09107e003b093a5b6a8be7dca98`. PR CI `38865089518`, main CI `38866037195`, and Azure deployment `38867058152` succeeded. Local implementation/correction commits: `08d999b056b30dae9d0c9393187d7d1fb4916a1f` and `9c10d19`; isolated release commits: `d1f088d45240e4a2b040d3a8aeef88042974e842` and `949b506ffe81234820345d9faaeaca35e9e2280f`.

Live web revision: `vct-connect-dev-web--0000047`. Image: `vctconnectp6zsuuvnenn5a.azurecr.io/vct-web@sha256:d7efdc2ef25305ee566c4acd31c91dbbfab980a76eaa7e8a8152b2e826301da9`.

Live API revision: `vct-connect-dev-api--0000056`. Image: `vctconnectp6zsuuvnenn5a.azurecr.io/vct-backend@sha256:63b2737df26cc130a31e65eab9c15f49a3464b49ef7899d1db3c9d559ec87a0c`.

New Taobao URL submissions, HTML imports and browser captures are paused before quota, evidence or queue admission. Web guidance offers 1688 and Alibaba. Extension 0.7.1 shows a localized Taobao pause notice without a capture action. Existing reports, guest previews, history, watchlists, saved-result restoration and already queued processing remain compatible. Retained offline Taobao adapters support historical evidence and future restoration.

CI passed 1186 backend tests (32 environment-gated skips) and 181 frontend tests, plus typecheck/build, client/archive secret scan, protected extension download in the actual image, sandboxed Chromium, PostgreSQL browser provenance/replay and Azure template validation. The first PR run exposed six integration fixtures that still submitted new Taobao work; corrected fixtures now assert rejection without database/queue/quota writes and seed pre-pause work to retain worker and ownership coverage. Local targeted checks passed 192 tests; PostgreSQL execution was verified in CI because local Docker was unavailable.

After deployment completed, the live homepage returned 200; its client bundle retained 1688/Alibaba guidance and omitted Taobao capture instructions. Anonymous extension download returned 401 with private/no-store behavior and no attachment. Live guest Taobao product and shop submissions both returned 422 with an explicit pause message. Those checks accepted no analyses and made no model calls. The deployment's ingress and synthetic guest-fixture health checks also passed.

The actual packaged extension 0.7.1 passed isolated authentication/download verification, archive CRCs, six-file manifest, stable extension identity and live origin checks. A real signed-in Clerk download was not exercised this turn; local desktop/mobile browser and ZIP-saving checks used fixture authentication. End-user check: refresh the live app, sign in, open **Tiện ích & hướng dẫn**, download the ZIP, replace the installed extension folder contents, and reload it in `chrome://extensions` or `brave://extensions`. Taobao should show the pause notice; 1688/Alibaba should retain their guided capture flow.

Unrelated dirty initiative documents and local sample files were preserved. No product changes deferred.
