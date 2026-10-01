# Alibaba source audit — planning checkpoint

## Local inventory

The existing file at `sample webpages/Women's Autumn and Winter Retro Elegant Knitted Texture Fabric V Neck Slim Long Sleeve Long Dress - 阿里巴巴.html` is a **1688** capture. Both its canonical link and saved-from comment identify `https://detail.1688.com/offer/996518024136.html`. It is 851,376 UTF-8 bytes and is not evidence of Alibaba.com layout support. Existing raw samples and asset directories remain local and untracked.

## Anonymous public probes

On 2026-10-01, the parent made one anonymous, fixed-URL request to each candidate, using the existing checked-public-IP transport, no redirects, no credentials or cookies, the 2,000,000-byte cap, and 25-second deadline:

- Product: https://www.alibaba.com/product-detail/100-Cotton-180gsm-T-shirts-Men_1600147809763.html
- Supplier profile: https://dgxuandele.en.alibaba.com/company_profile.html

These are independent candidate samples, not a claimed product/supplier pair. Public search results helped locate their URLs; indexed excerpts do not establish current raw HTML layouts.

Both requests returned HTTP 200 HTML containing an access-challenge bootstrap, not usable evidence. Product response: 90,995 bytes; supplier response: 90,801 bytes. Both contain a `punish-component` element, `_config_`, `_custom_config_`, `_____tmd_____`, `baxia`, `captcha`, `x5sec`, and `AWSC`. Their visible body text is empty; no title, canonical link, or application/ld+json is present. Requested identity appears only in challenge routing/configuration and cannot authenticate supplier evidence.

Temporary raw responses are `tmp/alibaba-public-product.html` and `tmp/alibaba-public-supplier.html`; they must remain untracked. No JavaScript executed, assets loaded, CAPTCHA bypass attempted, or response/session material logged. A sanitized structural fixture may support challenge classification, but these responses cannot ground successful extraction fixtures.

## Supplied readable samples (2026-10-01)

Both top-level samples in `sample webpages/alibaba/` decode strictly as UTF-8 and fit the shared 2,000,000-byte response cap. Their asset folders are not extraction inputs; scripts and assets must not execute or load.

| Sample | Source identity | Bytes | Original SHA-256 |
| --- | --- | --- | --- |
| `100% Cotton 180gsm T Shirts Men High Quality Fashion Cheap Wholesale Custom Logo Blank T Shirt - Buy Product on Alibaba.com.html` | `https://www.alibaba.com/product-detail/100-Cotton-180gsm-T-shirts-Men_1600147809763.html` | 1,595,448 | `fc5c421bd12e80efd88a076f85f69d23519b6538bb3324308b7b00b9754b5f19` |
| `Company Profile.html` | `https://dgxuandele.en.alibaba.com/company_profile.html` | 373,175 | `28b84f211d516a1c3f66c1472a6daad9f57db0ba248aa7e3c010dacaae51f0ad` |

Source URLs above are recovered from browser saved-from comments for the audit. Neither page has a canonical link. Comments alone must never establish parser identity. Product JSON-LD supplies SKU `1600147809763` and brand `Lanxi Beauty Clothing Firm`, with public supplier links to `beautiy.en.alibaba.com`. The independent profile belongs to `dgxuandele`; these are separate supplier evidence examples, not a matched pair.

Product JSON-LD includes Product, ImageObject and BreadcrumbList; no aggregateRating or review bodies appear in Product JSON-LD. Active `detailData` contains product and supplier models alongside buyer/risk state. Profile `shopBizData` includes `pageModuleMap` and public subdomain binding alongside account/session state. Retain selected public fields only; never whole scripts or models. The profile `reviews` module has an async URL and title rather than accessible review bodies; do not fetch the async URL or manufacture reviews from counts.

## Scope

Story 2.4 adds public HTTP extraction. Alibaba saved-HTML import, extension capture, browser fallback, merge, scoring, media fetching and source credentials are outside its approved ticket intent. Existing 1688/Taobao import/capture paths must remain valid; Alibaba requests to those endpoints must be explicitly rejected until supported. The user-approved live Taobao shop capture deferral remains recorded.

## Parsing and public evidence map

