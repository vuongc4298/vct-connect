- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-platform-foundation/story-trace-one-queued-analysis-through-the-platform-plan.md`
  summary: Add Azure Service Bus lock renewal for analyses that run longer than one message lock.
  evidence: The deterministic story 1.1 fixture completes in seconds, but a later long-running worker could lose its lock before persisting; story 1.4 owns production processing hardening.
- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-platform-foundation/story-trace-one-queued-analysis-through-the-platform-plan.md`
  summary: Give local queue claims an ownership token before relying on concurrent offline workers.
  evidence: A stale local worker can release a newer five-minute claim using only the analysis ID; the local transport is an optional development fallback.
- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-platform-foundation/story-trace-one-queued-analysis-through-the-platform-plan.md`
  summary: Verify the tracer page by clicking Submit and observing its rendered polling states in a browser.
  evidence: The in-app browser service returned no available browsers. HTTP checks verified the Next.js page and its API rewrite, but did not inspect rendered client state.
- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-platform-foundation/story-persist-the-core-business-and-evidence-schema-plan.md`
  summary: Add an outbox or equivalent reconciliation for ambiguous Azure Service Bus publish failures.
  evidence: Story 1.1 deletes a CREATED analysis when publish raises even if the broker may have accepted the message; Story 1.4 owns production queue idempotency and retry behavior.
- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-platform-foundation/story-persist-the-core-business-and-evidence-schema-plan.md`
  summary: Reconcile the analysis status when Service Bus publication succeeds but the QUEUED database update fails.
  evidence: The Story 1.1 publish and later status update are separate operations, so a successful message can exist while the caller receives an error; this predates the schema change.
- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-platform-foundation/story-persist-the-core-business-and-evidence-schema-plan.md`
  summary: Define repair behavior for a COMPLETED analysis whose result row is missing.
  evidence: The current atomic completion transaction cannot create this state, but manually altered or future legacy data would be acknowledged without result repair; later idempotency work should settle the policy.
- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-platform-foundation/story-verify-clerk-identity-and-api-roles-plan.md`
  summary: Reconcile Azure publications whose broker acceptance is unknown when the publish call raises.
  evidence: Story 1.1 deletes the CREATED row after any publish exception, although the broker may have accepted the message; production queue hardening must use an outbox or reconciliation record.
- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-platform-foundation/story-verify-clerk-identity-and-api-roles-plan.md`
  summary: Preserve repair evidence when both Azure publication and its compensating database deletion fail.
  evidence: A second database failure in the Story 1.1 exception path can leave a CREATED analysis permanently unqueued without a cleanup marker.
- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-platform-foundation/story-verify-clerk-identity-and-api-roles-plan.md`
  summary: Reconcile Azure messages published before the QUEUED status update fails.
  evidence: Story 1.1 publishes and updates status in separate operations, so a client can receive an error and retry while the first message remains live.
- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-platform-foundation/story-verify-clerk-identity-and-api-roles-plan.md`
  summary: Add ownership tokens to local queue claims before supporting concurrent offline workers.
  evidence: A stale Story 1.1 worker can clear a newer worker's claim because release_local identifies the claim only by analysis ID.
- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-platform-foundation/story-verify-clerk-identity-and-api-roles-plan.md`
  summary: Add bounded request timeouts to the shared browser API client.
  evidence: The Story 1.1 fetch path can remain pending indefinitely, leaving submission busy or polling stalled; this behavior predates Clerk integration.
- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-platform-foundation/story-harden-service-bus-processing-and-state-transitions-plan.md`
  summary: Validate and sanitize locally stored demo history entries before rendering them.
  evidence: Pre-existing demo history code casts any nonempty JSON array to `HistoryEntry[]`; malformed legacy or manually edited localStorage data can reach rendering without field validation.
- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-platform-foundation/story-deploy-the-development-baseline-and-protect-secrets-plan.md`
  summary: Add an evidence-backed detector for YEScale credentials when live YEScale integration is implemented.
  evidence: Story 1.5 does not configure a YEScale key, and its scanner checks configured values; the future credential format is not yet specified.
- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-platform-foundation/story-deploy-the-development-baseline-and-protect-secrets-plan.md`
  summary: Reconcile analyses left in DLQ_PENDING if PostgreSQL confirmation fails after Service Bus dead lettering.
  evidence: The Story 1.4 settlement path dead letters before marking the row, so an intervening database outage can leave the final disposition pending.
- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-platform-foundation/story-refactor-sweep-plan.md`
  summary: Validate the configured Clerk issuer's URL and trust domain before deployment.
  evidence: The existing deployment accepted any nonempty issuer, and a malformed value can leave authentication unusable; Story 1.7 preserves Clerk configuration behavior while consolidating deployment commands.
- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-extraction/story-extract-a-1688-url-into-the-shared-supplierdata-contract-plan.md`
  summary: Run GitHub CI and an Azure dev smoke check of a queued live 1688 snapshot after a push.
  evidence: The supplied URL returns an anti-bot challenge, so the adapter correctly records BLOCKED without a snapshot; an accessible public URL is needed to verify the deployed success path.
- source_plan: `_bmad-output/implementation-artifacts/plan-1688-saved-page-import.md`
  summary: Build a user-invoked 1688 browser extension capture that sends only selected rendered evidence and merges it into owner-scoped snapshots.
  evidence: The agreed delivery order starts with saved-page import; browser capture is independently shippable and reuses the import provenance contract.
- source_plan: `_bmad-output/implementation-artifacts/plan-1688-saved-page-import.md`
  summary: Assess 1688 Open Platform API eligibility and field coverage before choosing an official integration.
  evidence: API access and available product, supplier, and review fields require verification from the developer portal and do not block the saved-page import.
