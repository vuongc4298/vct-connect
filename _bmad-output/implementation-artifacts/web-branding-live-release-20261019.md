# VCT web branding live release

Released October 19, 2026 through PR #45: https://github.com/vuongc4298/vct-connect/pull/45.

The generic V mark is replaced with the supplied VCT artwork on the landing page, desktop/tablet sidebar, loading view and mobile workspace header. The frontend uses navy/blue with orange accents, cool neutral surfaces and a matching square browser icon. Success, warning, danger and unknown states retain distinct meanings. Vietnamese copy, account/navigation behavior, report values and extension behavior are preserved.

The supplied JPEG was copied unchanged: 75,703 bytes, SHA-256 `0cb5596ff86872ef6249461f4f2dec368189612a64af302d25900c7b5eeb4449`. The square ICO embeds the existing matching extension icon without altering its pixels: 3,441 bytes, SHA-256 `3bbaa956693357e2f54c257de63ccce6d8b9e56554571ef5c9192f608579d6b9`. Docker runtime packaging now includes public assets.

Local implementation commit: `32292639c7db086690b8a56dfac2b59de816b1fc`. Isolated reviewed release head: `a12e2b1069327c90c8561fe4c218f1642e9be378`, based on prior live main `9fa7e8aeba57423d78f2a81fd12916140ba267bc`. Main merge: `d56ecc0f592bcb00d82ffaca9a4ab336cfd87def`. The released frontend files exactly matched the locally verified source.

## Frontend-only validation and deployment

The user explicitly requested frontend deployment testing only. The release commits used `[skip ci]` to suppress the existing full-stack CI/deployment pipeline, following [GitHub's documented workflow-skip mechanism](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs). No required repository protection was overridden; rules were empty and classic main protection was absent. No backend tests, migrations, extraction, scoring or model calls were run for this task.

Final production Next build with TypeScript validation passed. Client/archive/build-log secret scan and remote frontend build-log scan passed. The existing frontend deployment verifier was extended to check anonymous logo/icon byte equality and content types, page title/icon/theme metadata, then the protected extension ZIP, CRC/manifest and private-path boundaries. Its actual standalone-server check passed using isolated loopback authentication. The implementer also ran nine existing Page interaction checks.

Actual-component Chromium checks passed ten desktop/tablet/mobile scenarios at 1440, 900, 390 and 320px: landing/guide/report layouts, visible mobile logo/account/navigation, Alibaba guide switch, history-search focus, and low/high/unknown report colors. No page runtime errors or horizontal overflow; primary-button contrast is 8.15:1. Signed-in guide/report previews used fixture identity and synthetic report data, without changing production auth.

Azure Container Registry quick build `cm1` succeeded after 3m59s, building only `frontend/apps/web/Dockerfile` from the clean merged checkout. Published image: `vctconnectp6zsuuvnenn5a.azurecr.io/vct-web@sha256:88eba92a3191192a67469d3b56e2b77e68ae41473a8360d5cd631f216c3a4885`. Only the web Container App image was updated. Live revision `vct-connect-dev-web--0000049` is Healthy and Running.

## Live frontend proof

Anonymous production HTTP requests returned the exact source JPEG and ICO with status 200 and correct image MIME types. Native fresh-browser checks at 1440px and 390px rendered the supplied logo, blue primary actions, orange accent, correct browser icon/theme/title and sign-up control. Both had zero page runtime errors and no horizontal overflow. Anonymous extension download remained 401 with `private, no-store` and no attachment; the private ZIP path remained 404. No production sign-in or saved report was needed for these live checks.

Before/after deployment metadata matched for the API (`vct-connect-dev-api--0000057`), dispatcher (`vct-connect-dev-dispatcher--0000105`) and Event-triggered analysis Job. All retain backend image `vctconnectp6zsuuvnenn5a.azurecr.io/vct-backend@sha256:0fdcc08b5a8496d499ff76fcccb80ffe8d733d20c95a082e17ab0262cb2558b9`. The backend/algorithm and extension source are unchanged; the existing Alibaba fix and extension 0.7.2 are retained.

Evidence: `tmp/web-brand-live-checks.json`, `tmp/web-brand-backend-unchanged.json`, `tmp/web-brand-release-baseline.json`, `tmp/web-brand-preview-checks.json`, `tmp/web-brand-frontend-deployment-check.txt`, `tmp/web-brand-build-final.log`, `tmp/web-brand-acr-build.log`, and `tmp/web-brand-live-1440.png` / `tmp/web-brand-live-390.png`.

The user can refresh the existing live URL; use Ctrl+F5 if an old tab retains previous styling. No extension reinstall is needed. Unrelated initiative edits and the original supplied file were preserved. No functional work remains deferred.
