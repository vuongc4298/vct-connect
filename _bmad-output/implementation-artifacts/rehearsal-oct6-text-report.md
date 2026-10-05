# Oct 6 saved-evidence text report rehearsal

Date: 2026-10-05. Checkout: `tmp/oct6-text-report-worktree`.
The approved plan was read fully; its frontmatter context list is empty.
This is fake-provider integration verification, not live YEScale acceptance.

## Prepared evidence and journey

Use the retained Chinese HTML in
`backend/tests/fixtures/1688_offer_996518024136.html` with the canonical URL
`https://detail.1688.com/offer/996518024136.html`. The PostgreSQL rehearsal imports
it for an authenticated owner using the real extraction parser and Store. It
observes extraction COMPLETED with report QUEUED, then generates a deterministic
Vietnamese report with FakeProvider, polls READY, resolves every citation to a
stored evidence ID, and reopens the persisted report through a new Store.
Original extraction result, events, evidence and snapshot ID must remain equal.
Other-owner and guest reads of this full report return 404.

The frontend static rendering rehearsal verifies independent report progress,
continued polling after extraction completion, Vietnamese findings, observation
versus inference labels, citation anchors and inspectable source text,
limitations, pre-order actions, separate extraction/generation dates, unknown
freshness/cost and absence of computed risk/reliability scores. This does not
claim a manual authenticated browser rehearsal.

Fallbacks: disabled/malformed provider configuration, rejected budget, oversized
input, unusable text and fixtures incur no provider call. Invalid JSON, unknown
citation IDs, unsupported score fields/claims and unexpected model IDs never
become visible reports. Timeout/transport ambiguity remains UNCERTAIN, with the
reservation retained and no automatic paid-call replay. Expired dispatched jobs
are uncertain; stale tokens cannot settle newer claims. An expired lease before
dispatch is reclaimable.

## Observed verification

- Offline frontend dependencies installed with `npm ci --offline --ignore-scripts`.
- `npm test`: 77 passed, including report/status/client coverage.
- `npm run typecheck`: passed.
- `npm run build`: web and extension passed with an explicitly test-only Clerk
  public key. esbuild required an unsandboxed build to resolve parent directories.
  The key cannot validate real authentication and these artifacts are not a release.
- Targeted report/provider and worker/deployment tests: 46 passed.
- Final backend regression run: 1,260 passed, 357 skipped (database/live-browser checks without their explicit test configuration). One existing FastAPI/httpx deprecation warning.
- Disposable PostgreSQL: 97 passed, 5 configuration-dependent skips, against
  fresh isolated schemas in `vct_oct6_report`. Includes saved-evidence API
  persistence/ownership, atomic enqueue rollback, redelivery, stale leases,
  crash uncertainty, concurrent budget reservations, migration/rollback and
  extraction regressions. No shared container settings were changed.
- The initial database regression run exposed an outdated snapshot cleanup
  helper; it now deletes report jobs before snapshots. The corrected run passed.
  Synthetic unpaid analyses left by that first run were removed using only the
  suite UUID identity patterns and absence of a dispatch ledger.
- Latest report/provider focused run: 30 passed after the final trace metadata change.
- `git diff --check`: passed.

## Activation and remaining acceptance

### Review corrections and final verification

All four review lenses completed. Nine local correction groups were applied:
business field labels/shipping projection, quantity-safe contact redaction,
conservative Vietnamese screening, numeric/written score rejection, decoded
credential rejection, nested provider-shape classification, continuous worker
draining coverage, mounted buyer Page coverage, and historical migration backfill.
The language screen is intentionally conservative and may reject valid prose;
it is not a factual or translation-quality evaluator.

Parent final checks:

- PostgreSQL-enabled backend run: 1,383 passed, 261 gated skips. Twenty-two tests
  could not set up because the existing pytest temporary directory was denied.
  They passed unchanged after using a new workspace temporary path: 23 passing
  cases in that rerun, including one overlapping case. An initial retry also
  needed its missing temporary parent directory created; no source fix was needed.
- Independent migration diagnostic run: 23 passed.
- Final provider/validator run: 79 passed, including four newly added written-number
  score cases. Across the broad run, setup retries and final focused checks,
  1,409 distinct backend cases have passing evidence. This is not one uninterrupted
  full-suite pass.
- Frontend: 78 passed, including actual Page mounting; typecheck passed.
- Web and extension builds passed with a synthetic Clerk public key.
- Credential scan passed with a synthetic YEScale backend key present during
  build. No configured server credentials were found in frontend output.
- The first sandbox frontend test attempt failed on esbuild directory traversal;
  all 78 tests passed unchanged with the required filesystem access.
- Remaining gated browser/live-cloud checks were not claimed as passing.

Live provider calls and deployment were not enabled. Configure backend-only
credentials, exact immutable model ID/version, contractual conservative rate
bounds, lifetime budget, per-call ceiling and deadline before activation.
Actual cost remains unknown; returned usage gives only a labeled configured-rate
estimate. Uncertain dispatches require operator reconciliation against provider
records before any further action. Azure combined/dispatcher workers drain the
PostgreSQL report queue; keep the dispatcher running for report-only uploads.

Live Vietnamese factual quality, latency/cost, model-version guarantees and
Azure acceptance require the separately authorized release. Schema and reference
validation does not independently verify the factual meaning of model prose.
Input minimization removes selected identifiers/contact fields and contact-like
text, but cannot prove arbitrary source prose contains no personal information.
