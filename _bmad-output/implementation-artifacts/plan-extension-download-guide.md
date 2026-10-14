---
title: Extension download and usage guide as the web entry point
created: 2026-10-14
status: built
route: full
route_source: auto
authorization: User requested implementation; existing session authorizes live releases.
baseline_revision: ff658849a188814e078793285a5abb68b66a7720
review: thorough
review_source: auto
lenses_ran: [blind-hunter, edge-case-hunter, verification-gap, intent-alignment]
---

## Frozen intent

Replace the web page's redundant URL extraction path with an extension download and usage guide available after login. Extension capture becomes the normal way to start an analysis. Keep existing report deep links, history, watchlist and account views working. Keep the current live address and existing extension identity. This is one extension-first entry feature; backend extraction APIs remain available to existing clients.

## Decisions and scope

Remove both the guest URL submission form and the signed-in URL/saved-HTML submission form from the main page. Guests can sign in or create an account, but cannot download the extension. After login, the default workspace is “Tiện ích & hướng dẫn.” Visiting a valid `?analysis=<UUID>` opens its report and retains authenticated polling. History and watchlist continue to reopen reports, including refreshing the same analysis ID.

The guide uses Vietnamese, the existing green visual style, clear installation steps and platform-specific capture steps. Each section has at most five numbered or bulleted items. Instructions cover extracting the ZIP, developer mode and loading the unpacked folder, pinning the extension, using the same signed-in account, and capturing visible evidence. For 1688 explain product → shop → factory; for Alibaba explain product → supplier → Company overview; for Taobao explain supported active-page capture. Explain closing CAPTCHA overlays with X only when content is already visible, completing collection within 30 minutes, and viewing reports/history. Do not promise access to content hidden behind a challenge.

Generate a private extension ZIP during the web build using the existing extension builder, deployed HTTPS origin and public Clerk key. Keep version 0.7.0, stable extension ID and existing icon. Package only the six runtime files, excluding environment files and server secrets. Use a deterministic ZIP writer with Node built-ins so Docker builds do not need another runtime or an undeclared dependency. Serve the private archive through a dynamic Node route after verifying the request's Bearer token with the existing `/api/v1/me` backend check. This matches the current customer workspace authorization. The client downloads with a fresh Clerk token and displays Vietnamese recovery messages on failure.

## Code map

- `frontend/apps/web/app/page.tsx`: workspace routing, sign-in state, report polling, guest landing, sidebar and main view.
- `frontend/apps/web/app/extension-guide.tsx`, `extension-guide.test.tsx`, `page.interaction.test.mjs`, `globals.css`: guide content, interactive download and layout coverage.
- `frontend/apps/web/app/api/_backend.ts`: existing authenticated backend proxy; reuse without changing its other callers.
- `frontend/apps/web/app/api/v1/extension-download/route.ts` and `route.test.ts`: protected archive endpoint and authorization/failure tests.
- `frontend/apps/extension/build.mjs`: existing extension build and fixed manifest identity; reuse its source build.
- New extension packaging script and ZIP helper/tests under `frontend/apps/extension/`: deterministic, explicit-file packaging.
- `frontend/apps/web/package.json`, `next.config.ts`, `Dockerfile`, `.gitignore`, `.dockerignore`: generation, standalone tracing/runtime copy and ignored generated assets; permit the icon through Docker exclusions.
- `frontend/package.json`, `scripts/scan_frontend_secrets.py`, `END_USER_TEST.md`: run new tests, include generated extension assets in secret checking, and document the actual end-user path.

## Tasks

1. Implement the private package generation and authenticated download route. Enforce a deployed HTTPS origin, fixed filename and no public asset fallback. Include it in standalone/Docker builds and exclude generated artifacts from source control.
2. Implement the Vietnamese guide and download interaction. Prevent repeated concurrent downloads; clean up temporary Blob URLs and links; handle missing/expired tokens and backend/network failures without exposing server details. Prevent a download from completing for a stale signed-in user.
3. Replace web form entry points with guide navigation. Remove their submission state, handlers, guest polling and unreachable demo components. Preserve report loading, extraction-only fallback, same-ID reopening, account ownership resets and real history/watchlist operations. Make the source URL read-only report evidence.
4. Add focused authorization, archive, navigation and download tests to the existing test command. Update end-user instructions. Check type safety, the production build and bundled artifact contents.
5. Review the change for authorization and packaging leaks, report regressions and guide usability. Fix supported findings. Stop implementation at verified local files: the parent handles staging, workflow reviews, commits and live release after this build workflow completes. Preserve unrelated dirty files; do not run remote operations during implementation.

## Acceptance criteria

