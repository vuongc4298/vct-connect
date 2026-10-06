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
  summary: RESOLVED — user-invoked 1688 extension capture and owner-scoped merge were implemented.
  evidence: Superseded by the completed epic-extraction story 2.6 and plan-1688-browser-extension-capture.md, with the earlier accepted 25% live capture. Current-release network/result-opening and Taobao live shop acceptance remain separate under retrospective A5 / ticket 2.13; resolving construction does not claim those checks passed.
- source_plan: `_bmad-output/implementation-artifacts/plan-1688-saved-page-import.md`
  summary: Assess 1688 Open Platform API eligibility and field coverage before choosing an official integration.
  evidence: API access and available product, supplier, and review fields require verification from the developer portal and do not block the saved-page import.
- source_plan: `_bmad-output/implementation-artifacts/plan-1688-browser-extension-capture.md`
  summary: Check whether a still-loading 1688 offer page can produce a sparse capture that consumes quota.
  evidence: The signed-in live page state is unavailable here; a real Chrome click-through will show whether loading versus challenge states need separate handling.
- source_plan: `_bmad-output/implementation-artifacts/plan-1688-browser-extension-capture.md`
  summary: Expand reliable browser evidence coverage using representative 1688 pages and field-specific source checks.
  evidence: The user's live capture verified supplier name, product title, and price text at 25% coverage; company details, activity, ratings, reviews, delivery, and transaction signals remain unknown. The user flagged quantity and quality as limited.
- source_plan: `_bmad-output/implementation-artifacts/plan-1688-browser-extension-capture.md`
  summary: Add browser automation for popup reopening, result recovery after a failed lookup, and automatic web-result navigation.
  evidence: The user verified the live sign-in/capture/result flow. Automated checks cover contracts and proxy behavior; browser lifecycle and the final auto-opening addition currently rely on reviewed Chrome API wiring and manual operation.
- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-extraction/story-classify-extraction-failures-and-bounded-http-retries-plan.md`
  summary: Bound decompression output before HTTPX allocates a decoded response chunk.
  evidence: The baseline fetcher used iter_bytes, which automatically decompresses before the 2 MB cap check; a compressed response can allocate beyond that cap. Story 2.2 checks capacity before appending, but streaming decompression with bounded output needs separate transport hardening.
- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-extraction/story-add-the-alibaba-source-adapter-plan.md`
  summary: Resume manual deployed browser acceptance for supported HTML imports, extension extraction, and signed-in Alibaba URL presentation.
  evidence: On 2026-10-02 the user explicitly deferred manual testing in favor of development progress. Automated CI, deployment, guest fixture and two Alibaba access-outcome queue checks passed; these do not establish manual browser compatibility. Alibaba upload/capture remains unsupported, and the existing Taobao shop capture deferral remains in place.

- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-extraction/story-use-playwright-only-when-public-http-evidence-is-insufficien-plan.md`
  summary: An abruptly exited runner can reparent children before discovery.
  evidence: An abruptly exited runner can reparent children before discovery. Whether Playwright pipe closure or Chromium parent-death cleanup prevents surviving children is unverified; settle with forced runner termination and descendant observation (medium if confirmed).

- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-extraction/story-use-playwright-only-when-public-http-evidence-is-insufficien-plan.md`
  summary: Cleanup reserves 0.5 seconds but proc enumeration/profile deletion has no independent wall timer.
  evidence: Cleanup reserves 0.5 seconds but proc enumeration/profile deletion has no independent wall timer. Actual tested cleanup remains bounded; a reachable slow-profile/proc state exceeding the total budget needs measurement (medium if confirmed).

- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-extraction/story-use-playwright-only-when-public-http-evidence-is-insufficien-plan.md`
  summary: DOM allocation precedes size rejection.
  evidence: DOM allocation precedes size rejection. Container memory is capped at 1 GiB; it is unverified whether adversarial allocation kills only Chromium or the worker and loses HTTP evidence. Settle with bounded allocation/OOM observation (high if worker loss confirmed).

- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-extraction/story-use-playwright-only-when-public-http-evidence-is-insufficien-plan.md`
  summary: Provide a compatible supervised Chromium sandbox runtime before enabling public browser fallback in Azure.
  evidence: The deployed worker probe vct-connect-dev-analysis-b5fc458 succeeded but returned RUNTIME_UNAVAILABLE for 1688, Taobao and Alibaba, preserving the original HTTP evidence at 1, 1 and 3 populated fields. PUBLIC_BROWSER_FALLBACK remains False; no sandbox bypass was applied.

