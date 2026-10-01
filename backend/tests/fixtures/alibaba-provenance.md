# Alibaba fixture provenance

Fixtures derive from the two approved UTF-8 local samples recorded in
`_bmad-output/initiative-vct-connect-year-one/epic-extraction/alibaba-sample-audit.md`.
They are independent pages: product 1600147809763 belongs to beautiy; the profile
belongs to dgxuandele. No enrichment or association joins them.

Original hashes: product `fc5c421bd12e80efd88a076f85f69d23519b6538bb3324308b7b00b9754b5f19`;
profile `28b84f211d516a1c3f66c1472a6daad9f57db0ba248aa7e3c010dacaae51f0ad`.

Sanitization preserves strict inline detailData/shopBizData JSON public field
shapes, selected module names, Product SKU/offer URL metadata, supplier category
navigation, 16 product cards and one accessible product review body. Assets,
account/security/session/tracking/contact/reviewer/order metadata are removed.
The profile retains no async review URL or fabricated review bodies. Original
samples and challenge responses remain untracked.

Direct comparison on 2026-10-01 produced identical normalized evidence except
the extraction timestamp: product PARTIAL, 10/12 fields; profile PARTIAL, 9/12.
The retained supplier key is the public profile hostname. Primary product scalar
fields use detailData; aggregate rating/count uses storeReview (214), while the
profile uses supplierPerformance.reviews (39). Supplier tenure is Alibaba tenure,
not legal age. Profile per-product prices/MOQ do not count as supplier pricing.
Certificates preserve PRODUCT versus INSPECTION_REPORT labels. Comparisons,
industry averages, and source claims of verification do not become verified facts.

`alibaba_access_challenge.html` is a structural negative fixture derived from the
observed anonymous HTTP 200 challenge: an empty public body, punish-component and
challenge bootstrap markers. Routing identifiers and all security/session values
are excluded. It cannot establish product or supplier identity.

Anonymous adapter probes on 2026-10-01 at 15:37 UTC returned
`BLOCKED / ACCESS_CHALLENGE` for both audited URLs, with no usable snapshots.
These are local public transport observations; deployed smoke remains a release
step after review and approval.
