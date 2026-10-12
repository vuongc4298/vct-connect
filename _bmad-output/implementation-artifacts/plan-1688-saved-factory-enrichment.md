# Linked saved 1688 supplier enrichment

Baseline: 3abe99e. Continuation of approved extraction remediation and the operator's BMAD renderer-failure waiver.

Acceptance: use the supplied product/shop/factory HTMLs offline; verify product canonical, scoped supplier shop link, shop's own credit-page link and nonconflicting canonical, factory shop backlink and factory member canonical. Preserve captured product/review evidence. Extract only scoped factory capability fields and showroom description. Retain unknown certification/activity fields. Do not execute source scripts or fetch the browser-blocked shop via another mechanism.

Implemented bounded offline parser and trusted-operator dry-run/import CLI. New imports use normal customer quota/admission, immutable snapshot and worker assessment/reporting paths. Provenance includes base snapshot ID/hash, profile/shop hashes and source URLs; saved-page age remains unknown. Report has separate factory-profile evidence with a platform-claim disclaimer. Static shop markup omitted a factory href, so the operator-provided factory URL is validated rather than claimed as automatically discovered.

Actual fields: establishment 2025-07-14; completed age 1 on 2026-10-11; employees 11–50; annual turnover below 500,000 (displayed Chinese claim); custom MOQ 2,000; private-label MOQ 5,000; no foreign-trade-order support; processing modes; no VAT invoices. Description includes wholesale/distribution and individual household. Recommended suppliers' certificates and unexpanded annual-report links are excluded.

Live first enrichment exposed an unrelated aggregation inconsistency: high source-field completeness could produce LOW with six unknown risk dimensions. Assessment coverage is now bounded by configured weight of dimensions with usable scored signals; uploaded pages receive no known-freshness credit. Insufficient assessments suppress the overall aggregate score while retaining dimension evidence. Pure scoring weights and thresholds remain unchanged. Old persisted reports are not rewritten.

Verification: real saved-file dry run retained ten reviews and reduced missing source fields to certifications/activity_history. Corrected analysis d0bc536b-5e16-4bd2-a794-2b3ba79a20f7 completed on worker attempt 2 with real YEScale/DeepSeek, INSUFFICIENT_INFORMATION, no overall score, confidence .4406 and risk coverage .15. Browser verified the report, source age warning, ten reviews, profile/age evidence and remaining missing fields. Screenshot: tmp/factory-enriched-report.png. Earlier diagnostic analysis 4d63b74f-1fdc-4572-9410-1cd543afa632 retains its pre-correction result and must not be treated as the current acceptance report.

Validation: 926 backend tests passed / 142 environment-dependent tests skipped; seven PostgreSQL worker/report/replay tests passed. Independent quick review found one shop-identity issue; fixed with scoped identity and conflicting-canonical checks plus adversarial regressions. Follow-up review found no actionable issues. API/web remain running; approved continuous worker restarted with these changes.

Status: offline operator enrichment implemented and verified. Automatic live linked-page traversal, ordinary web multi-page upload, paginated reviews and review media/vision remain unimplemented.