- source_plan: `C:/Users/eidel/Desktop/VCT Connect/_bmad-output/initiative-vct-connect-year-one/epic-extraction/story-refactor-sweep-plan.md`
  summary: Resolve static stylesheet cascade order and important priority before marking nodes hidden.
  evidence: Story 2.8 review B4/E6 reproduced visible login walls disappearing for overridden display declarations; the moved helper AST matches the baseline exactly.
- source_plan: `C:/Users/eidel/Desktop/VCT Connect/_bmad-output/initiative-vct-connect-year-one/epic-extraction/story-refactor-sweep-plan.md`
  summary: Resolve inline display declarations in their effective order before pruning visible content.
  evidence: Story 2.8 review E3 reproduced display:none followed by display:block causing a visible login wall to be removed; the ancestor visibility helper is unchanged from baseline.
- source_plan: `C:/Users/eidel/Desktop/VCT Connect/_bmad-output/initiative-vct-connect-year-one/epic-extraction/story-refactor-sweep-plan.md`
  summary: Preserve explicitly visible descendants beneath visibility-hidden ancestors.
  evidence: Story 2.8 review E4 reproduced a visibility:visible child login wall disappearing when its hidden ancestor is pruned; the limitation predates this refactor.
- source_plan: `C:/Users/eidel/Desktop/VCT Connect/_bmad-output/initiative-vct-connect-year-one/epic-extraction/story-refactor-sweep-plan.md`
  summary: Respect stylesheet media applicability when computing static screen visibility.
  evidence: Story 2.8 review E5 reproduced a print-only hiding rule removing screen-visible login content; the stylesheet helper is AST-identical to baseline.
- source_plan: `C:/Users/eidel/Desktop/VCT Connect/_bmad-output/initiative-vct-connect-year-one/epic-extraction/story-refactor-sweep-plan.md`
  summary: Recognize zero percentage opacity when excluding invisible selected evidence.
  evidence: Story 2.8 review E7 reproduced opacity:0% text surviving static pruning; the unchanged stylesheet regex handles numeric zero only.

## Extraction follow-up routing — 2026-10-03

The historical entries above remain their original evidence. The user approved retrospective A1–A6; current execution is consolidated in `initiative-vct-connect-year-one/epic-extraction/tickets.toml` and `retrospective-action-execution.md`:

- Five visibility concerns from the refactor baseline → **2.9 / A1**. Only the correction's regression and adapter/browser evidence can resolve them.
- Decoded response allocation boundary → **2.10 / A2**. Observe allocation before rejection, including cumulative chunks.
- Forced runner death, independently bounded cleanup and DOM allocation failure hypotheses → **2.12 / A4**. Qualification precedes activation; these are not three presumed defects.
- Compatible deployed sandbox runtime → **2.11 / A3**, after 2.12. Current false flag remains; `browser-runtime-decision.md` contains the prepared scope/runtime alternatives.
- Latest-release selected wire payload, popup recovery/result opening and live Taobao shop capture → **2.13 / A5**. `extension-acceptance-checklist.md` records the exact session-dependent journey. Prior item/import acceptance remains valid historical evidence.
- Cross-baseline defect and exact-environment acceptance audit → **2.14 / A6**, applied in `extraction-completion-gate.md`. Ticket labels alone never close required evidence gaps.

The earlier extension-construction item is explicitly resolved above by its implementation evidence. Other source accessibility, coverage expansion and platform API eligibility concerns remain separate; this consolidation does not invent their completion.

## Extraction review follow-ups — first-instance deferrals, 2026-10-04

These entries process the ten held first-instance review deferrals once. Later carried verdicts do not append them again. Ticket 2.15 owns the remaining static/consumer boundaries; 2.12 retains access-lifecycle and memory/restart qualification; 2.13 retains representative capture/loading/field-coverage observations; 2.16 records the existing official-API assessment separately. None is resolved by a built label or a declared unsupported input.