Decode only the JSON object following `window.detailData =` or `window.shopBizData =` with `json.JSONDecoder.raw_decode`; do not execute assignments or retain their whole objects. The observed JSON is strict. Product root keys are `devData`, `globalData`, `hierarchy`, `metaData`, `nodeMap`. Supplier modules are an array: resolve `shopBizData.pageModuleMap` by exact `moduleName`, then read the selected `moduleData` fields; indices are not stable contracts.

Product property arrays `productBasicProperties`, `productKeyIndustryProperties`, `productOtherProperties` contain objects shaped `{attrName, attrNameId, attrValue, attrValueId}`. Retain names/values selected for evidence, rather than all IDs. The supplier own-category candidate selector matches 21 links in this sample.

Below `G` means `window.detailData.globalData`; `M(name)` means `window.shopBizData.pageModuleMap[moduleName == name].moduleData`.

| SupplierData field | Product sample | Independent supplier sample |
| --- | --- | --- |
| supplier_name | `G.seller.companyName`; DOM `.module_unifed_company_card` | `M(supplierPerformance).companyName`, `M(supplierActionBar).companyName`; DOM `.company-name` |
| company_information | Allowlist `G.seller.companyBusinessType`, `companyRegisterCountry`, `companyName` and public `.module_unifed_company_card` text: Trading Company, CN | `M(factoryCapability).cards[].items[]` has `fieldName`, `label`, `type`, optional `value`: employee_count 43, factory_area_sqm 2000, production_line_count 3, rd_team_count 3, qc_staff_count 3. `M(tradeCapacityMarkets).markets[]` has name/percentage; `.company-card` displays Custom Manufacturer and CN. |
| years_active | `G.seller.companyJoinYears = 6`; `localCompanyJoinYears = "6 yrs"` | `M(supplierPerformance).years.value = "6 yrs"`; use supplier's value, not `avgValue = "4 yrs"`. This is Alibaba tenure; exporting tenure is a different fact (8 years). |
| categories | `G.seo.breadCrumb.pathList[].hrefObject.name`: Apparel & Accessories, Men's Clothing, Men's T-Shirts; JSON-LD BreadcrumbList available | `section[data-module-name="productCategories"]` displays supplier product tabs; own-store `a.menu-link[href*="/productgrouplist-"]` names are category candidates. `M(productCategories).categories` is an empty list, so cannot supply evidence by itself. Avoid global navigation categories. |
| certifications | `.module_certification` empty; no certificate evidence there | `M(certifications).items[].name`, `.category`: RoHS, GCC (PRODUCT); ISO 1833, AZO, RoHS, CPSIA (INSPECTION_REPORT). Items also have certId, description, certificateValidityPeriod and photo fields. DOM `section[data-module-name="certifications"]` is empty, so structured public module is the available evidence; preserve category rather than treating every entry as identical certification. |
| products | `G.product.productId`, `.subject`, `.mediaItems`, observed attribute arrays; DOM `.product-title-container h1`, `.module_attribute`; JSON-LD Product `name`, `sku`, `image` | `section[data-module-name="productCategories"] a[href*="/product-detail/"]`: 16 bound product cards. Each has direct image wrapper then text wrapper containing title/price/MOQ. Titles include literal `&#39;` after DOM parsing and need deliberate entity normalization. No product-array evidence in empty structured categories. |
| price_information | `G.product.price.productRangePrices`: USD dollarPriceRangeLow 3.26, High 4.59; localized VND low 87059/high 122577 and `priceRangeText`. `price.currencyRule` provides localized pattern/rate; `price.unit = piece`; `G.product.moq = 2`; JSON-LD offers is USD price 3.26. DOM `.module_price` shows VND range/MOQ. | Prices/MOQ scoped to the 16 product cards, not a supplier-wide quote. Keep them attached to each product. |
| transaction_signals | `G.seller.tradeHalfYear` has ordAmt, ordAmt6m, ordCnt6m. Public company card fields: `detailData.nodeMap.module_unifed_company_card.privateData.onlinePerformance.fields[]` with title/value/desc; displays top buyers 9, revenue $10K–$20K, dispute rate 6.5%. Select fields explicitly; exclude traceInfo. | `M(supplierPerformance).onlineTransactions.amount = US $100K − $200K`, `.bigBuyerCount.amount = 35`, `.reorderRate.value = 43.9%`. `avgValue`, deltaPercent and tier describe comparisons, not observed supplier evidence. |
| rating | `G.review.storeReview.averageStar = 4.7`; alternatively `G.seller.supplierRatingReviews.averageStar` is a numeric string. Product rating is a separate scope. | `M(supplierActionBar).rating = "4.7"`; `M(supplierPerformance).reviews.value = "4.7"`, count 39. DOM own profile feedback `a.value[href*="/company_profile/feedback.html"]` displays 4.7/5. |
| reviews | **One public body** at `.product-review-list div.r-relative.r-whitespace-normal`: `Nice product`. This is within active product review content. Bind its source_url to this product; exclude sibling reviewer identity/country/date/avatar/product-order metadata. JSON-LD contains no reviews. | `M(reviews)` only title/asyncUrl and `section[data-module-name="reviews"]` is empty. Counts/aggregate ratings are not review bodies; reviews remains missing. Do not fetch async endpoint during this audit. |
| delivery_information | `G.trade.leadTimeInfo.ladderPeriodList[]` has minQuantity/maxQuantity/processPeriod: 1–50 => 7, 51–100 => 15, 101–500 => 25 days. `G.trade.logisticInfo` public packagingDesc/unitSize/unitWeight; `.module_attribute` Packaging and delivery. `G.seller.supplierOnTimeDeliveryRate = 100.0%` and responseTimeText ≤3h are supplier performance, not an order quote. | `M(supplierPerformance).shippingDays.value = 25.6d`, responseTime.value ≤2h; `.company-card` displays on-time dispatch 98.9%. Avoid `avgValue = 14.7d` and personalized/order shipping quotes. |
| activity_history | No bound chronological activity history observed. Aggregate 180/90/30-day metrics remain transaction/delivery signals. | No bound chronological activity history observed. Exporting tenure and New products/year 1100 are company capabilities, not an event history. |

