# Signed-in extension acceptance — ticket 2.13 / A5

Status: automated checks can run; live acceptance awaits a connected source session.

On 2026-10-03 the browser inventory exposed only empty Codex in-app and MCP Apps browser surfaces. No Chrome/Edge source session was connected. The earlier accepted 1688 capture and Taobao item/import checks remain historical evidence; they do not establish latest-release live shop capture or result opening.

## Required live journey

Use the installed candidate extension and the deployed development web/backend release. Record extension version/build revision, backend image digest, date and platform/page family. The user signs in through their normal source session; a login or CAPTCHA is an access outcome, never a passed capture.

1. Open an accessible canonical 1688 offer or Taobao item and invoke **Capture this page**. Inspect the actual request to the capture endpoint: only supported source identity and selected bounded fields are in its JSON. Platform cookies, passwords, session tokens, full HTML and arbitrary page globals must be absent. VCT authorization belongs in the request header, not the source payload. Record field names, byte count and status only; do not save credentials or an unredacted HAR.
2. Poll the created analysis with its owner. Verify the persisted source identity, extension method/mode, capture hash/version, missing fields, completeness and merge provenance. Repeat equivalent evidence and inspect deduplication; a different owner must receive 404 and no snapshot data.
3. Confirm automatic result opening lands on that analysis. Reopen the popup and recover the existing result after a failed lookup. Record observed destinations/outcomes, not merely Chrome API invocation.
4. Repeat for an accessible live Taobao shop/category page with the audited product shelf. Verify selected visible product URLs/titles and shop identity against the page. A saved shop import or synthetic DOM test does not cover this row.
5. Record pass/fail/access-blocked for each row with sanitized metadata. A missing source session stays pending. Preserve prior accepted item/import evidence and the user's earlier manual deferral.

## Automated supporting gates

### Existing coverage and loading questions owned by 2.13

During the permitted representative live captures above, record source loading state, selected field names, missing fields and completeness. The prior 25% 1688 observation does not qualify current company/activity/rating/review/delivery/transaction coverage. Observe whether a still-loading sparse capture consumes quota; retain that as an open policy/coverage outcome rather than changing quota or treating unknown fields as verified. Record the evidence gaps for planned 2.16's separate API eligibility/field comparison. Source access is required for these observations; no automated fixture claims them passed.

### Available automated checks

- Extension selected DOM, byte bounds and result-navigation tests: `npm test --prefix frontend`.
- Client/extension types: `npm run typecheck --prefix frontend`.
- Backend selected schema, secret rejection and deduplication: `backend/tests/test_extension_merge.py`.
- Database-backed owner-scoped capture/merge/replay: relevant extension cases in `backend/tests/test_postgres_tracer.py` with a disposable PostgreSQL database.

These checks support implementation readiness. They do not mark the live journey complete.

References: [retrospective A5](epic-extraction-retrospective.md), [extension build](story-accept-and-merge-extension-evidence-safely-plan.md), [Taobao audit](taobao-sample-audit.md).