- source_plan: `_bmad-output/implementation-artifacts/plan-extraction-retrospective-actions.md`
  summary: Qualify mixed supported/pseudo selector-list behavior under ticket 2.15.
  evidence: Original B2 independently compared baseline and candidate: both leave a wall visible when a mixed selector rule is discarded; this predates the correction and needs an explicit supported-input decision and consumer evidence.
- source_plan: `_bmad-output/implementation-artifacts/plan-extraction-retrospective-actions.md`
  summary: Qualify Unicode and escaped CSS identifiers under ticket 2.15.
  evidence: Original B3 found the ASCII selector boundary in both baseline and candidate; Unicode/escape hiding is ignored and requires separate selector and source-classification qualification.
- source_plan: `_bmad-output/implementation-artifacts/plan-extraction-retrospective-actions.md`
  summary: Observe transient access walls revealed only by visibility-attribute changes under ticket 2.12.
  evidence: Original B7 identifies the unchanged observer's missing attribute subscription; actual reveal/hide transitions and their observation cost must be qualified before this lifecycle path is accepted.
- source_plan: `_bmad-output/implementation-artifacts/plan-extraction-retrospective-actions.md`
  summary: Establish bounded profile reclamation across worker death/restart under ticket 2.12.
  evidence: Original B9 and the actual outer-worker death gate leave an interrupted profile; the production cleanup slot exists only in memory and the test's independent deletion does not establish restart reclamation.
- source_plan: `_bmad-output/implementation-artifacts/plan-extraction-retrospective-actions.md`
  summary: Finish native browser allocation and durable recovery qualification under ticket 2.12.
  evidence: Original B10's synthetic allocator bypasses normal collection/encoding/reparse. Parent later observed real UTF-8 MemoryError with caller HTTP preservation and a separate durable kernel-OOM/next-browser completion; isolated serialization, reparsing, durable native-fault completion and permanent broader probe registration remain separate open evidence.
- source_plan: `_bmad-output/implementation-artifacts/plan-extraction-retrospective-actions.md`
  summary: Qualify line/block-separated access phrases at static and browser consumers under ticket 2.12.
  evidence: Original E4 found the same missing BR-separated literal phrase classification in baseline and candidate; normalization/layout separation needs independent current-latch and selected-status checks.
- source_plan: `_bmad-output/implementation-artifacts/plan-extraction-retrospective-actions.md`
  summary: Bound or explicitly qualify static CSS matching work under ticket 2.15.
  evidence: R2-B1 measured multiplicative rule/node work in both baseline and candidate (800 broad rules and 1,000 nodes); neither has a work guard and parsing executes before a subsequent fetch deadline check.
- source_plan: `_bmad-output/implementation-artifacts/plan-extraction-retrospective-actions.md`
  summary: Settle ARIA-hidden and HTML-hidden rendering/evidence conventions under ticket 2.15.
  evidence: R2-B2 compared both versions: aria-hidden text and hidden attributes overridden by display:block are unconditionally suppressed; this is an existing convention requiring a documented consumer decision.
- source_plan: `_bmad-output/implementation-artifacts/plan-extraction-retrospective-actions.md`
  summary: Qualify CSS all-shorthand visibility rollback under ticket 2.15.
  evidence: R2-B3 compared display:none;all:initial in both versions and found the same suppression; the shorthand boundary predates the change and needs independent rollback/priority evidence.
- source_plan: `_bmad-output/implementation-artifacts/plan-extraction-retrospective-actions.md`
  summary: Qualify restored visible product links beneath hidden structural shelves under ticket 2.15.
  evidence: R2-B6's Taobao fixture produces no products in both baseline and candidate because shelf discovery excludes the inactive structural container before selecting restored visible descendants.

- source_plan: `_bmad-output/implementation-artifacts/plan-extraction-retrospective-actions.md`
  summary: Unverified medium: synchronous worker process-start-time reads may exceed the attempt budget under a reachable kernel stall.
  evidence: Final edge review identifies browser.py profile-name /proc stat read before supervised launch; settle with actual kernel-delayed read and deadline measurement. Ordinary pseudo-file access and a substituted sleeping function do not establish production reachability.

