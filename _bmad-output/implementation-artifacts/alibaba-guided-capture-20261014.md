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

Release status will be appended after CI and Azure verification.
