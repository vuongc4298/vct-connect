---
title: 'Accept single-quoted source text in Vietnamese reports'
type: 'bugfix'
ticket: ''
created: '2026-10-05'
status: 'built'
route: 'oneshot'
route_source: 'auto'
review: 'quick'
review_source: 'auto'
lenses_ran: ['quick', 'quick-followup']
context: []
baseline_revision: 'ce131aa20d244414d367c2c9227e146e4a342895'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A live diagnostic report has valid Vietnamese prose but fails the language screen because its English product title is single-quoted and contains a possessive apostrophe. Quoted source text is already allowed for double quotes and backticks.

**Approach:** Recognize straight and curly single-quoted source text without treating apostrophes within words as opening delimiters. Preserve language checks outside quotes, unsupported-score and citation rejection, and the failed paid jobs. Verify the complete retained diagnostic response offline, then deploy the narrow correction and run a fresh owned browser rehearsal within approved limits.

</frozen-after-approval>

## Implementation Notes

- Fewer than 100 code lines, two code/test files; direct oneshot implementation.
- Only diagnostic finding 0 fails screen_vietnamese; every other diagnostic field passes. Initial cloud call's exact rejected text was not retained, so its specific validation cause remains unknown.
- Existing operational tmp evidence is preserved under continuing user authorization.
- Straight/curly single quotes are handled by matching exact strings in supplied evidence, including typographic apostrophe variants; generic ambiguous single-quote regex was discarded after review.
- Final local and actual-image report tests: 106 passed. Complete retained diagnostic response validates offline against the original minimized evidence. Initial prototype image was published but never deployed; final source-matching image has digest `sha256:65e8ee2aa49a5ce6dcb0bf12a1c79bc3219b0d39c9569e191fd4fccb96cc10ef`.
- Follow-up review exposed order-dependent replacement; patched with one literal-match pass. Final local suite: 109 passed; retained full diagnostic still passes offline. The two prototype images above were never deployed; final image will be rebuilt from this correction.

## Plan Change Log

## Review Triage Log

- Medium, patch: regex could swallow English between titles when a closing quote adjoins prose. Removed regex; exact source matching leaves outside prose visible, regression tests pass.
- Medium, patch: plural possessives ended generic quotes prematurely. Exact source matching handles embedded possessives, regression tests pass.
- Medium, patch: sequential set-ordered replacement could break nested apostrophes or manufacture a later source match. Single-pass literal source pattern, ordered longest first, operates on original text; both reproductions have regression tests.

## Verification

- Focused report tests: straight/curly quotes, embedded apostrophes, unbalanced quotes, English outside quotes, wholly foreign quoted prose, and unsupported scores.
- Offline validation of full retained response without another provider call.
- Rebuild backend, verify tests in image, deploy backend images only; never requeue dispatched jobs.