## DOM, data disagreement, and exclusion caveats

- Product contains duplicate `id="review-layout"` and `id="key-attributes"`; prefer scoped selectors and deduplicate by evidence content. Generated `radix-:*` IDs and Tailwind utility classes are unstable. The review-body selector above is the exact observed candidate, but should be tested with near-miss reviewer/rating/order rows before relying on it.
- `.detail-review-item` is an aggregate/header component, **not** a review body. `.product-review-list` contains the one review. Product JSON aggregate product count is 2; store count 214; DOM store tab shows 239; seller supplierRatingReviews totalReviewOrderCount is 17. Preserve scope/source and prefer a documented precedence; do not invent a combined review count.
- Supplier modules are scoped by `section[data-module-name="supplierPerformance"]`, `factoryCapability`, `productCategories`, `certifications`, `reviews`; certifications/reviews are placeholders while their selected structured counterparts differ in availability. `#tradeCapacityMarkets`, `#productionCapacities` are observed section IDs.
- Top supplier card displays revenue US$200,000+ while supplierPerformance says US$100K–$200K. Treat separate period/definition/refresh evidence conservatively; no numerical reconciliation is justified by this capture.
- Price scopes differ: live public primary offer MOQ 2 versus a product attribute MOQ 10 Piece. Preserve primary offer MOQ and contextual attribute evidence; do not override based on a loose MOQ search.
- Exclude all buyer/login/account state, `G.buyer`, `G.extend` tracing/security material, `G.inventory` personalized shipping state, `G.risk`, unrelated globals, HEADER_DATA/one-tap login data, cart/forms, cookies, local-storage payloads, contact-person names/photos/gender, encrypted IDs, account IDs, tokens, `traceInfo`. Supplier `shopBizData.globalData` includes CSRF/chat/cna/session/account/buyer fields; extract only explicitly justified public binding fields, never copy the object. Likewise exclude `realTimeGlobalData` and `_globalConfig_`. Do not retain reviewer identity, avatars, countries, dates, order details or full review cards. Do not broaden review selection to surrounding reviewer metadata.
- Both real samples have no `punish-component`, `#nc-container`, login form or password input. Product still contains **nine `Sign in` occurrences** in navigation/scripts. A substring login detector would falsely return AUTH_REQUIRED. Require active login gate/challenge structure, title/status signals, or absent usable content. Standard sign-in links, JavaScript SDK names and certificate verified badges are not access gates.
- Earlier anonymous probes have empty visible body, no title/canonical/JSON-LD and real `<punish-component>` plus `_config_`/captcha/baxia challenge markers. Those are safe negative classifier fixtures only; queried target IDs in challenge config do not ground product/supplier evidence.
- Product HTML assets/helper documents are not required for these mapped fields; no iframe or other assets were loaded or executed. Supplier company overview is its own supported page type, not inferred from product HTML. Matching profile requires an explicit product-seller identity check before enrichment.

