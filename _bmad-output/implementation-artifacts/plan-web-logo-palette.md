---
title: Apply supplied VCT web logo and palette
type: feature
ticket: ''
created: '2026-10-19'
status: built
baseline_revision: b68f47ae2f7f5acbaccd0cb64a9c5b3d6fe3c926
route: full
route_source: auto
review: thorough
review_source: auto
lenses_ran: [intent-alignment, blind-hunter, edge-case-hunter, verification-gap]
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="User explicitly requested implementation and frontend-only deployment validation">

## Intent

Replace the generic V web mark with the user's supplied VCT logo and make the web application's palette consistent with its blue/orange identity. Deliver the updated frontend to the existing live URL and validate the frontend deployment only, as expressly requested.

## Boundaries & Constraints

Always preserve the supplied artwork, Vietnamese text, navigation, account/download authentication, responsive layouts, report meaning and accessibility. Use deep navy/royal blue for brand/navigation/actions and orange as an accent; retain meaningful success/warning/error distinctions and adequate contrast. Keep one canonical publicly served logo and supply a matching browser icon. Preserve unrelated initiative edits and the user's original image.

Never change backend code, algorithms, extraction, scoring, database, extension behavior or production workflow configuration for this branding task. Do not execute backend tests, migrations, full-stack deployment or live supplier/model calls. Release only a web image; leave API/worker image digests and configuration intact. No domain change or generated replacement artwork.

## I/O & Edge-Case Matrix

| Scenario | Input/state | Expected result |
| --- | --- | --- |
| Public landing | Signed out, desktop/mobile | Supplied logo is readable, blue/orange palette, sign-in and sign-up remain usable |
| Workspace | Signed-in guide, history/account or report | Shared logo/palette; active navigation, download controls, charts and evidence remain readable |
| Compact navigation | Tablet sidebar or narrow mobile viewport | Brand fits without clipping artwork or causing horizontal overflow |
| Asset packaging | Standalone web image and public live URL | JPEG logo and browser icon load correctly with appropriate content type |
| Semantic states | Success, unknown, warning, danger | Meaning remains distinguishable from brand accents and retains text labels |

</frozen-after-approval>

## Code Map

- Source artwork: `frontend/apps/web/app/icon/075d774f-1b9b-4181-8207-14d85f53ed04.jpg` (1536×1024, 75,703 bytes), inspected visually. Preserve original file; copy unchanged to a descriptive public asset. CSS can frame its whitespace without altering the artwork.
- `frontend/apps/web/app/page.tsx`: shared `Brand()` currently renders a generic V; used on landing/sidebar/loading. Replace only brand presentation; retain page effects, auth and navigation.
- `frontend/apps/web/app/style.css`: roughly 700 lines; green tokens and many hard-coded green-tinted neutrals span landing, shell, guide, history and report. Update consistently, preferably using explicit brand tokens and semantic status colors. Existing tablet rule hides the last span in sidebar Brand; account for the new markup.
- `frontend/apps/web/app/layout.tsx`: Vietnamese ClerkProvider and CSS import. Add web metadata/logo icon and matching browser theme color; no auth changes.
- `frontend/apps/web/public/vct-logo.jpg`: new canonical unchanged supplied JPEG. `frontend/apps/web/Dockerfile` currently omits public assets from runtime, so include public directory in standalone image.
- Existing frontend deployment verification: production Next build, `scripts/scan_frontend_secrets.py`, `scripts/verify_web_extension_download.py` with isolated loopback auth. Browser preview harnesses can render actual React components with fixture auth; do not modify production auth to preview.
- `.github/workflows/ci.yml` and `deploy-dev.yml` always test/deploy backend. Leave these intact. Parent will clearly mark this release to skip that full-stack automation, record the explicitly requested frontend checks, build an immutable web-only ACR image from an isolated clean checkout and update only the Azure web app. Do not bypass any required repository protection.

## Tasks & Acceptance

- [x] Replace the generic mark, add original public artwork, metadata and Docker runtime asset inclusion.
- [x] Apply coherent blue/orange branding throughout the web CSS with responsive brand framing and distinct semantic states.
- [x] Parent performs frontend typecheck/build, client/archive scan, actual standalone deployment checks and desktop/mobile visual checks using real components; no backend suite.
- [x] Review presentation and deployment packaging, fix actionable issues, isolate release diff, publish the web image and verify live rendering/asset/theme/auth boundaries and unchanged backend images.

Given the supplied artwork, when the web application loads at desktop/tablet/mobile sizes, then its generic V is replaced by a recognizable complete VCT logo and its blue/orange visual identity is consistent. Given the web image is deployed, when clients open the existing live URL, then branding assets and browser icon load, and backend/worker deployment identifiers remain unchanged. Given report risk/unknown states, then their semantic meaning remains clear and their saved values remain unchanged.

## Implementation Notes

Baseline local HEAD: `b68f47ae2f7f5acbaccd0cb64a9c5b3d6fe3c926`; prior live main merge: `9fa7e8aeba57423d78f2a81fd12916140ba267bc`. Two unrelated tracked initiative documents are dirty and will be preserved. User's explicit implement/redeploy instruction supplies authorization; no redundant planning approval is requested. Palette changes are mechanical but span enough CSS declarations to use the full route. Parent owns all remote operations.

## Plan Change Log

## Review Triage Log

All four lenses completed against the shared workspace mirror of the technical diff. The first attempts could not access the parent sandbox's system-temp file; they were rerun against its identical workspace copy. No code-review result was inferred from those failed reads.

