---
title: Highlight Alibaba storefront link during product guidance
type: bugfix
created: '2026-10-19'
status: built
route: oneshot
route_source: auto
baseline_revision: b4430475691e205c9335a40623df6e6c2485963e
review: quick
review_source: auto
lenses_ran: [quick]
context: []
---

<frozen-after-approval reason="User reports the wrong Alibaba product-to-shop highlight and requests correction">

## Intent

During Alibaba product-to-shop guidance, highlight the actual matching supplier storefront link above Company Overview, rather than a generic Company text match or the profile link. Preserve the later shop-to-company-profile guidance and the 1688 journey. If no visible matching storefront anchor exists, do not highlight a profile, foreign supplier or arbitrary label; retain the explicit correct storefront link in the guidance. Keep identity validation, collection state, extraction and algorithms unchanged. Deliver the corrected live extension package consistently with the current frontend-only release workflow.

</frozen-after-approval>

## Implementation Notes

`showCompanyGuidance` accepts company_profile.html in SHOP mode and separately finds any company-card leaf div/span matching Company/Co./Limited/LTD; Company Overview satisfies this loose regex. Saved Yiheng sample has an empty storefront/logo anchor, a storefront company-name anchor, company_profile and productlist links. Correct selection is visible, matching-shop root/index anchor with a readable label preferred over its empty logo sibling. Highlight that clickable anchor directly. Profile path remains reserved for FACTORY guidance. Add focused guidance regression checks, run capture/background compatibility and actual Chromium injection; publish extension 0.7.3 through a web-only image without backend changes. Unrelated initiative edits remain untouched. User's earlier frontend-only verification/redeploy preference is retained; no backend tests/migrations/model calls.

## Verification

Given Company Overview appears before the supplier-name anchor or contains a nested leaf span, SHOP guidance must highlight only the actual storefront anchor. Given mobile/desktop supplier URLs, a hidden/wrong-supplier link or only a profile link, matching and explicit fallback must remain correct. Dismissal and replacement must restore existing styles. FACTORY must still highlight the matching company profile; 1688 behavior must remain. Run focused frontend regression tests, typecheck/build/package check, actual browser fixture injection and live version verification. Native marketplace acceptance requires reloading the updated extension.

Focused frontend checks: 43 capture/background tests passed with no skips. Actual serialized Chromium injection passed named-mobile-storefront preference, Company Overview leaf/profile exclusion, hidden/foreign links, dismissal style restoration, next-stage profile highlighting and missing-storefront fallback. Browser evidence: `tmp/alibaba-shop-cue-fixed.png`; harness: `tmp/check-alibaba-shop-cue.cjs`. Build/typecheck/package and release checks continue. The raw saved product was inspected only for public card anchor labels/URLs; no scripts/private state entered fixtures or model calls.

## Review Triage Log

- Medium / patch: the quick reviewer reproduced an invisible named storefront winning because getClientRects remains nonempty for visibility:hidden/opacity:0. Added the same rendered-visibility/ancestor checks used by the existing Alibaba capture inside the serializable guidance function, restricted to Alibaba so 1688 behavior remains unchanged. Added hidden-self and transparent-parent regression cases; all 43 focused frontend checks passed again. Actual Chromium injection confirmed those links remain unhighlighted while the visible storefront wins. No functional work deferred.

Final production frontend build/typecheck and actual standalone branding/metadata/protected-package check passed with extension 0.7.3 and the same extension ID/live origin. The local build-live directory has the reviewed guidance. The client/archive secret scan and live web-only package publication remain the last release gates; no backend source, tests, migrations or scoring calls are involved.

### Live release complete

Final secret scan and independent review follow-up passed. PR46 merged as `d6bb5b287d2dba32e2691d9d5b214f68f3ba45f7`; frontend-only ACR build cm2 succeeded. Healthy web revision50 serves the actual inspected 0.7.3 ZIP. Live desktop/mobile frontend checks passed; API revision57, dispatcher revision105 and worker image/trigger remain unchanged. Full evidence and extension-reload instructions are in `alibaba-shop-cue-live-release-20261019.md`. No product changes remain deferred.
