# Expanded 1688 extension evidence

Baseline: 1580ad614881861b9afeef52167c4ae4a9ed9063.

The operator's offer 1027322610455 completed, but its extension payload contained only supplier name, title and an unqualified coupon price. Its saved visible DOM also contains supplier metrics, platform membership tenure, business category, attributes, SKU price/stock, shipping, rating, approximate review count and a review snippet.

The operator explicitly approved proceeding after the BMAD renderer failed to acquire Jinja, without rerunning the renderer. This plan records implementation and validation directly.

Acceptance:
- Capture only bounded visible text from scoped supplier/product regions, excluding account globals, scripts, hidden nodes and recommendations.
- Retain both coupon and regular price with visible qualifications, plus SKU price and stock together.
- Preserve duplicate attribute labels with different values, approximate review counts, product review rating and supplier/dropshipping metric scopes.
- Keep platform tenure separate from founding age, shipping origin separate from company location, and SKU inventory separate from supplier capacity.
- Accept legacy payloads; validate expanded fields strictly and keep the serialized request within 16 KB.
- Verify the sanitized saved-page fixture in a real browser, backend normalization and existing frontend/API regression tests. A fixture pass does not replace a fresh Chrome recapture.

Implementation: extension capture, strict backend normalization, shared product contract, sanitized regression fixture and acceptance guide.

Status: implemented, verified and independently reviewed with no actionable findings.

Validation: 164 backend tests (normalization, strict API admission, legacy parity, merge and report projection), 129 frontend tests, TypeScript checking, extension production build and two PostgreSQL extension checks passed. Real-browser sanitized fixture passed 14 checks; its 3,851-byte capture retains all 41 attributes, four supplier metrics, nine dropshipping metrics, both qualified prices, SKU price/stock, shipping, rating and one review. The title/specification weight conflict is retained. The original historical parity fixture is unchanged; its test explicitly allows only the deliberate extractor version advance.

The updated API and approved continuous worker were restarted. Fresh Chrome extension recapture remains the operator's end-user acceptance step; existing reports were not rewritten.
