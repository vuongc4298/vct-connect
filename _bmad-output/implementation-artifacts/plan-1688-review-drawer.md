# 1688 review drawer capture

Baseline: 959a05c. Operator supplied actual drawer markup after the complete saved page omitted its dynamic drawer. This continues the previously approved extractor fix and renderer-failure waiver.

Acceptance: capture the visible scoped review drawer, prefer it over the inline snippet, retain separate repeated-text cards, ignore hidden/ambiguous panels, exclude buyer identity/avatar fields, and retain existing per-review/list/payload bounds. Closed drawers fall back to inline capture. Pagination is not traversed and media bytes are not captured.

Implementation: capture `.ant-drawer-body .evaluate-panel-content` and its scoped title/rating/review text. Actual drawer contains ten cards and three repeated platform-rendered sentences. A sanitized fixture removes original buyer identity and all media references, with synthetic buyer canaries to test exclusion.

Independent review found that same-owner snapshot merging deduplicated identical current reviews. Fixed 1688 review merging to retain maximum observed multiplicity per text across captures, avoid growth from overlapping recaptures, preserve newer cards first and limit the combined set to 20. Historical metadata enriches only unambiguous one-to-one matches. Other-platform legacy merge behavior is unchanged.

Validation: 131 frontend tests, TypeScript, extension production build, 170 backend tests, two PostgreSQL extension tests and 17 actual-browser saved-DOM checks passed. Ten reviews survive normalization, merge and assessment preparation. The API was restarted. Fresh Chrome capture remains the operator acceptance step; media analysis remains unconnected.

Status: implemented, verified and independently reviewed with no remaining actionable findings.
