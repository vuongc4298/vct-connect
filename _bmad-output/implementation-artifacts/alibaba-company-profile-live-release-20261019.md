# Alibaba Company profile capability-card release

Release requested by the user after a failing third guided Alibaba capture stage. PR #44: https://github.com/vuongc4298/vct-connect/pull/44. Merged October 19, 2026 as `9fa7e8aeba57423d78f2a81fd12916140ba267bc` from tested release head `ec93ef8e9084c972951b115f19d71557c586a00e`; local implementation commit `e8bc159`.

## Result

The failing Guangzhou Lianxian Company profile uses capability cards instead of the previous table layout. Its visible business type, production lines and floor space now become the same identity-checked company claims in selected evidence and cleaned HTML. The supplied layout captures Custom Manufacturer, two production lines and 5000 square metres. Backend normalization retains these facts and includes sourced manufacturing evidence. Legacy table profiles retain support.

Conflicting supplier identities, incomplete/challenge-only profiles, invalid measurements and changes between the two capture injections remain retryable. A valid product/store/profile finishes one collection with one quota reservation; a lost finish response replays the stored evidence. This change does not rewrite historical reports or solve CAPTCHA.

Extension version: **0.7.2**, stable extension ID `klggcepemjjbphjclpiabgpfgdbgiljj`. Existing permissions, icon and live origin are preserved. Local ignored `frontend/apps/extension/build-live` has been rebuilt for the live origin.

## Verification

PR CI `39185261201` succeeded: 1194 backend tests passed with 33 environment-gated skips, 198 frontend tests passed, typecheck/build/client-and-archive secret scan passed. The actual web image passed protected download, ZIP CRC/manifest and private-path checks with isolated authentication. Sandboxed network-denied Chromium passed 79 tests, including the new source-layout capture and changed-HTML rejection; PostgreSQL Chromium ownership/provenance checks passed 12 tests. The guided owned-report PostgreSQL test covers both company layouts.

Final local verification: 1059 backend tests passed with 168 environment-gated skips, 198 frontend tests passed, typecheck and production build passed. The new actual Chromium regression also passed locally. Offline actual injected functions captured the supplied saved page and retained the legacy Yiheng profile's 15 claims. Only sanitized public source-layout fixtures were committed; raw downloaded page/session state was excluded.

## Deployment evidence

Main CI `39190117930` and Azure deployment `39190842938` succeeded for the merged commit. Deployment completed its cookie-scoped guest fixture through the live queue at `2026-10-19T02:52:56Z`; ingress and web response checks passed. This synthetic health fixture made no supplier/model verification claim.

Live web revision `vct-connect-dev-web--0000048` and API revision `vct-connect-dev-api--0000057` are active, Healthy and Running. Web image: `vctconnectp6zsuuvnenn5a.azurecr.io/vct-web@sha256:79fcb90303b94b80446e02b6d1eb80a6ba022a95dfacfd58c4baf37cb7032669`. Backend image: `vctconnectp6zsuuvnenn5a.azurecr.io/vct-backend@sha256:0fdcc08b5a8496d499ff76fcccb80ffe8d733d20c95a082e17ab0262cb2558b9`. The analysis Job uses that backend image and Event triggering. Dispatcher revision `vct-connect-dev-dispatcher--0000105` is active and Healthy.

Read-only checks of the live web origin returned homepage 200, anonymous `/api/v1/me` 401, anonymous extension download 401 with `private, no-store` and no attachment, and private ZIP path 404. Read-only Node inspection inside the ready web revision verified the actual packaged extension is **0.7.2**, targets the production origin, and has ZIP SHA-256 `ab2c7a1d86c2606d9f4d877ad60d9235cd76676952540729e96f3295f063348f`. The first inspection hit Windows batch quoting, then an Azure console request-length limit; the shorter read-only inspector succeeded without modifying the container. Local evidence: `tmp/alibaba-profile-live-http.json`, `tmp/alibaba-profile-live-package.json`, `tmp/alibaba-profile-fix-main-ci.log` and `tmp/alibaba-profile-fix-deploy.log`.

## End-user acceptance

Sign in on the live app, open **Tiện ích & hướng dẫn**, download and extract the updated ZIP, replace the installed extension folder contents, and reload VCT Connect in `chrome://extensions` or `brave://extensions`. Confirm version **0.7.2** and start a fresh collection. Capture the product, save its supplier storefront, then save Company profile and analyze. Expect `product.html`, `shop.html` and `company.html` in the same analysis directory, followed by a report with the captured company evidence.

The native signed-in Alibaba navigation and actual Clerk-authenticated download remain operator acceptance checks; automated capture used the supplied source layout and fixture authentication. Existing pending collections can expire after 30 minutes. Unrelated dirty initiative documents and raw samples were preserved.
