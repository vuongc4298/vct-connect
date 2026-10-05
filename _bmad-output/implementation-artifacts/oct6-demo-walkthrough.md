# Oct 6 buyer demo walkthrough

## Main journey: about three minutes

1. Sign in to VCT Connect. Explain that the demo interprets saved public evidence;
   platform access can be blocked and source freshness may be unknown.
2. Enter `https://detail.1688.com/offer/996518024136.html` and select
   `backend/tests/fixtures/1688_offer_996518024136.html`. Submit once. Show progress
   while extraction and Vietnamese interpretation complete.
3. Read the Vietnamese summary. Explain source observations versus inferences,
   missing evidence, limitations and pre-order actions. No computed risk or
   confidence score is supplied by this real report path.
4. Open E2 and expand its evidence: price minimum 37.00, maximum 39.00, MOQ 1.
   These are saved source claims, not independently verified facts.
5. Reopen the owned saved link below. Show the same persisted report and source.
   Reopening does not request generation.

## Saved-result fallback

[Verified owned report](https://vct-connect-dev-web.blackdesert-0144dda1.southeastasia.azurecontainerapps.io/?analysis=36677413-84b7-45b5-8255-828fbe4cd0c8).
Use the same account that created it. Screenshot:
`tmp/owned-cloud-report-ready.jpg`. Corrected source form screenshot:
`tmp/reopened-report-source-fixed.jpg`.

If a fresh import is slow or fails, switch to this saved result. Preserve its
failure status and extraction; do not replay a dispatched report blindly. The
retained snapshot is the evidence fallback. Demo fixture scores elsewhere are
illustrative and must be described as such.

## Before presenting

- Confirm sign-in and open the saved link in advance.
- Keep the matching saved HTML available; live 1688 access is unreliable.
- A fresh submission incurs one bounded provider request; reopening does not.
- Keep configured spending limits and the 120-second report deadline.
- Chinese product-title translation requires separate acceptance: this main
  page's projected product title is English.

The separate Chinese Taobao rehearsal extracted the page successfully but its
provider request returned an upstream 503 at the 120-second deadline. Translation
is still unverified. Do not present it as a completed report or retry it blindly.
[Retained Chinese evidence](https://vct-connect-dev-web.blackdesert-0144dda1.southeastasia.azurecontainerapps.io/?analysis=c40adda8-aba1-42c2-8306-12f8604f1abc).

One operator-approved fresh attempt returned in 49.4 seconds but failed output
validation. [Fresh failed result](https://vct-connect-dev-web.blackdesert-0144dda1.southeastasia.azurecontainerapps.io/?analysis=5d86a995-5687-4b60-9e18-b31c87216d7e).
Chinese translation remains unverified. Freeze the current implementation and
present the verified saved report above; do not describe the Chinese attempt as
a completed report. Further diagnosis is after-demo work unless reprioritized.

Full scoring, review clustering, image/video analysis, production history,
Watchlist, human evaluation and formal pilot validation remain after-demo work.
