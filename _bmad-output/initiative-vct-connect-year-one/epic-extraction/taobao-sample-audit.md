# Taobao sample audit — Story 2.3

## Sources and handling

The user supplied product `1076425861755` and shop `159450000`, with authenticated browser captures under `sample webpages/taobao`. Original capture time is unknown. These are parser samples, not proof of anonymous server access. Keep full captures and assets local and untracked; fixtures must retain only public source values needed for normalization and binding. Do not retain user, cart, messaging, navigation session state, response cookies or source tokens. Parse embedded JSON without executing JavaScript or loading assets.

- Product: `https://item.taobao.com/item.htm?id=1076425861755`
- Shop: `https://shop159450000.world.taobao.com/category.htm`
- Product file: `sample webpages/taobao/洁柔抽纸Face粉软柔韧100抽3层抽实惠亲肤细腻宝宝可用2元包邮-淘宝网.html` (472,468 bytes, declared UTF-8).
- Shop file: `sample webpages/taobao/首页-心相印维达生活馆-淘宝网.html` (722,085 bytes, declared GBK; decode with GB18030 and replacement for invalid bytes).

## URL scope and binding

Accept strict HTTPS `item.taobao.com/item.htm` with exactly one numeric `id`, retaining that ID and dropping tracking/SKU parameters. Reject duplicate/ambiguous IDs, credentials, ports, fragments and shorteners.

The supplied shop host is `shop159450000.world.taobao.com`; its embedded public `seller.pcShopUrl` is `//shop159450000.taobao.com`. Scope shop hosts to numeric `shop<ID>.world.taobao.com` and `shop<ID>.taobao.com`, with `/`, `/index.htm`, or `/category.htm`. Preserve supported host/path, remove tracking queries, and bind embedded `seller.shopId` to the numeric host ID. Same-shop redirects between these forms may be followed within the shared limit; a different shop, item, platform or foreign destination is terminal. Product redirects must retain the product identity. Never follow a login destination; classify only recognized exact login hosts/paths. Reject an explicit Tmall seller designation rather than mislabeling it as Taobao.

## Product layout

The main ICE bootstrap script contains `window.__ICE_APP_CONTEXT__` and a JSON object assigned to `var b =`, subsequently assigned to that global context. Verify the wrapper/assignment before parsing its JSON, then inspect `loaderData.home.data.res`. Require `loaderData.home.data.ssrItemId` and `res.item.itemId` to agree with the requested item when present. Do not scan arbitrary script IDs as binding evidence.

Observed public paths below are relative to that object:

| Source path or scoped DOM | Mapping / limitation |
| --- | --- |
| `item.itemId` | Must match the requested item; value `1076425861755` |
| `item.title` | Product title; DOM fallback class token begins `mainTitle--` |
| `seller.shopName`, `seller.shopId`, `seller.sellerId` | Display name `心相印维达生活馆`, shop `159450000`, seller `2895982467`; seller ID is platform supplier identity, not shop ID |
| `seller.sellerType` | Observed `C`; reject known Tmall designation when explicitly observed |
| `componentsVO.priceVO.price.priceText`, `extraPrice.priceText` | Observed listed `3.35` and discounted `2.01`; preserve labels/context, do not infer a universal purchasable price |
| `skuCore.sku2info.0.subPrice.priceText` | Observed `2.01起`; explicit starting-price text differs from selected-SKU price |
| `item.vagueSellCount` | `3万+`; preserve approximate display text instead of asserting exact sales count |
| `componentsVO.rateVO.totalCount`, `favorableRate` | Visible aggregate `2万+`, positive-review text scoped to the most recent three months; retain display text and verified context rather than an exact count |
| `[class^="Comment--"] [class^="content--"]` | Exactly two public Chinese review bodies. Retain text/source only, not reviewer handles or headers |
| Shop DOM token prefixes `shopName--`, `starNum--`, `storeLabelItem--` | Visible shop score `4.9`, VIP positive-review rate `97%`, average shipping `23小时`; distinguish shop metrics and time windows, not product rating |

Scope DOM fallbacks to verified product/shop containers. Avoid generic `content--` selection outside the review section. Only review bodies that exist in the capture become accessible reviews; aggregates do not imply all reviews were collected. Fields without verified values remain absent in the 12-field completeness denominator.

## Shop layout

The shop embeds a JSON object assigned to `window.g_config`. Select its public `seller` object only:

- `shopId`: `159450000`; `sellerId`: `2895982467`; `shopName`: `心相印维达生活馆`. Require `seller.pcShopUrl` to identify the same normalized shop when present.
- `shopDuration`: `10年老店`; retain original text, and map years only under a documented exact pattern.
- `tmall`: `false`; check this explicitly where available.
- `evaluates`: distinct description `4.8`, service `4.9`, shipping `4.9`; retain labels rather than silently averaging into an overall rating.
- Product cards have class token `shop-item-card` inside the observed `shopProductShelfArea--Z6GzvxkU` container, with actual `item.taobao.com/item.htm?id=...` links. Titles come from the card's `title--PtjUKgj2` node title attribute/text. Collect at most 20 displayed cards without fetching products; exclude cards outside this shelf. Product fields may be absent when unavailable.
- No verified company registration, certifications, categories or individual shop review text has been established by this audit.

## Public route observation

Cookie-free checked-public-IP HTTP probes of both canonical URLs returned HTTP 200 with approximately 5 KB of script content and `_____tmd_____` markers, without usable product/shop evidence. The existing 1688 classifier did not recognize those pages. The Taobao adapter must inspect the actual challenge script structure and add a precise classifier; a marker alone on an otherwise legitimate populated page is insufficient. No live successful extraction or Azure roundtrip is claimed.

The moved 1688 full capture is under `sample webpages/`; active tests use the committed sanitized fixture, so the move does not require a runtime code change.