## Implementation decisions from the audit

- Admit HTTPS `www.alibaba.com/product-detail/<slug>_<positive numeric ID>.html` and `<store>.en.alibaba.com/company_profile.html` only, with bounded ASCII slug/subdomain/ID lengths, no credentials/ports/fragments/control characters. Remove tracking queries. No homepage, locale fetch, short-link or mobile forms are established by these captures. Metadata containing a locale-specific product URL may corroborate the same numeric ID without admitting its host as a fetch destination. Every public fetch/redirect preserves requested product ID or supplier subdomain; changed identity is terminal.
- Product identity requires agreement among observed main-product `productId`, JSON-LD Product SKU/offers URL, and optional canonical/og hints. Absent hints are allowed; any observed conflicting or malformed binding is rejected. Profile requires matching `shopBizData.globalData.esiteSubDomain.value`, with observed own-store source hints agreeing. Saved-from comments, unrelated product cards, breadcrumbs and challenge configuration cannot establish main-page identity. Product supplier identity uses its bound public profile hostname; a conflicting seller subDomain/profile URL fails. Use the same hostname-derived supplier key on product/profile evidence.
- Public model parsing accepts only audited active inline assignment wrappers, strict JSON, one unambiguous effective source model; reject duplicate/reassigned ambiguous models without executing scripts. Exclude template/noscript and visibly inactive DOM. Sparse identity-bound public evidence is PARTIAL; missing binding or unusable changed layout produces fixed PARSE_FAILED.
- Raw retention is an explicit path allowlist plus original response-byte hash and provenance. Selected JSON values remain source values. Every retained normalized value must trace to a selected raw value. No entire global, pageModuleMap, privateData object, review card or script is retained. JSONB safety checks apply to retained values and keys.
- Document primary scalar precedence: product name/company/tenure/offer prices from the main `detailData` model; JSON-LD corroborates identity. Store aggregate rating/count from `G.review.storeReview`, never product/DOM/seller counts mixed into one aggregate. Profile rating/count from `M(supplierPerformance).reviews`, with action-bar corroboration retained as scoped display evidence when useful. Keep the source, label and scope for differing metrics; do not reconcile them.
- Normalize supplier tenure separately from legal age. Supplier/company/price/transaction/delivery values remain source claims. Render selected company, tenure, product, price, rating, scoped transaction/delivery/certificate evidence and accessible review text in the shared web evidence panel. Extend typed display containers where required; preserve the 12-field denominator. Certificate entries retain their PRODUCT versus INSPECTION_REPORT category in selected raw evidence and labeled normalized strings. Profile product prices/MOQ stay attached to their product, not supplier-wide price coverage.
- Sanitized positive fixtures preserve both observed structures and public field shapes while stripping account/security/tracking/media/contact/reviewer metadata; keep independent identities and one product review body. Separate negative fixtures cover challenge bootstrap, harmless sign-in navigation, conflicting identity, ambiguous assignments, inactive/unrelated content, malformed retained JSON and missing fields. Compare extraction against original local files without committing their sensitive contents.

## Implementation verification (2026-10-01)

The implemented public adapter was compared directly against both original files
and the sanitized fixtures. Normalized evidence agrees apart from extraction
timestamp: the product is PARTIAL at 10/12 fields (one review body), and the
independent profile is PARTIAL at 9/12 fields (16 product cards; no accessible
review bodies or supplier-wide quote). The original hashes match the inventory.

The saved Product offers URL is protocol-relative on `indonesian.alibaba.com`
and ends in a hyphen followed by the product ID. It is corroborating metadata
only; admission/fetch remain limited to the approved `www.alibaba.com` form.
The product's public `homeUrl` points to the same store's `index.html` with
navigation queries; it is checked as a supplier hint and omitted from raw
retention. Mobile company-card links are excluded as fetch/evidence sources.
The profile action-bar rating is numerically encoded in the supplied JSON and
retains a separate display scope from the performance-module aggregate.

Two anonymous requests through the new adapter at 15:37 UTC returned
`BLOCKED / ACCESS_CHALLENGE`, with no snapshots. No script, asset, async review,
credential or session collection was performed. Local transport outcomes do not
substitute for the deployed smoke required after review and release approval.