- Given a signed-out visitor, when opening the home page, then sign-in/signup are available and neither an extraction form nor extension download is available; an unauthenticated download API request returns 401.
- Given a signed-in customer without a report query, when the workspace loads, then the extension guide is the default view and the download succeeds only with verified authorization.
- Given the downloaded ZIP, when unpacked and loaded in Chrome/Brave, then the manifest, icon, six runtime files, current version, stable identity and live web origin are intact.
- Given a user following a platform's instructions, when completing capture, then the guide explains each required source page and how to reach the report, with no section exceeding five steps.
- Given a saved report URL or history/watchlist selection, when opened or reopened, then the same authenticated report polling and evidence fallback work without a web submission form.
- Given invalid authentication, missing archive, unavailable backend or failed download, when requesting the extension, then no archive is disclosed and the UI offers a localized retry message.

## Input/output matrix and verification

Anonymous/invalid token → 401 or upstream authorization failure, no file read. Valid customer token + package → private ZIP attachment. Valid token + missing package → 503. Backend outage → 503, no archive. Default login → guide. Valid report UUID → report view. Guide navigation → clear report query. Same-ID reopen → fresh report fetch. Account switch → clear scoped state and cancel stale download.

Run the complete frontend test suite, workspace typecheck, production web build, archive extraction/CRC and deterministic-content tests, and frontend secret scan. Inspect the guide at desktop/mobile widths and test the authenticated download in a local route harness. CI must build the actual Docker asset and run repository-required checks. Verify live deployment revision, anonymous download denial, signed-in guide and downloadable ZIP where the existing browser session permits. Preserve unrelated dirty files. User's implementation request authorizes reversible work; no additional planning checkpoint is needed.

## Review triage log

| Lens / finding | Verdict and evidence | Resolution |
| --- | --- | --- |
| Blind 1: stalled download | Medium: pending token/fetch had no deadline, so the button could remain disabled. | Patch: 45-second client deadline and 15-second backend verification timeout; retry test. |
| Blind 2: origin build contract | Low: current default is the correct live origin, but Docker could not accept an override. | Patch: explicit build argument and workflow forwarding. |
| Blind 3: obsolete recovery | Medium: report recovery still advertised removed HTML import and said Alibaba capture was unsupported. | Patch: actual supported extension recovery, updated assertions. |
| Blind 4: update instructions | Low: replacing files without Reload can leave the old loaded extension running. | Patch: permanent folder, replace contents, Reload; align manual guide. |
| Blind 5: desktop requirement | Low: mobile Chrome/Brave do not support the specified installation path. | Patch: label desktop browsers beside download. |
| Blind 6: partial completion controls | Low: guide described completion but omitted actual popup labels. | Patch: name both available completion controls. |
| Blind 7: site access prompt | Low: first capture requests optional host permission. | Patch: explain allowing access and retrying after denial. |
| Blind 8: saved upload retry | Low: interrupted upload has a specific retained-evidence control. | Patch: name Gửi lại dữ liệu đã lưu. |
| Blind 9: installation count assertion | Low: at-most-five would pass with zero steps. | Patch: exactly five installation steps and four per platform. |
| Blind 10: independent ZIP reader | Medium verification gap: custom parser did not validate CRC or packaged artifact. | Patch: actual standalone/image endpoint check uses Python ZipFile.testzip and six-file manifest assertions; local check passed. |
| Edge: stalled response | Medium: same missing deadline as Blind 1. | Same timeout patch. |
| Verification: workspace account switch | Medium verification gap: standalone unmount did not test Page keying by owner. | Patch: mounted account switch asserts old token never downloads and new account can start. |
| Intent: broader readings and verification surfaces | False as a defect: user explicitly scoped frontend; guide is a workspace page, and the removed upload shared the retired URL form. Backend APIs remain intentionally compatible. | Browser desktop/mobile and actual ZIP saving checked separately; actual standalone authorization/package check added to CI. A fresh marketplace collection from the downloaded artifact remains operator acceptance, not claimed as executed. |

No product changes deferred. The implementer delegate failed due to account usage limits; the parent completed implementation. Reviewers initially received ephemeral sandbox-temp paths; reviews were repeated against a persistent workspace copy. Four reviews completed; the intent lens ran after a concurrency slot became available.

## Verified local result

183 frontend tests passed; workspace typecheck and production web build passed. Targeted deployment tests: 17 passed. Secret scan includes the private archive and decompressed entries. Headless desktop/mobile guide and real ZIP saving passed against local fixture authentication. The actual Next standalone server passed anonymous/invalid denial, verified ZIP bytes, Python CRC/manifest checks and public-path denial. The same server/archive check is registered in image CI. No fresh supplier/model analysis was submitted for this UI change.
