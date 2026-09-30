# Sanitized Taobao parser fixtures

Derived locally from the user supplied authenticated browser captures listed in
`_bmad-output/initiative-vct-connect-year-one/epic-extraction/taobao-sample-audit.md`.
The original capture timestamp is unknown; these fixtures establish parsing only.

The product fixture retains the observed ICE wrapper and public item/seller,
price labels, approximate sale/review counts, two scoped review bodies and shop
metrics. The shop fixture retains the public g_config seller, exact `10年老店`
display text, distinct description/service/shipping evaluations and 20 displayed
product links and observed titles inside the audited shopProductShelfArea--
container. Raw source values are retained where normalization uses them.
All session/user/cart/navigation state, reviewer identities, source tokens,
images and external assets are removed. Full captures remain local and untracked.

Supported URL forms: HTTPS `item.taobao.com/item.htm` with one numeric `id`;
numeric `shop<ID>.taobao.com` or `shop<ID>.world.taobao.com` hosts with `/`,
`/index.htm` or `/category.htm`. Tracking is discarded; source identity is checked
against the main embedded model. Shop duration is displayed shop age, not legal
incorporation age; aggregates and shop metrics are not exact product ratings.
