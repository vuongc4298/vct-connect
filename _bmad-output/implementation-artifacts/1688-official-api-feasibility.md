# 1688 official API feasibility (2026-09-30)

## Decision

Keep the saved-page import as the working fallback. Do not replace it with an official API call yet: 1688's public portal confirms a product API category and developer application flow, but the accessible public documentation does not establish that this project can request arbitrary offer, supplier, or review data with the required permissions.

The user reports that the 1688 partner registration route requires enterprise documents they do not have. Defer this route under that constraint and continue the user-invoked browser capture implementation. No official API credentials are needed for browser capture.

## Follow-up: user-supplied Alibaba.com token API

On 2026-09-30, the public [GenerateAccessToken reference](https://openapi.alibaba.com/doc/api.htm#/api?cid=4&path=/auth/token/create&methodType=GET/POST) and its documentation JSON were reachable. The documentation request returned HTTP 200 with `success: true`; this verifies access to documentation, not a successful token exchange.

- `/auth/token/create` requires `app_key`, `timestamp`, `sign_method`, `sign`, and `code`. Its SDK examples construct the client with an app key and app secret. The optional `access_token` parameter does not remove these requirements.
- The [Getting Started guide](https://openapi.alibaba.com/doc/doc.htm) describes Alibaba.com GGS developer registration, approved application categories, application credentials, and requested API permissions. It does not establish permission to read arbitrary 1688 offers or reviews.
- The reference supplies a placeholder `url` in its request examples, rather than a token gateway URL. Its public tool metadata points to a Lazada test console; that link is not evidence of 1688 API coverage.
- No token exchange was attempted with fabricated credentials or example authorization codes. Without an approved application's key, secret, and authorization code, a meaningful authenticated probe is unavailable. Keep the official adapter deferred; reconsider only if approved 1688 credentials and relevant API permissions become available.

## Verified from official sources

- The [1688 Open Platform](https://aop.alibaba.com/) lists API areas for products, members, and shops, plus a developer control center and business solutions for cross-border procurement and distribution. These are separate from the [Alibaba.com Global Open Platform](https://openapi.alibaba.com/doc/doc.htm), whose seller authorization and GGS APIs must not be assumed to cover 1688.
- An [official Alibaba developer document](https://developer.alibaba.com/docs/doc.htm?articleId=122128&docType=1&treeId=1) references `alibaba.fenxiao.productInfo.get` for a distribution product flag. This proves a product-info API exists in a specific business context; it does not establish general access or a review-text endpoint.
- The [1688 platform notice list](https://aop.alibaba.com/doc/notice.htm) includes a January 2026 legacy API retirement announcement. Any integration should be built against currently supported APIs after the application permission list is known.
- The [1688 API catalog](https://aop.alibaba.com/api/overview.htm?id=category_new) is available from the portal navigation, but its method details and permission scope were not exposed to the public viewer used for this check.

## Access and field check before implementation

1. In the 1688 Open Platform control center, register or open a VCT Connect developer application for the intended buyer or ISV scenario.
2. Record the application category, approval state, and the exact product, member/shop, and review or rating API method names shown as requestable. Note whether each requires supplier authorization, buyer authorization, or neither.
3. For one test offer, inspect response fields and permission errors. Map each returned value to the versioned SupplierData fields; keep unavailable fields in `missing_fields` rather than inferring them.
4. Confirm rate limits, storage/redistribution terms, and current API version before adding a backend credential or transport. Keep any app secret in local or Azure secret storage; only a publishable identifier belongs in documentation.

**Gate:** Implement an official adapter only if the approved application exposes enough product and supplier fields for a useful snapshot. Treat individual review text as unavailable until a documented, permitted method is demonstrated.
