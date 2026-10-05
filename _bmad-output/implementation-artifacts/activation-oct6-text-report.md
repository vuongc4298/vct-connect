# Oct 6 live report activation

Implementation: local commit `541d99e`, branch `codex/oct6-text-report`.
Azure activation completed on 2026-10-05 after migration and queue audit.
Owned Clerk browser acceptance passed on 2026-10-05 after the quotation
validation correction. Chinese-to-Vietnamese translation quality remains
unverified. Earlier disabled and pending states below describe historical stages.

## Verified target

- Subscription: `93bd5d96-c7a2-4072-9aa3-458ab6132d92`.
- Resource group: `VCT_Connect_Service_Bus`, region `southeastasia`.
- Existing Key Vault: `vctconn-p6zsuuvnenn5a`.
- Existing API/web/dispatcher apps are running. Dispatcher currently has no
  YEScale or text-report environment variables.
- Key Vault contains the enabled `yescale-api-key` alongside `clerk-secret-key`,
  `database-url`, and `postgres-admin-password`. Catalogue authentication passed.
- Local environment files and process configuration have no inspected YEScale
  credentials or model configuration. Secret values were not printed.

## Operator information needed

1. Credential supplied securely through Key Vault; verification complete.
2. Approved rehearsal ceilings: **$2 total, $0.10 per request**. User answered
   "1" to the displayed budget choices, interpreted as the first option and
   communicated back to the user. These limits do not authorize account top-ups.
3. Choose an exact model/version, or delegate catalogue inspection and a pinned
   candidate recommendation. Confirm gateway input/output price upper bounds
   in USD per million tokens before activation.

