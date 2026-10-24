# Alibaba guided supplier capture — 2026-10-14

Implemented the 1688-style guided flow for the supplied Yiheng offer 1601711788226: product → supplier storefront → Company overview. The desktop and mobile supplier hostnames share a canonical desktop identity. All captures retain one owner, analysis ID and quota reservation, with the existing 30-minute deadline and response-loss recovery.

## Evidence verified from supplied pages

An offline Chromium harness loads inert copies of the three downloaded pages and their local CSS. Original scripts, account forms and source state are removed before loading. The actual injected functions capture rendered product and company regions, and the backend independently validates the resulting inert HTML.

The sample preserves 3 product review bodies, rating 4.8 and product total 78; 24 attributes; four VND price tiers and MOQ 1; 15 company claims including establishment year 2026, factory size 1,000–3,000 square meters, four production lines, a combined manufacturer/trading declaration, OEM options and payment terms. Product review scope is distinct from supplier review totals. Employee/certificate placeholders remain unknown. Platform tenure is not treated as completed registered operating years.

The factory assessment considers profile, area, manufacturing/trading declaration and production lines. Its classification remains UNCERTAIN at confidence 0.2853 for the supplied sample, because the source declares both manufacturing and trading. Low-confidence prior bars remain hidden. Advertised Alibaba order protections are sourced to the product and marked with unverified eligibility/fulfillment.

## Boundaries and compatibility

Only selected visible text is downloaded/uploaded; scripts, globals, module-data, contact/account widgets, review buyer identities and embedded media are excluded. The LLM continues to receive structured evidence and bounded relevant excerpts. Supplier host, company name, product title, prices, attributes, reviews and company claims are checked against captured HTML. Foreign links, conflicting claims and private state are rejected. Large Unicode review samples yield to the assessment input byte budget with an explicit retained-count disclosure.

The bundle discriminator defaults to 1688. Its serialization deliberately omits the default discriminator/new optional profile name, preserving the existing 1688 reservation digests across rollout. Standalone Alibaba saved-HTML uploads are unchanged; guided extension upload supplies all captured sources.

## Validation and release

Extension 0.7.0 includes Vietnamese Company overview labels and guidance. Local TypeScript, 173 frontend checks, production build and 35 new Alibaba backend cases pass. Existing 1688 browser/bundle tests pass. The local full backend run stalled in Windows and was interrupted; PostgreSQL transaction/worker acceptance is reserved for CI because Docker is unavailable locally. Native signed-in Alibaba/Chrome acceptance remains the five-step operator flow in END_USER_TEST.md.

First CI run verified begin/finish replay, one quota admission and one persisted owned report. It failed only on the new test's expected generic company evidence ID; the actual report uses specific identity-source IDs. The assertion was corrected to require the sourced production-line value, and product rating/count were additionally checked against captured HTML before the final CI run.

## Verified live release

PR #41 merged as `4d59cd5bb3a23b7c87e960685a93074b1e09beb6`. PR CI `38535333931`, main CI `38541308785` and Azure deployment `38542499073` passed. Final CI totals: 1,185 backend checks passed / 32 skipped, 173 frontend checks, and the separate Chromium suites passed (78 sandbox and 12 PostgreSQL cases). The collection test verifies begin/finish replay, one quota admission, one persisted owned report and its sourced production-line evidence.

Active ready revisions: API `--0000054`, web `--0000045`, dispatcher `--0000099`. API, dispatcher and Event analysis worker use backend digest `95464865ab7f2d2054cb3249171cfcd2e532edd7263a1eb3ce28575b5ee0f072`; web uses digest `33bfa82f2d8b397558f66152ca1cdef4043b3ac222fa4f4b60b06fbe1ff89906`. The workflow passed migrations, activation, ingress and guest-fixture checks.

The read-only deployed-image execution `vct-connect-dev-analysis-4c3cpas` succeeded. Its assertions confirm Alibaba platform/extractor, all three parsed HTML pages, three review bodies / product total 78, 24 attributes, 15 company claims, four production lines and five factory evidence records. It reads only the public committed fixture, with no database access, report changes or LLM calls. The live homepage and served JS asset also confirm the updated Vietnamese Alibaba capture guidance (JavaScript Unicode/hex escapes decoded for inspection).

The live extension folder and `tmp/vct-connect-live-extension-0.7.0.zip` match, target the existing HTTPS origin and retain the icon/extension identity. Reload 0.7.0 and start a fresh capture using the five-step guide; native signed-in Alibaba/Chrome navigation, downloads and session-sync acceptance remain the operator check.
