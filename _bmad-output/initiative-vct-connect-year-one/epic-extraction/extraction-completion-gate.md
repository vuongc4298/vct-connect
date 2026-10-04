# Extraction completion gate — ticket 2.14 / A6

Applied on 2026-10-03. This checklist governs reassessment of the full epic. The original retrospective remains a dated baseline, with the current execution record maintained separately.

## Gate rules

1. Identify the candidate full Git revision and deployed backend image digest. Label local, container, database, CI, deployed and live-browser evidence separately. Earlier-image checks cannot qualify a changed image.
2. Walk every original and follow-up ticket, including issues carried forward from earlier baselines. A finding's age or a built/done label does not remove it from the epic's declared criteria.
3. For each confirmed defect, require a baseline-failing regression, a candidate pass at the actual consumer boundary and preservation of valid three-platform evidence/provenance. Audit allocation during decompression and DOM collection, not only rejection after allocation.
4. For runtime hypotheses, record an actual fault probe, environment/resource controls, elapsed time, descendant/profile outcome and retained HTTP evidence. Distinguish a demonstrated defect, a qualified path and an untested path. Skipped tests do not satisfy a row.
5. For each declared criterion below, cite current evidence and state pass, fail, pending or explicitly deferred. A scope deferral needs the product owner's decision and preserves its outstanding activation/manual gates. Only that decision can change the declared acceptance scope.
6. Reconcile duplicate/superseded entries in `implementation-artifacts/deferred-work.md`. Give each surviving extraction concern one follow-up ticket, without deleting its historical source. Resolve it only after its observable verification passes.
7. Reject full acceptance while a criterion has an unresolved defect, an unqualified required capability or a pending required live check. Record any human acceptance override explicitly. Build completion and epic acceptance are separate states.

## Criterion evidence table

| Declared criterion | Required evidence | Current baseline |
| --- | --- | --- |
| 1. Three-platform deployed result or correct explicit status | Candidate deployed queue completion, owner poll, foreign-owner denial, truthful snapshot/status | Historical retrospective probe demonstrates bounded representative forms; candidate deployment pending |
| 2. HTTP first; bounded justified browser fallback; access guidance | A1/A2 regression and adapter gates; A4 fault qualification; A3 exact-image deployed browser qualification | Current image qualifies 418 browser/supervision cases, sixteen database cases and one kernel OOM; final review completed and confirmed blockers corrected. Remaining native/lifecycle qualification is explicit. Deployed enrichment remains required and disabled |
| 3. Versioned raw/normalized provenance and replay | Candidate parity/replay and persisted ownership/immutable provenance checks | Current backend passes 1319 cases with 261 explicit gates; current-image ownership/replay checks pass. Final unified review completed with confirmed defects corrected and explicit deferred boundaries. Deployed criterion evidence remains pending |
| 4. Credential-free deduplicated extension merge | Candidate schema/merge/database checks plus A5 latest-release selected wire payload, result opening and live shop capture | Prior item/import acceptance retained; current live session unavailable |

## Action inventory

| Action | Ticket | Completion evidence / remaining prerequisite |
| --- | --- | --- |
| A1 effective screen visibility | 2.9 | Five reproductions, priority/inheritance/media/opacity boundaries and valid adapters |
| A2 bounded decompression | 2.10 | Observed output allocation bound, supported compression/hash and malformed-input gates |
| A4 cleanup/allocation qualification | 2.12 | Actual forced death, slow cleanup and allocation failure; preserve HTTP and worker |
| A3 deployed runtime reconciliation | 2.11 | [Recorded runtime decision](browser-runtime-decision.md); user retained deployed enrichment required on 2026-10-04; exact-image deployed qualification remains |
| A5 signed-in extension acceptance | 2.13 | [Concrete acceptance checklist](extension-acceptance-checklist.md); connected accessible source session |
| A6 completion process | 2.14 | This gate, mapped follow-ups and superseded inventory; reassessment retains unresolved rows |

## Surviving concern ownership

| Concern group | One current follow-up owner | State / verification boundary |
| --- | --- | --- |
| Original five visibility defects | 2.9 | Implemented; final review and corrected current-image integration complete |
| Decoded allocation, valid compression/provenance | 2.10 | Implemented; final review/current-image integration complete |
| Runner/namespace death, deadlines, output, allocation, restart profiles | 2.12 | Required qualification remains in progress; measured pass and unobserved path are recorded separately |
| Attribute-only transient walls and line/block-separated access phrases | 2.12 | Attribute observation is implemented in newer source; coherent inline/line/block handling and current runtime verification belong to loop 4. CSSOM-only transient visibility and broader lifecycle qualification remain open |
| Unsupported/pseudo selector lists, Unicode/escapes, all shorthand, hidden/ARIA convention, restored structural shelves, CSS work | planned 2.15 | CSS-work bounding is implemented in newer source, with explicit failure propagation under loop-4 correction. Other static/consumer boundaries still need refinement and observed outcomes; unsupported is not resolved |
| Exact-image deployed browser gain/preservation and accessible live-source queue evidence | 2.11 | Host/release decision and actual deployed qualification pending |
| Selected wire privacy, merge/deduplication, popup recovery, result opening, live shop capture, loading/representative field coverage | 2.13 | Available automated support recorded; connected live source session pending |
| Prior official 1688 API eligibility/permitted field assessment | planned 2.16 | Human developer-portal access and a separate future decision; no API implementation or scope waiver |
| Prior extension construction | historical 2.6 / resolved | Source evidence retained; latest-release/live acceptance belongs to 2.13 |