| Finding | Verdict / route | Evidence and decision |
| --- | --- | --- |
| Blind 1: good metric ring inherits brand blue | Low / patch | Verified default ring color becomes blue while good pills remain green; add the matching success ring rule. |
| Blind 2: history-search reset overrides generic focus | Medium / patch | The new focus rule loses to the existing outline reset; give the search container a visible focus-within indicator. |
| Blind 3: evidence-summary outer focus is clipped | False / rejected | Parent caller tracing found no JSX consumer of evidence-summary in the current web app; this is residual CSS, so the claimed live control is unreachable. The implementer was instructed to omit this patch. |
| Blind 4: rectangular full JPEG is weak at favicon sizes | Low / patch | New icon metadata reuses a large rectangular canvas; use a square ICO containing the existing matching VCT product icon, preserving its PNG unchanged. |
| Blind 5: failed-image visual fallback is weak | Low / rejected | VCT alt text remains accessible, Connect remains visible, and the deployment check will verify actual asset availability. A separate failed-network state would add behavior/guards to this reversible branding change. |
| Blind 6: mobile signed-in shell has no brand | Low / patch | Sidebar is hidden below 720px; a compact mobile brand can be added with a two-row header while retaining navigation/account controls. |
| Blind 7: original JPEG is larger than its display frame | Low / rejected | Actual asset is 75,703 bytes and reused/cacheable; no material frontend performance failure was demonstrated. Preserve the supplied source rather than add a derivative pipeline solely for this negligible finding. |
| Blind 8: repeated neutral colors lack semantic tokens | False / rejected | All references resolve and the repeated values currently agree; no named consumer diverges. Future design changes are hypothetical, not a verified inconsistency in this palette. |
| Blind 9: no persistent visual regression suite | Low / rejected | Temporary repeatable actual-component browser checks cover seven sizes/states and will expand for fixes. Literal CSS/markup snapshot tests are unnecessary for this reversible visual task; the material packaging gap gets a persistent frontend deployment assertion. |
| Edge: no findings | No patch | Lens traced the change and reported an empty finding list. |
| Verification: image guard does not fetch logo | Medium / patch | Existing protected-download test can pass without public COPY; extend its actual frontend HTTP assertions to check logo/icon bytes and metadata. |
| Intent: semantic colors remain | False / rejected | Blue/orange define the brand; success/warning/danger colors retain their established report meanings as required for a usable report. |
| Intent: binary diff cannot establish artwork equality/framing | Verification boundary | Supplied and public JPEG hashes match; actual browser previews and manual inspection establish complete framing. |
| Intent: diff does not establish live delivery/validation | Release gate | Parent performs web-only image rollout and live frontend checks before reporting deployment complete. No backend tests are authorized for this release. |

## Verification

Frontend-only scope: web TypeScript check; production build; existing frontend client/archive scan and protected-download standalone check; real browser desktop/mobile previews of landing, signed-in guide and representative report, including logo load, colors, overflow, focus and semantic states. No new tests for literal color/markup substitutions. Build one web image from committed release source; verify new healthy web revision and served branding, then record original/current API/analysis-worker image equality. Record clearly any native sign-in boundary and whether frontend checks used fixture authentication.

### Initial frontend deployment checks

Production Next build completed with TypeScript validation. Client/archive/build-log secret scan passed. The actual standalone frontend passed protected extension download checks with loopback fixture authentication. Real Chromium rendered the actual Page and FullReport components with fixture identity: landing at 1440/390px, guide at 1440/900/390px, report at 1440/390px, and unknown-state toggle. All seven views had no horizontal overflow or runtime errors, loaded the original logo where the shell shows branding, retained distinct success color, and provided visible keyboard focus. Primary-button contrast is 8.15:1. Manual screenshot inspection confirmed complete artwork, compact sidebar and mobile report legibility. Production live/asset checks remain pending. No backend tests or model calls were run.

### Reviewed final frontend verification

All actionable findings were patched and the unused evidence-summary finding was rejected after caller tracing. The final production build/typecheck and client/archive/build-log secret scan passed. Extended actual standalone frontend deployment check passed exact anonymous JPEG/ICO bytes and content types, title/icon/theme metadata, anonymous/invalid ZIP denial, verified ZIP CRC/manifest and private-path denial with isolated loopback auth. Final actual-component browser checks passed ten scenarios at 1440/900/390/320px, including mobile logo/account/navigation, guide switch, active history-search focus and green low-risk/red high-risk/striped unknown report states. No horizontal overflow or page runtime errors; primary-button contrast remains 8.15:1. Implementer also ran the nine existing Page interaction checks; no backend tests, migrations, extraction or model calls were run. Nothing functional was deferred. Native production rendering and deployment identifier checks remain release gates.

### Live release verified

PR #45 merged as `d56ecc0f592bcb00d82ffaca9a4ab336cfd87def`. Web-only ACR build `cm1` succeeded and image digest `sha256:88eba92a3191192a67469d3b56e2b77e68ae41473a8360d5cd631f216c3a4885` is running in healthy web revision 49. Live frontend HTTP/browser checks passed exact logo/icon delivery, metadata/palette, desktop/mobile rendering, anonymous download protection and private-path denial. API revision 57, dispatcher revision 105 and Event worker image remain identical to the pre-release baseline. No full-stack pipeline/backend tests were executed. Complete proof and native sign-in boundary are recorded in `web-branding-live-release-20261019.md`; all requested work is complete.