- source_plan: `_bmad-output/implementation-artifacts/plan-story31-confidence-basis-guidance.md`
  summary: Existing unsupported-score regex can reject qualitative confidence explanations that mention evidence quantities or ordinary number words.
  evidence: Offline synthetic confidence-basis probes using a confidence-label phrase followed by 2 reviews or một phần trigger UNSUPPORTED_SCORE without asserting a numeric score. Prompt guidance v6 avoids the ambiguous construction, but the guard itself remains conservative. A broader validated score-assertion design is separate; missing rejected cloud prose cannot establish historical causes.

- source_plan: `_bmad-output/implementation-artifacts/plan-story31-language-contract-investigation.md`
  summary: Revise the Vietnamese-language contract for short natural clauses and mixed-language boundaries before further live acceptance.
  evidence: Targeted25-case synthetic probe reproduces6 Vietnamese false rejections and2 foreign/mixed false acceptances through both screen_vietnamese and validate_report; existing57 cases still match labels. Small vocabulary and sentence coverage do not establish robust language identification. The missing v7 response's exact cause remains unknown; investigation does not authorize a production threshold change.
- source_plan: `_bmad-output/implementation-artifacts/plan-story31-language-contract-investigation.md`
  summary: Bind foreign quotation exemptions to supplied evidence while preserving legitimate source names and identifiers.
  evidence: unprovided_english_quote passes validate_report with evidence E1 containing no source text because double-quoted content is stripped unconditionally. Independent straight/curly-quote probes reproduce this pre-existing boundary. Source quotation policy and meaningful negative tests must be settled before correction; no guard change in the approved offline investigation.

- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-analysis-intelligence/story-interpret-one-supplier-fixture-through-yescale-plan.md`
  summary: Existing Vietnamese cue-ratio screening can accept foreign fragments padded with Vietnamese prose.
  evidence: Completion review reproduced inline excellent quality and très fiable accepted after ordinary Vietnamese cues; the same heuristic limitation predates this change. A general language-identification contract needs independently labeled evaluation, not a claim of complete foreign-language exclusion.

- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-analysis-intelligence/story-interpret-one-supplier-fixture-through-yescale-plan.md`
  summary: Existing source-quotation exemptions are global rather than bound to a finding's cited evidence.
  evidence: Completion review confirmed a finding citing E1 can quote foreign text present only in E2. The baseline already exempted globally supplied single-quoted source text. Citation membership proves existence, not factual entailment.

- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-analysis-intelligence/story-interpret-one-supplier-fixture-through-yescale-plan.md`
  summary: Existing recursive source-string collection includes structural evidence metadata in quote exemptions.
  evidence: Completion review confirmed quoted delivery_information is exempted when present only as a path. Baseline source-string collection traversed entire evidence entries; restrict future exemption input to source values with meaningful metadata-negative tests.

- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-analysis-intelligence/story-interpret-one-supplier-fixture-through-yescale-plan.md`
  summary: The existing risk-score guard can reject explicit unknown-risk statements followed by source counts.
  evidence: Both baseline guard and completion probe reject Mức rủi ro chưa xác định vì chỉ có 2 đánh giá; the risk branch was preserved in this confidence correction. A separate assertion-aware risk policy must preserve rejection of invented risk scores.

- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-analysis-intelligence/story-interpret-one-supplier-fixture-through-yescale-plan.md`
  summary: Source-attributed confidence-score quotations lack a distinct policy from unsupported report score assertions.
  evidence: The baseline and candidate both reject an exact source quotation containing confidence score 90% before language quotation exemptions. Resolve source-score presentation explicitly rather than exempting numerical confidence assertions silently.

- source_plan: `_bmad-output/initiative-vct-connect-year-one/epic-analysis-intelligence/story-interpret-one-supplier-fixture-through-yescale-plan.md`
  summary: Technical non-Latin units beyond the bounded µm and Ω exceptions remain unsupported by the conservative prose screen.
  evidence: vi-prose.v4 already rejected µg, µF and kΩ; the completion correction is narrowly tested for numeric µm/Ω. Broader unit recognition requires bounded quantity parsing and foreign-prose counterexamples.
