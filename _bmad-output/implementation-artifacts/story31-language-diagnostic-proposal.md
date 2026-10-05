# Proposed bounded language diagnostic

Status: proposed; requires operator approval. No further paid request authorized
by this proposal until approval is received.

The single v2 rehearsal failed `NON_VIETNAMESE_PROSE / findings.text`.
Rejected content was not retained, so the current evidence cannot distinguish
untranslated model prose from a false rejection by the conservative lexicon.
Changing validation without that evidence would violate the approved plan.

Proposed next experiment:

- One fresh local diagnostic dispatch, never a replay of the failed cloud job.
- Use only the same authentic sanitized Taobao fixture and minimized projection.
- Keep `deepseek-v4.1-flash`, exact expected returned version,
  thinking disabled, 120-second deadline and 2400 output-token ceiling.
- Maximum authorized charge $0.10 for this one request, within the existing
  $2 aggregate approval; preserve previous reservations and uncertain spend.
- Preserve only the first rejected `findings.text` in a local inspection file:
  maximum 1600 characters and 8000 UTF-8 bytes, after credential, URL, email
  and phone redaction. Do not save the complete response, arbitrary extra
  fields, headers, credentials, account/reviewer identifiers or HTML.
- If safe redaction cannot be established, save no prose. Cloud metadata remains
  fixed category/location only; the production rejection and no-replay behavior
  remain unchanged.
- Keep the capture outside tracked files and public artifacts. Retain it locally
  for this investigation only; report the finding and sanitized regression case
  rather than publishing the capture.
- Evaluate the failing sentence against Chinese evidence and Vietnamese language.
  Only an evidenced correction proceeds to a validator regression and review.
  No automatic paid retry follows this diagnostic.

This changes the rejected-output retention boundary and authorizes a new paid
experiment. The earlier approved plan requires an explicit bounded/redacted
policy for such storage, which is why this proposal needs approval.
