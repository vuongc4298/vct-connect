# Story 3.1 completion: Azure dev release

Release date: 2026-10-06. User explicitly approved push/release after the
fixture acceptance documented in `story31-completion-acceptance.md`.

## Source and image

- Code commit: `f42499cff894e7587bafa019eb2b91d4d21dc7f2`, pushed to
  `codex/oct6-text-report` in the existing private VCT repository.
- Tested and published backend digest:
  `sha256:2ed167c4a1a1d3148e8b91d84804297f506dd02eeaf96dfe8fc78a5e7e3621b6`.
- Registry image:
  `vctconnectp6zsuuvnenn5a.azurecr.io/vct-backend@sha256:2ed167c4a1a1d3148e8b91d84804297f506dd02eeaf96dfe8fc78a5e7e3621b6`.
- The exact non-root release image passed 554 report/auth tests with networking
  disabled and a read-only filesystem. One existing Starlette/httpx deprecation
  warning remains. No provider call was made by these tests.
- No branch CI run was triggered: the repository workflows do not run on this
  branch push. This release relies on the recorded local/image verification.

## Deployment and health

Existing approved subscription/resource group, Standard queue and registry were
verified before publication and deployment. Only backend images were changed;
API/dispatcher and analysis/migrate job configuration, secret references and
private API ingress were preserved. Azure's generated revision URL was excluded
from the configuration comparison after verifying it was the only additional
API change beyond image/revision name.

| Resource | Result |
| --- | --- |
| API | `vct-connect-dev-api--0000020`, active, Healthy, Provisioned, latest ready |
| Dispatcher | `vct-connect-dev-dispatcher--0000029`, active, Healthy, Provisioned, latest ready |
| Analysis job | Matching backend digest, provisioning Succeeded |
| Migrate job | Matching backend digest, provisioning Succeeded |
| Web | Existing revision `vct-connect-dev-web--0000011`, active, Healthy, Provisioned, HTTP 200 |

Web image remains
`sha256:410c164eba65e801b5b79b62d0a41e7ed90f20753aa54d56daa871cb2a16d17a`.
API ingress remains internal with 100% latest-revision traffic. The localhost
rehearsal stack and retained diagnostic database were preserved.

## Preservation verification

Preflight execution `vct-connect-dev-migrate-9uq9wjj` succeeded: internal API
health HTTP 200, 13 dispatches, reserved USD `0.03186975`, no queued/processing
report or extraction jobs. All saved report content/state/timestamps hash:
`a54ba0cf923f061c45d085136b6d2eee7f1d587c39e472aad22292c3ebed2038`.

Post-release execution `vct-connect-dev-migrate-yy4fb04` succeeded. Its saved-report
hash and ledger match preflight exactly; queued/processing reports and extractions
remain zero. READY demo `36677413-84b7-45b5-8255-828fbe4cd0c8` and FAILED v8
`d2bd6fe1-82a5-46b0-b33e-a884e081a4d6` both reopen identically for their owners
and retain exactly one dispatch each. Runtime versions are `vi-text.v8`,
`text-report.v2`, `saved-evidence.v1`, `vi-prose.v5`. Internal API health is
HTTP 200. Localhost API `/healthz` and web `/` also return HTTP 200.

No paid request, report resubmission, ledger reset or saved-report rewrite was
part of this release. The accepted Chinese fixture remains the previously
verified isolated local run; this release does not claim a fresh cloud semantic
acceptance or general translation accuracy. Original Story 3.2 is next.

Operational proof files are retained locally under `tmp/story31-completion-release-*`;
resource snapshots and diagnostic content are not included in this commit.