The current official integration example uses
`https://api.yescale.io/v1/chat/completions`. YEScale supports app/environment
access keys, model restrictions and key budgets. Its example model is not an
approved model selection for this demo. See the
[official integration guide](https://yescale.io/blog/huong-dan-su-dung-yescale-ai-control-plane).

## Execution after information is supplied

1. Verify the key through bounded read-only catalogue access; inspect available
   immutable model identifiers and pricing. Do not make paid generation calls
   before limits and candidate configuration are settled.
2. Prepare deployment configuration for backend-only Key Vault access, model
   provenance, contractual rates, byte/token/deadline bounds and approved budget.
   Inspect queued/backfilled analyses before enabling automatic processing so
   the selected rehearsal evidence receives the intended budget.
3. Build images from the reviewed implementation using real existing Clerk
   public configuration. Keep report calls disabled through migration and
   baseline deployment. Preserve the existing queue, identity and access rules.
4. Apply migration 0010 through the private-network migration job and verify the
   database/report queue. Activate the bounded report path only after these
   gates pass. Record exact image digests and configuration provenance.
5. Ask the operator to sign in if a fresh Clerk session is necessary. Rehearse
   owned saved Chinese HTML → progress → real Vietnamese report → citations →
   reopen. Use `backend/tests/fixtures/1688_offer_996518024136.html` and its
   matching canonical URL as the prepared example.
6. Check Vietnamese factual support, limitations/actions, actual returned model,
   latency, usage and billing records. Observe uncertainty without blind replay;
   label estimates separately from actual gateway charges.
7. Retain saved-result evidence and an extraction-only fallback. Disable the
   report feature if live quality or gateway assumptions fail. Do not discard
   immutable extraction or spend-ledger records.

## Credential readiness update

Operator saved `yescale-api-key`. Read-only verification confirmed the secret is
enabled and the credential can access `GET https://api.yescale.io/v1/models`.
The catalogue returns 89 model IDs. Its entries contain only created/id/model;
they expose neither prices nor immutable-version guarantees. No IDs in this
catalogue contain a full dated snapshot identifier. This does not prove version
pinning is unsupported; it means it has not been established from that response.

Rehearsal budget is approved at $2 total and $0.10 per request. Model/version
selection is now supplied: operator intends Starter access with DeepSeek V4.1
Flash. Signed-in catalogue lists `deepseek-v4.1-flash`, input $0.15/output $0.60
per million tokens and a 1x billing multiplier on its card. The details panel
says "No tier information"; no immutable dated snapshot guarantee is shown.
Record the exact named version and this limitation rather than claim an
immutable provider snapshot. Observed catalogue latency: P50 30s, P95 64.29s,
24 qualified points; use a 90s operator rehearsal deadline within the supported
120s cap. Workspace balance displays $0.10; no top-up is authorized.

One local live rehearsal was prepared with an effective $0.10 ledger budget,
also respecting the approved $2 lifetime/$0.10 per-call ceilings. Exact projected
input is saved in `tmp/yescale-evidence-preview.json`: public dress title,
price range 37–39, MOQ 1, aggregate review counts/rates and rating, missing fields.
The captured 1688 page's projected title is English; this example does not prove
Chinese-to-Vietnamese translation quality. No identity/contact/reviewer text or
raw HTML is transmitted. Automatic approval initially rejected the payload
export; inspection established the limited public content and a subsequent
approval review allowed the same action. Local setup failures occurred before
dispatch (URL encoding, Azure CLI executable resolution) and were corrected
without paid retries. No Azure deployment or feature activation has occurred.

## First live call: reconciled

- Local retained schema: `live_yescale_rehearsal_20261005` in `vct_oct6_report`.
- Analysis: `f4a9ef8a-dab7-4358-afac-54e3e9b7a948`.
- Dispatch: `aca656fb-d295-4e2a-b9bb-277f9ae583e4`.
- Gateway request: `20261005124330752491679whrY7vIY`.
- Exactly one dispatch, reserve $0.0020292; immutable extraction preserved.
- Requested `deepseek-v4.1-flash`; returned `deepseek-v4-1-flash-260910`.
- App result FAILED / UNEXPECTED_MODEL. No report accepted or displayed.
- Returned usage: 885 input, 2400 output tokens; local latency 58046ms.
- Signed-in YEScale request detail confirms Starter key, successful gateway
  completion, billing ledger charge $0.0016 and balance after $0.0984. This is
  dashboard-displayed billing precision, not an unrounded invoice value. Local
  product ledger actual_usd remains null; preserve it rather than overwrite from
  a rounded dashboard reading.
- No automatic replay occurred. The script refuses any retained paid dispatch.
- Adapter follow-up: separate exact requested/expected-returned IDs, preserve
  both in provenance, retain rejection of all other model IDs; explicitly
  configurable thinking disabled for this short report. DeepSeek docs establish
  default thinking high and the `thinking.type=disabled` request parameter:
  https://api-docs.deepseek.com/guides/thinking_mode/ . Thinking consumption is a
  hypothesis here: the current adapter did not retain raw reasoning or finish
  reason after rejecting the model, so token exhaustion alone does not prove it.
- Use a new deliberate rehearsal only after adapter validation; never requeue
  the dispatched analysis. Chinese translation quality remains unverified
  because this captured page projects an English product title.

Operator approved the adapter fix and continuing in the existing worktree while
preserving operational evidence. Backend configuration now additionally supports:

```
YESCALE_MODEL=deepseek-v4.1-flash
YESCALE_EXPECTED_RETURNED_MODEL=deepseek-v4-1-flash-260910
YESCALE_THINKING=disabled
TEXT_REPORT_DEADLINE_SECONDS=120
```

Empty expected-returned ID defaults to the requested ID. Empty thinking omits
the parameter and preserves provider behavior; valid explicit values are only
enabled/disabled. No prefix matching or inferred aliases are accepted. Both
identifiers and the thinking setting are retained in report metadata. These
settings are local preparation, not Azure activation. The deliberate second
rehearsal uses a new schema/analysis and accounts for the prior displayed charge
with an effective balance cap of $0.0984; the first dispatch remains intact.

## Adapter verification outcome

Local commits: `fdebda3` (exact returned version/thinking) and `2762ce8`
(ordinary Vietnamese purchasing vocabulary). Both quick reviews found no
actionable findings. Final focused suite: 92 passed; isolated PostgreSQL suite:
10 passed before the pure language-screen correction. No Azure deployment,
public authentication/browser acceptance or Chinese translation acceptance.

Second call: app FAILED/INVALID_OUTPUT, 860 input/1578 output, 26.36s; gateway
ledger displays $0.0011 and balance after $0.0974. Third deliberate diagnostic:
860 input/1190 output, 15.05s; dashboard charge $0.0008. Retained bounded report
text established NON_VIETNAMESE_PROSE false positives on ordinary Vietnamese
fabric/returns/payment/dispute terms. Six regression phrases pass after the
lexicon correction; foreign-script/English/schema/citation/score guards remain.
The same real diagnostic response passes all report checks offline, saved as
`tmp/live-yescale-validated-report.json`. Failed jobs were not relabeled READY.

Final fresh-analysis call: analysis `7e9342cf-dff7-4328-8793-97f80a1f5850`,
dispatch `a0d7dbad-937f-4cb9-b484-b692d08ac05e`, local state UNCERTAIN /
PROVIDER_TIMEOUT at 90016ms, reserve $0.0020292 retained. YEScale request detail
at 2026-10-05 13:13:13 Asia/Bangkok (abbreviated ID ending Vqs7rx) reports
request_failed, 503, do_request_failed, transient_upstream, retry_count 0,
latency 89909ms, usage zero and displayed cost $0.00. No billing ledger charge
is shown for that failed request. Product ledger remains uncertain with actual
cost unknown; no paid replay or reserve deletion followed reconciliation.

Four provider calls total; sum of displayed charges is approximately $0.0035.
Model compatibility and saved-response validation are established. Consistent
live READY completion remains unverified due to the final upstream 503; retain
extraction-only fallback and the clearly labeled validated offline report.

Operator subsequently approved increasing the deadline and proceeding with a
fresh rehearsal, then route/backup investigation if needed. Active rehearsal
deadline is now 120 seconds, the existing supported cap. The 90-second values
above describe historical calls. Extended rehearsal reserves against a
conservative $0.094 balance cap, preserving the prior uncertain reservation;
existing jobs are never requeued.

## Extended rehearsal succeeded

The fresh 120-second rehearsal reached READY on 2026-10-05. Analysis
`36065625-f59a-4493-96cf-e643d19b19ec`, immutable snapshot
`13edcde9-576c-473f-9320-de9fe6cfce4a`, gateway request
`20261005132445186801329cw3ZGF7X`. Returned exact expected version
`deepseek-v4-1-flash-260910`, thinking disabled, 860 input/1353 output tokens,
observed latency 42015ms, reserve $0.0020292. Schema, citations, Vietnamese
prose and score checks passed; original extraction was preserved. A fresh Store
reopened the exact persisted report for its owner; the schema has one dispatch
and another worker poll found no queued work. The previous uncertain job and its
reserve remain intact. This successful call finished well below 90s, so the
timeout increase cannot be claimed as the cause of upstream recovery.

YEScale dashboard confirms successful Starter call and displayed $0.0009 charge.
Five total requests, four displayed charges totaling approximately $0.0044;
the earlier 503 displays $0.00. No backup model was needed. Readable local
preview: `tmp/live-vietnamese-report-20261005.md`; retained report/ledger evidence:
`tmp/live-yescale-rehearsal-20261005-extended.json`.

Live local READY persistence/reopen acceptance is now established for this
bounded saved evidence. Azure deployment, real Clerk browser acceptance and
Chinese-to-Vietnamese translation acceptance remain pending. Use the successful
saved report and extraction fallback if gateway availability varies.

## Azure activation: 2026-10-05

- Configuration commit `ecb1b9c`; backend image digest
  `sha256:4cbe10510b68165f3b40d33191cc41dcf706fc3a237f6d228883d6fb9e2acaed`;
  web image digest
  `sha256:bae4b3d1460cf52bcad7fb38b588b7ea8093bcda76ad26c2c13974e29689347a`.
- Built using the existing deployed Clerk publishable key. Report tests in the
  actual backend image: 92 passed; authentication tests: 32 passed. Bicep
  compiled; deployment script tests: 20 passed. Quick review finding about
  subsequent deployments disabling reports was patched.
- Full-template what-if included unrelated database/network default changes.
  Used narrow application image and worker configuration updates instead,
  preserving infrastructure, identity permissions and the existing queue.
- Stopped analysis executions and dispatcher replicas before migration.
  Private migration execution `vct-connect-dev-migrate-btey0en` succeeded.
  Private audit execution `vct-connect-dev-migrate-hw2jdf2` succeeded: zero
  dispatches/reservations and zero pending historical owned extractions.
  Four queued historical reports were held as UNAVAILABLE/PRE_ACTIVATION_HOLD;
  three existing reports were INSUFFICIENT. No extraction or ledger was deleted.
- Dispatcher revision `vct-connect-dev-dispatcher--0000018` is running. Analysis
  job is Event-triggered on the existing `vct-connect-standard/vct-analyse`
  queue, polling every 30 seconds, max three executions. Switching to Manual
  had cleared its event configuration; the reviewed original rule was restored.
- Both workers have a backend-only Key Vault reference to `yescale-api-key`,
  thinking disabled, requested `deepseek-v4.1-flash`, exact expected returned
  `deepseek-v4-1-flash-260910`, 120-second deadline, 2400 output token cap and
  $0.09 lifetime ledger budget. The $0.10 per-call ceiling remains; the smaller
  total cap accounts conservatively for funded balance and retained local
  reservations. No top-up or automatic replay was performed.
- Web availability, unauthenticated rejection and private API ingress checks
  passed. Guest fixture completed once through the deployed queue with
  cookie-scoped status; no paid report is generated for a guest.
  Signed-in browser saved-page import/report/reopen still requires the
  operator's fresh Clerk login in the opened VCT Connect tab.
- Operational rollback references, deployment parameters, audit output and
  scripts are retained under `tmp/azure-report-*`; secret values are absent.
- Dependency audit reports eight existing workspace advisories (seven high,
  one moderate): Clerk extension dependency chain and Next's PostCSS build
  dependency. Dependency upgrade is separate follow-up; the web flow does not
  use the extension bundle or compile user-supplied CSS. This rollout did not
  claim a clean dependency audit.

## Signed-in cloud acceptance: 2026-10-05

The first signed-in import reached FAILED/INVALID_OUTPUT (analysis
`495a48f2-71b0-442d-a79b-ca2904d6ae3c`, gateway request
`202610051407221739475PCEzoZLt`). A separate, deliberate local diagnostic
reproduced a language-screen false positive on a single-quoted English source
title inside Vietnamese prose. This establishes the diagnostic cause, not the
unretained contents of the first cloud response. Both failed analyses remain
failed; neither was replayed or relabeled.

Correction commit `ec8c44a` exempts only exact single-quoted supplied evidence
strings, using one deterministic replacement pass after the unsupported-score
guard. Independent review findings about apostrophes, swallowed surrounding
English and replacement ordering were resolved. All 109 focused report tests
passed locally and in the final backend image. Final deployed backend digest:
`sha256:eebc31de07fd7e9982b2c83cb648f01edf2b93e414429ae89d6e1e3462afbca0`.
Dispatcher revision `vct-connect-dev-dispatcher--0000019` and API revision
`vct-connect-dev-api--0000010` were running; analysis and migration jobs use
the same backend image. The web image and approved report bounds are unchanged.

Fresh signed-in saved-page import completed with report READY:

- [Owned saved report](https://vct-connect-dev-web.blackdesert-0144dda1.southeastasia.azurecontainerapps.io/?analysis=36677413-84b7-45b5-8255-828fbe4cd0c8).
- Analysis `36677413-84b7-45b5-8255-828fbe4cd0c8`; immutable snapshot
  `4f100d5e-6297-4578-9611-c24f28876115`.
- Gateway request `20261005143154813333689YMoi4x5w`; returned exact expected
  model `deepseek-v4-1-flash-260910`, thinking disabled, 860 input / 1329 output
  tokens; app latency 23388ms. Generated at `2026-10-05T07:32:18.124654+00:00`.
- Browser showed Vietnamese summary, four source observations, two labeled
  inferences, limitations, pre-order actions and E1–E4 citations. E2 opened the
  saved price evidence: minimum 37.00, maximum 39.00, MOQ 1.
- A fresh navigation through the owned analysis link reopened the exact same
  report section text. Read-only private acceptance execution
  `vct-connect-dev-migrate-pbbct7t` also verified owner-scoped retrieval,
  COMPLETED/READY state, matching immutable snapshot and exactly one dispatch.
  Persisted report SHA-256:
  `40eac95bad4f7610fc725cfd359bd96815b0214fb08d8c21f1ab83f2f9d3d482`.
- The earlier cloud failure remained intact with its one dispatch. Cloud ledger
  has two dispatches and total retained reservations $0.0040584. Successful
  call reservation is $0.0020292; configured-rate usage estimate is $0.0009264.
  Actual product-ledger cost remains unknown/null.
- YEScale detail displays a $0.0008 charge and balance after $0.0927; its log
  table displays $0.0009 for the same request. These are rounded dashboard
  displays, not an exact invoice reconciliation. No top-up or automatic paid
  replay occurred.

Operational evidence is retained in `tmp/cloud-report-acceptance-logs.json`,
`tmp/azure-report-quote-fix-deployment.json` and
`tmp/owned-cloud-report-ready.jpg`. The projected product title is English;
this acceptance demonstrates Vietnamese interpretation of the saved evidence,
not Chinese-title translation quality. Source freshness remains unknown and
no computed risk or confidence score is presented.

## Reopened source correction: 2026-10-05

Commit `8799ac8` restores the source URL on the first owned response for every
extraction method and removes the extension-only assumption for saved links.
Subsequent polling preserves form edits. All 80 frontend tests and typecheck
passed; independent quick review found no actionable issues. The production web
build succeeded using the existing Clerk public configuration.

Deployed web digest
`sha256:a5954af3acaded647bd2d0a354069213e4b6ace9e8eab665a5eec602931a228c`,
revision `vct-connect-dev-web--0000010`: Healthy, Running, Provisioned.
The signed-in saved report reload displays its actual source
`https://detail.1688.com/offer/996518024136.html`, no fixture badge, and exactly
the same persisted report section. No generation was submitted during this check.
Screenshot: `tmp/reopened-report-source-fixed.jpg`.

Demo status: the selected signed-in vertical journey is verified. Presentation
walkthrough and saved-result fallback are recorded in `oct6-demo-walkthrough.md`.
Chinese title/review interpretation was rehearsed separately with the
existing sanitized Taobao product capture; this does not close the full analysis,
reporting, extraction or pilot epics. The original checkout's edited development
pipeline is preserved rather than overwritten from this worktree's older copy.

## Chinese evidence rehearsal: explicit upstream failure

Used `backend/tests/fixtures/taobao_item_1076425861755.html`, derived from the
operator's authenticated capture with documented provenance in
`backend/tests/fixtures/taobao-provenance.md`. Original capture time is unknown.
This source has authentic Chinese product/review text; account/session state and
reviewer identities are removed. The model projection selects bounded public
title, prices, metrics, delivery text and review bodies, excluding supplier IDs,
identity, contacts and raw HTML. One deliberate submission was made under the
existing approved bounds.

Analysis `c40adda8-aba1-42c2-8306-12f8604f1abc`, immutable snapshot
`39d6a669-0384-43c2-8ed1-1837c0b7ad37`: extraction COMPLETED/PARTIAL; report
UNCERTAIN/PROVIDER_TIMEOUT after 120001ms. Read-only private inspection execution
`vct-connect-dev-migrate-3xf10w0` confirmed exactly one dispatch
`9fe5a1fe-d800-49c5-a552-39ae1c589fd0`, reserve $0.0021396 retained, actual cost
unknown/null. Logs retained in `tmp/cloud-chinese-inspect-logs.json`.

YEScale detail at 2026-10-05 14:59:14 Asia/Bangkok, request abbreviated suffix
`H3JJ03`, reports request_failed, 503/do_request_failed/transient_upstream,
latency 120084ms, zero usage and displayed $0.00, without a billing charge ledger.
Gateway metadata reports retry_count 1; this is an upstream gateway retry, not
an additional application dispatch. No application replay, relabeling or reserve
deletion occurred. Chinese translation acceptance remains unverified because
no report returned. Use the already verified saved Vietnamese report for the
demo; the Chinese extraction is retained as a second evidence example.
