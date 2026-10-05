# Oct 6 live report activation

Implementation: local commit `541d99e`, branch `codex/oct6-text-report`.
Activation and paid calls remain disabled while operator information is pending.

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
TEXT_REPORT_DEADLINE_SECONDS=90
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
