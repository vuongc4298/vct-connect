# Extension guide live release

Released October 14, 2026 (Asia/Bangkok) through PR #42: https://github.com/vuongc4298/vct-connect/pull/42.

Main merge: `423405a4cf5cc9df49e5c16cac687094d2de320f`. PR CI `38561215254`, main CI `38562223005`, and Azure deployment `38563530763` succeeded. Local implementation commit: `27666ee5f34634a4c52506858c16aab9342225fc`; isolated release commit: `960e0db87a1b128266b23a759b6cc70c3db3c6b6`.

Live web revision: `vct-connect-dev-web--0000046`. Image: `vctconnectp6zsuuvnenn5a.azurecr.io/vct-web@sha256:53ad9eff4c18eb67e7c44095a5c749ae5d55ddb5c84904f30d3f1fc4e66306bb`.

The live home page serves successfully without URL/saved-HTML extraction forms or the fictional supplier preview. The client bundle contains the Vietnamese signed-in extension guide, platform steps and protected download path. Anonymous and invalid-token download requests both return 401 with private/no-store caching and no attachment.

183 frontend tests and 1186 backend tests passed in CI (32 backend tests skipped separately); required sandboxed-browser/PostgreSQL/image/infrastructure checks passed. Local typecheck/build, targeted deployment tests, client and decompressed ZIP secret scan passed. The actual web image passed an isolated loopback-auth download check, including archive CRCs, six files, live origin, icon/version and stable extension ID. Local headless desktop/mobile renders and actual Blob ZIP saving passed. No marketplace analysis or LLM request was submitted for this UI change.

Real signed-in Clerk download on live was not exercised because this turn had no browser session available. End-user check: refresh the live app, sign in, open Tiện ích & hướng dẫn, select Tải tiện ích, and follow the installation/capture guide. Existing report deep links, history and watchlist reopening are retained and covered by mounted interaction tests.

Review findings were corrected; no product changes deferred. Unrelated dirty initiative documents and local sample files were preserved.
