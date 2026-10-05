# Proposed bounded diagnostic and correction run

Status: approved by the operator on 2026-10-05; execution results recorded separately.

The two approved local diagnostics encountered different first failures:
SCHEMA_INVALID/findings, then NON_VIETNAMESE_PROSE/summary. Neither produced the
findings-only sample permitted by the first policy. A useful diagnostic must
handle whichever allowed prose field fails first. The prepared offline helper
does that without changing production validation.

## Proposed authorization

- At most three deliberate fresh requests, total spending ceiling $0.03 and
  $0.01 per request, within the existing $2 aggregate approval and conservative
  $0.09 ledger cap. Count reservations for unknown/uncertain costs against these
  bounds; stop if a reservation would exceed either remaining ceiling.
- Inspect and reconcile every result before deciding whether a next request is
  needed. No transport retries, replays, model changes or automatic retry loop.
  Stop early once the diagnostic and substantive acceptance succeed.
- Same sanitized Chinese Taobao fixture and minimized public evidence,
  deepseek-v4.1-flash / expected deepseek-v4-1-flash-260910, thinking disabled,
  120-second deadline, maximum 2400 output tokens.
- Each rejected response may retain only its first failing prose field among
  summary, findings.text, limitations, actions, and self_reported_confidence.basis.
  Each capture is at most 1600 characters and 8000 UTF-8 bytes; batch maximum
  three local captures / 4800 characters / 24000 bytes.
- Redact credential/contact strings; withhold output if safe redaction is not
  established. No complete rejected response, arbitrary fields/keys, headers,
  credentials, account/reviewer identifiers or HTML storage. Schema failures
  retain only fixed subtype and allowlisted location, with no rejected values.
- Keep captures local and Git-excluded for this investigation. Publish only
  conclusions and sanitized/synthetic regression cases, never the captures.
- Use observed evidence to distinguish invalid/foreign output from a Vietnamese
  screen false positive. Only an evidenced correction proceeds through regression
  tests and implementation review; never weaken a guard to fit unknown output.
- Where a correction is warranted, implement and verify it, commit locally and
  release the reviewed change to the existing dev resources. A remaining request
  may be used for deliberate cloud owner-scoped acceptance and reopen, after
  checking deployed readiness and retained spending. Do not push Git remotely
  unless separately requested.
- Keep confidence explicitly uncalibrated and separate from supplier safety and
  deterministic assessment confidence. Preserve old reports, failures, snapshots
  and reservations. If the batch ends without acceptance, record that honestly
  and stop paid requests.

The expanded first-field policy and bounded batch avoid needing a separate
approval for each known validation location. The helper already passes offline
retention/selection checks. No broader capture or further paid call will occur
until the operator approves this concrete proposal.