The additional planned entries record existing concerns for A6; they do not broaden the six current implementation actions or close their evidence gates. The one-owner inventory preserves original deferred entries and source findings.

## Reassessment record

Full-epic acceptance: **pending remediation / rejected at the retrospective baseline**. No automatic acceptance is implied by applying proposals, finishing a local fix or passing an automated suite. Record candidate results and review decisions in [action execution](retrospective-action-execution.md).

References: [epic criteria](epic-extraction.md), [retrospective findings and baseline evidence](epic-extraction-retrospective.md), [ticket breakdown](tickets.toml).


Loop-4 current qualification: four review blockers corrected; 1,287 backend passes after ACL-only setup retry, 72 frontend passes/typecheck, 395 distinct actual Linux browser/supervision passes after fault-injection correction, sixteen database browser passes and one kernel OOM pass. Final packaged image `sha256:26bd283edc8ab2940ef417ca1dcc694eaafa9aeef7bb24529426d32a3bdf39cd` differs from the fully exercised production image only in the corrected supervision test; production hashes are identical. Historical tables above preserve previous checkpoints. Unified review remains pending; deployed enrichment, broader native-allocation/lifecycle boundaries, and live extension acceptance remain pending.


### Final patch verification checkpoint — 2026-10-05

All three surviving final-review patch groups are corrected. Focused local covering checks passed 400 cases (256 gated skips). Full latest backend passed 1,230 cases with 350 explicit runtime/database skips, zero failures/errors (75.09 s); frontend remains unchanged from 72 passes and successful typecheck. Original implementer was unavailable after interruption; parent applied the workflow fallback. Final source hashes are in `tmp/retro-final4-patched-results/final-source-checkpoint.json`. Docker startup now fails on an inaccessible dockerInference socket; a preserving rename failed with the same Windows error. No factory reset, container-data deletion, reinstall or configuration change was performed. Final immutable build/hash/browser/database/OOM verification is unrun for the latest metadata/layout patches. Earlier image passes are historical, not latest acceptance. Plan remains in-review and uncommitted; operational/manual gates remain pending. Details: `tmp/retro-final4-patched-results/runtime-blocker.md`.


### Final current-image qualification — 2026-10-05

Docker restoration resolved the environmental blocker. Final immutable image `sha256:72048fe1f718859df17daf1b7573e480b19724ed9c62c3646771424fcfa15048` matches all fourteen packaged hashes and UID10001. Whole backend: **1319 passed, 261 gated skips**, no failures/setup errors. Actual Linux browser/supervision: **418 distinct passing cases**; initial failed cases, if any, passed unchanged in isolated rerun under the same controls: `['backend.tests.test_browser_fallback::test_actual_chromium_gain_for_all_platforms[1688]', 'backend.tests.test_browser_fallback::test_actual_five_screen_cases_through_wrapper_and_latch[<style media="print">.runtime-wall{display:none}</style>-<p class="runtime-wall">WALL</p>-AUTH_REQUIRED-1688]', 'backend.tests.test_browser_fallback::test_actual_five_screen_cases_through_wrapper_and_latch[<style media="print">.runtime-wall{display:none}</style>-<p class="runtime-wall">WALL</p>-AUTH_REQUIRED-TAOBAO]', 'backend.tests.test_browser_fallback::test_actual_five_screen_cases_through_wrapper_and_latch[<style media="print">.runtime-wall{display:none}</style>-<p class="runtime-wall">WALL</p>-AUTH_REQUIRED-ALIBABA]', 'backend.tests.test_browser_fallback::test_actual_five_screen_cases_through_wrapper_and_latch[<style>.runtime-wall{opacity:0%}</style>-<p class="runtime-wall">WALL</p>-None-1688]', 'backend.tests.test_browser_fallback::test_actual_five_screen_cases_through_wrapper_and_latch[<style>.runtime-wall{opacity:0%}</style>-<p class="runtime-wall">WALL</p>-None-ALIBABA]']`. Both original and retry artifacts remain. Database browser ownership/provenance/faults: **16 passed**. Kernel OOM: **1 passed**. Frontend source is unchanged from 72 passing tests and successful typecheck. Raw current-image artifacts are in `tmp/retro-final4-patched-results/`. Source was frozen throughout qualification; no source overlay or security/resource waiver was used.

Four independent review lenses completed; each finding was classified before grouping. All confirmed current-change blockers are corrected, including final top-level/inline metadata representability, multi-keyword layout text and live-profile protection regressions. Existing native allocation/lifecycle/registration/shared-cgroup and static consumer boundaries stay tracked; the new synchronous-proc-read hypothesis is explicitly deferred as unverified medium. No skipped/previous-image case establishes current qualification. Full epic acceptance, compatible deployed enrichment and latest live extension wire/shop/result acceptance remain pending; deployed fallback remains disabled. Build completion is local remediation and review, not operational acceptance.
