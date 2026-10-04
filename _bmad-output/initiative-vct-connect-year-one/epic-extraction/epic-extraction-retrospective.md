---
epic: epic-extraction
date: 2026-10-03
verdict: rejected
criteria: declared
headless: false
---

# Extraction epic retrospective

Completed evidence review of the extraction implementation through `50c9f37`. Machine verdict: **rejected** for full epic acceptance, with six proposed action items. The deployed three-platform path works; confirmed access-classification defects remain unresolved. Existing approvals to release individual stories and defer manual/runtime work are preserved; they do not explicitly accept the full epic against every declared criterion.

## Epic summary

Selected epic: `epic-extraction` (initiative epic 2). Ticket status check: 2.1–2.5 are built/review; 2.6–2.8 are done/done. No unfinished tickets (`pending_tickets: []`). Built tickets remain subject to human closure.

The user reported no particular concern to weight. The declared R4 criteria govern this assessment.

| Ticket | Build order and status | Plan baseline → next baseline |
| --- | --- | --- |
| 2.1 | 1688 contract/extraction; built/review | `a0265a1..e3c5a4a` |
| 2.2 | Failure classification/retries; built/review | `e3c5a4a..499d255` |
| 2.3 | Taobao adapter; built/review | `499d255..e452afd` |
| 2.4 | Alibaba adapter; built/review | `e452afd..374dfc8` |
| 2.5 | Public browser fallback; built/review | `374dfc8..1d31eac` |
| 2.6 | Extension merge; done/done | `1d31eac..51810d1` |
| 2.7 | Layout verification/raw replay; done/done | `51810d1..90bead7` |
| 2.8 | Shared helper refactor; done/done | `90bead7..50c9f37` |

Baselines are recorded in the corresponding eight `story-*-plan.md` frontmatters; each ancestor relationship was checked. The final endpoint is inferred from HEAD `50c9f37df40476c8be22f1a49af745e0a4e120e8`, the extraction release closeout. No later implementation commit was found. Ranges 2.1 and 2.3 also include explicitly recorded saved-page/extension recovery follow-ups. Range attribution does not imply those follow-ups were part of the original frozen ticket intent.

Inventory: epic file and parent initiative R4 read; all eight `tickets.py find` entries resolved; all eight plans available, including triage, verification, change logs and the dated 2.3 follow-up review. Every `story_file` is null. Additional evidence includes the Taobao/Alibaba sample audits, recovery plans, tracked deferred-work record, sanitized fixtures, source and tests, three merge commits, and local sanitized deployed outcome/image-probe records. The configured `planning-artifacts` folder is absent, so PRD/architecture comparison is limited to the epic, initiative and existing code conventions. No previous foundation retrospective exists. No conversation transcripts were loaded; process analysis is limited to explicit plan/build records, without inferring why undocumented session decisions occurred.

The required `git_evidence.py` pre-pass failed with Git dubious-ownership errors under both sandbox and approved execution. It intentionally removes `GIT_*` environment overrides. No Git configuration was changed. Deterministic fallback used native Git with a command-scoped safe.directory for this exact repository: commit ranges, ancestor checks, non-merge numstat aggregation and final diff. The union contains 27 commits, including three merges (`c7ef8c5`, `0cba680`, `b0eec86`); final net diff: 98 files, 21,527 insertions and 839 deletions. Non-merge volume is kept separate from final net differences and merge changes. Binary-revision completeness from the failed helper is unavailable.

The bmad-review input is the staged unified diff at `C:/Users/eidel/AppData/Local/Temp/vct-extraction-retro-bgdeovpq.diff` (temporary review input; source of record is the Git range above). Review lenses are adversarial, edge-case-hunter and verification-gap. Subagent tooling is unavailable; the lenses run sequentially with scope focused on transport, access classification, shared DOM/coverage helpers, extension merge, replay, API/worker wiring and release verification. No exhaustive claim is made for every line of the 98-file diff or unseen source layouts.

## Findings

### Aggregate views

**Architecture delta and duplication.** The epic adds 15 extraction modules. The AST-derived relative-import graph has no cycle in that package. Shared transport is in `fetch.py`; JSON/scalar readers in `evidence.py`; DOM/access mechanics in `dom.py`; coverage/status assembly in `contracts.py`. The three adapters call the shared fetch path, and the worker dispatches by canonical platform (`backend/worker/main.py:33`). Replay still imports platform-specific binding/selection helpers from Taobao and Alibaba; this is explicit reuse of their audited contracts, not an independently demonstrated layering defect (`backend/app/extraction/renormalize.py`, imports and `renormalize_public_fields:447`). This analysis covers imports in the extraction package and changed API/storage/worker entry points; it is not a repository-wide dependency audit.

**Size and churn.** Non-merge added/deleted/net lines: `offer1688.py` 670/404/+266; `alibaba.py` 567/38/+529; `taobao.py` 483/118/+365; `renormalize.py` 518/12/+506; `storage.py` 388/136/+252. Current sizes are respectively 266, 529, 365, 506 and 822 lines; storage started at 570. The largest added artifact is the 6,163-line test baseline, followed by dependency-lock churn. These measurements identify maintenance surfaces, not god classes: adapters own their layouts, replay owns retained-field validation, and storage owns transactions. No size-based defect is asserted. Merge first-parent deltas were inspected separately: 2.6 9 files/+538/−2, 2.7 11 files/+1,312/−15, 2.8 19 files/+6,919/−267; these are not added to non-merge churn. Sources: the eight ranges above, especially `eefbfe0`, and AST/line-count measurements in this run.

**Pattern divergence retained intentionally.** HTTP/replay coverage treats None, empty strings and empty lists as absent; extension coverage preserves the legacy non-None predicate; browser gain additionally excludes empty dictionaries (`backend/app/extraction/contracts.py:25`, `:30`; `browser.py:41`). The refactor names those policies instead of silently changing outcomes. Disposition: **accept as-is** for compatibility, with no upstream change proposed in this retrospective. Coverage is a field-presence measure, not proof of evidence quality. Sources: `story-refactor-sweep-plan.md:140`; `backend/tests/test_extension_merge.py:62`; `test_refactor_parity.py:198`. The fresh selected tests pass.

**Verified wins.** Shared status/provenance survives the deployed queue; unauthorized capture/import and foreign guest polling are rejected. Merge has explicit same-source checks and immutable baseline provenance (`extension_merge.py:71`; `storage.py:484`), with repeated-capture bounds and source-label tests (`test_extension_merge.py:103`, `:129`, `:148`). Replay rejects incompatible revisions/nested fields, preserves source capture metadata and states `retained_public_fields_only` (`renormalize.py:447`; `test_renormalize.py:40`, `:51`, `:181`). The 41-case parity fixture has case-set and LF/CRLF assertions (`test_refactor_parity.py:154`, `:167`, `:175`), avoiding silent loss of a golden case. Original complete HTML is not retained; replay cannot recover fields missed by an earlier selector. This is an explicit accepted scope limit, not a missing full-page archive requirement.

### Consolidated findings and routing

Each finding has an instance disposition and a prevention lesson. Findings F4–F6 establish missing qualification evidence, **not** a demonstrated orphan, deadline overrun or worker OOM. Their existing deferrals are preserved.

| ID | Evidence and implication | Instance disposition | Prevention |
| --- | --- | --- | --- |
| F1 | Five shared CSS visibility defects remain across adapter/access-wall consumers. Overridden stylesheet hiding, `display:none;display:block`, visible descendants of visibility-hidden parents, and print-only styles each make `browser.access_wall` return None for screen-visible `Please sign in`. Stylesheet `opacity:0%` instead returns AUTH_REQUIRED for invisible text. All five were reproduced in this run. Sources: `backend/app/extraction/dom.py:59`, `:83`, `:90`; `browser.py:100`; `story-refactor-sweep-plan.md:93`–`:99`; `../../implementation-artifacts/deferred-work.md:87`–`:101`. These defects existed before 2.8, but were introduced during this epic and survive its refactor. They can suppress real access barriers or introduce false ones. | **fix now**, A1; blocks full acceptance of criterion 2. No claim of credential bypass or observed external-source exploitation. | A6: epic acceptance must examine surviving defects across ticket baselines; parity with a defective earlier ticket is insufficient. |
| F2 | The shared fetcher calls HTTPX `iter_bytes()` before checking the 2 MB capacity. A 2,942-byte gzip response yielded one 3,000,000-byte decoded chunk in this run. The cap rejects accumulated data after decompression allocation. Sources: `backend/app/extraction/fetch.py:220`–`:230`; 2.2 plan Review Triage Log, Blind 9; `../../implementation-artifacts/deferred-work.md:64`. No compressed-response allocation regression was found by the scoped source/test search. | **fix now**, A2. The reproduced defect concerns allocation timing, not successful persistence of an oversized page. | A6: resource gates must observe allocation boundaries, not only final rejection codes. |
| F3 | Browser enrichment is inactive in the Azure worker. The recorded deployed probe returned RUNTIME_UNAVAILABLE for all platforms, preserving HTTP fields; latest release retains `PUBLIC_BROWSER_FALLBACK=False`. Sources: 2.5 plan Release Closeout at `:127`; 2.8 plan `:153`; `backend/app/config.py:34`; `backend/worker/main.py:40`; `infra/azure/main.bicep:12`. Local Chromium success does not establish deployed enrichment. | **defer**, consistent with the recorded runtime decision; A3 proposes a compatible runtime or an explicit epic-scope reconciliation. Disablement is not itself a new defect, and this finding alone does not force rejection. | Resolve runtime availability before claiming deployed fallback coverage; scope changes require a human decision. |
| F4 | Abrupt runner death/reparenting remains unqualified. Existing actual cleanup test exercises an infinite script, an approximately 2 MB DOM and a conflicting field; it does not forcibly kill the runner before descendant discovery. Sources: `backend/app/extraction/browser.py:132`; `backend/tests/test_browser_fallback.py:290`–`:321`; 2.5 triage B5. Repo source/test search for kill_tree/reparent/forced termination found no covering fault-injection test. | **defer**, A4 before browser activation; orphan survival remains an open hypothesis. | Test the process-lifetime boundary using actual descendants, rather than treating normal cleanup as proof for abrupt parent death. |
| F5 | Cleanup reserves 0.5 seconds, while process enumeration and temporary-profile deletion lack an independent wall-clock guard. The existing normal-resource cleanup assertion is under 11 seconds; no slow-profile/proc-state fault was found in the searched tests. Sources: `browser.py:132`, `:188`–`:214`; `test_browser_fallback.py:297`; 2.5 triage B6. | **defer**, A4; no over-budget cleanup was observed in this retrospective. | Qualify cleanup separately from source execution and define the supervisor's enforcement boundary. |
| F6 | DOM serialization/allocation precedes output-size rejection. The 1 GiB container gate and 2,000,001-character test verify one bounded case, not worker behavior under memory exhaustion. Sources: `backend/app/extraction/browser_runner.py:196`–`:211`; `.github/workflows/ci.yml:59`; `test_browser_fallback.py:293`; 2.5 triage B7. No OOM qualification test was found by the scoped search. | **defer**, A4; worker-loss/OOM remains unproven. | Observe which process fails and whether original HTTP evidence survives an allocation failure before activation. |
| F7 | Current merged extension behavior has strong deterministic/owner-store checks but no recorded completed signed-in network inspection on the latest released build. Earlier 1688 capture and Taobao item capture/import were accepted; live Taobao shop capture was explicitly deferred. Sources: 2.8 plan `:156`; recovery plan User browser capture, saved-product and Shop HTML checkpoints; `frontend/apps/extension/src/capture.test.ts:20`, `:134` (simulated DOM); `test_extension_merge.py:20`, `:103` (merge/provenance assertions). These checks do not establish the current Chrome-to-deployed-merge journey or its actual wire payload. | **defer**, preserving the user's earlier manual deferral; A5. This is a verification limit, not a claim that credentials are transmitted. | Distinguish source DOM selection, signed-in wire payload and persisted merge assertions in release evidence. |

### Review-lens record

The adversarial pass identified eleven concrete improvements/qualification gaps: the five F1 cases separately, F2, F3, F4, F5, F6 and F7. The edge-case pass independently retained the five F1 branches and F2's decoded-chunk boundary. The verification-gap pass retained the F2 resource-verification boundary, F4–F6 unqualified runtime faults and F7 current-client release boundary. Overlap is preserved below; the consolidated table above deduplicates remediation.

No additional proven ownership, deduplication or replay regression survived the scoped inspection and fresh targeted verification. Handled paths were dropped: extra/secret-shaped capture keys, mismatched page identity, foreign owners, duplicate-only merges, source revisions, raw nested-field selection, ordinary redirect/deadline failures and failed-source outcomes have explicit guards/assertions. This does not assert exhaustive verification of unseen platform layouts.

Canonical review findings (no severity/ranking; lens overlaps are intentional):

```json
[
  {"lens":"adversarial","location":"backend/app/extraction/dom.py:90","trigger_condition":"Overridden stylesheet hiding suppresses a visible access wall","guard_snippet":"Resolve effective cascade and important priority before pruning","potential_consequence":"A visible login wall is omitted from classification"},
  {"lens":"adversarial","location":"backend/app/extraction/dom.py:59","trigger_condition":"Inline display:none followed by display:block remains classified as hidden","guard_snippet":"Resolve effective inline display declaration","potential_consequence":"A visible login wall is omitted from classification"},
  {"lens":"adversarial","location":"backend/app/extraction/dom.py:83","trigger_condition":"Pruning a visibility-hidden ancestor also removes its visible descendant","guard_snippet":"Preserve explicitly visible descendants","potential_consequence":"A visible login wall is omitted from classification"},
  {"lens":"adversarial","location":"backend/app/extraction/dom.py:90","trigger_condition":"Print-only stylesheet hiding is applied to screen content","guard_snippet":"Respect stylesheet media applicability","potential_consequence":"A screen-visible login wall is omitted from classification"},
  {"lens":"adversarial","location":"backend/app/extraction/dom.py:109","trigger_condition":"Stylesheet opacity:0% is not treated as invisible","guard_snippet":"Handle percentage-zero opacity consistently","potential_consequence":"Invisible text produces a false access failure"},
  {"lens":"adversarial","location":"backend/app/extraction/fetch.py:220","trigger_condition":"Automatic decompression allocates a chunk beyond the page limit","guard_snippet":"Bound decoded output before allocation crosses the budget","potential_consequence":"Compressed content exceeds the intended memory bound"},
  {"lens":"adversarial","location":"story-use-playwright-only-when-public-http-evidence-is-insufficien-plan.md:127","trigger_condition":"Deployed runtime cannot execute browser enrichment","guard_snippet":"Qualify a compatible supervised runtime or reconcile epic scope","potential_consequence":"Local browser gains do not reach deployed users"},
  {"lens":"adversarial","location":"backend/app/extraction/browser.py:132","trigger_condition":"Abrupt runner death has no recorded descendant qualification","guard_snippet":"Force runner termination and observe descendant cleanup","potential_consequence":"An orphan-process risk remains unqualified"},
  {"lens":"adversarial","location":"backend/app/extraction/browser.py:188","trigger_condition":"Slow cleanup has no independent wall-clock qualification","guard_snippet":"Measure cleanup faults and enforce the supervisor boundary","potential_consequence":"The total browser deadline remains unqualified under cleanup faults"},
  {"lens":"adversarial","location":"backend/app/extraction/browser_runner.py:196","trigger_condition":"Allocation-failure worker survival has no recorded qualification","guard_snippet":"Observe bounded memory pressure and preservation of HTTP evidence","potential_consequence":"The worker-loss hypothesis remains unresolved"},
  {"lens":"adversarial","location":"story-refactor-sweep-plan.md:156","trigger_condition":"Latest merged release lacks completed signed-in extension network acceptance","guard_snippet":"Inspect selected wire payload and persisted same-owner merge","potential_consequence":"Current client-to-deployed-merge compatibility remains unverified"},
  {"lens":"edge-case-hunter","location":"backend/app/extraction/dom.py:90","trigger_condition":"Stylesheet display hiding is subsequently overridden","guard_snippet":"resolve_effective_cascade_before_pruning()","potential_consequence":"Visible access wall is removed"},
  {"lens":"edge-case-hunter","location":"backend/app/extraction/dom.py:59","trigger_condition":"Inline display:none is subsequently overridden","guard_snippet":"resolve_effective_inline_display()","potential_consequence":"Visible access wall is removed"},
  {"lens":"edge-case-hunter","location":"backend/app/extraction/dom.py:83","trigger_condition":"Hidden ancestor contains an explicitly visible descendant","guard_snippet":"preserve_visible_descendants()","potential_consequence":"Visible access wall is removed"},
  {"lens":"edge-case-hunter","location":"backend/app/extraction/dom.py:90","trigger_condition":"Hiding stylesheet applies only to print media","guard_snippet":"if not applies_to_screen(style): continue","potential_consequence":"Screen-visible access wall is removed"},
  {"lens":"edge-case-hunter","location":"backend/app/extraction/dom.py:109","trigger_condition":"Stylesheet opacity is zero percent","guard_snippet":"normalize_opacity_percentage_before_comparison()","potential_consequence":"Invisible text creates a false access wall"},
  {"lens":"edge-case-hunter","location":"backend/app/extraction/fetch.py:220","trigger_condition":"One compressed response expands beyond the decoded byte budget","guard_snippet":"decode_with_remaining_output_limit()","potential_consequence":"Allocation exceeds the intended cap before rejection"},
  {"lens":"verification-gap","location":"backend/app/extraction/fetch.py:220","trigger_condition":"Size rejection checks do not observe decompression allocation","guard_snippet":"Assert bounded decoded chunk allocation from compressed input","potential_consequence":"Post-allocation rejection stays green despite excess allocation","gap_shape":"regression-gap","consumer":"shared bounded_extract used by all three adapters","evidence":"Read the shared fetch path; scoped repo gzip/decompress searches found no regression; fresh 2942-byte gzip produced a 3000000-byte chunk"},
  {"lens":"verification-gap","location":"backend/app/extraction/browser.py:132","trigger_condition":"Existing cleanup test does not inject abrupt runner death","guard_snippet":"Force parent death before discovery and assert no surviving descendants","potential_consequence":"Normal cleanup passes without qualifying reparented descendants","gap_shape":"regression-gap","consumer":"render_cached process supervision","evidence":"test_browser_fallback.py:290-321 covers infinite script, DOM limit and conflict, not forced runner termination; scoped source/test search found no such case"},
  {"lens":"verification-gap","location":"backend/app/extraction/browser.py:188","trigger_condition":"Existing deadline assertion does not inject slow cleanup","guard_snippet":"Observe supervisor deadline under slow profile/proc cleanup","potential_consequence":"Normal cleanup passes without qualifying total-budget faults","gap_shape":"regression-gap","consumer":"render_cached cleanup boundary","evidence":"Read test_browser_fallback.py:297 and browser.py cleanup; scoped slow-cleanup/profile search found no fault-injection case"},
  {"lens":"verification-gap","location":"backend/app/extraction/browser_runner.py:196","trigger_condition":"DOM-limit test does not observe allocation-failure worker survival","guard_snippet":"Verify original HTTP evidence survives an observed allocation failure","potential_consequence":"Output rejection passes while worker-loss risk stays unqualified","gap_shape":"regression-gap","consumer":"browser_runner DOM serialization and worker result retention","evidence":"test_browser_fallback.py:293 allocates 2000001 characters; CI caps container at 1 GiB; scoped OOM/allocation search found no qualification test"},
  {"lens":"verification-gap","location":"frontend/apps/extension/src/capture.ts:44","trigger_condition":"Latest signed-in wire-to-deployed-merge acceptance remains deferred","guard_snippet":"Inspect selected JSON transmission and owner-scoped merged snapshot","potential_consequence":"Synthetic DOM and merge tests cannot establish current Chrome deployment compatibility","gap_shape":"regression-gap","consumer":"Chrome Capture this page to deployed capture endpoint","evidence":"Read simulated-DOM capture.test.ts:20/134 and merge/provenance assertions at test_extension_merge.py:20/103; latest release plan:156 explicitly leaves signed-in network acceptance open"}
]
```

## Behavior verification

### Fresh deployed exercise in this retrospective

Executed three bounded guest submissions against the existing development web deployment, followed by owner polling and a separate guest's polling attempt. The actual API, queue, worker and persistence path ran; this is distinct from deterministic tests. Results from this run:

| Platform | Analysis ID | Owner poll / completed result | Snapshot | Foreign poll |
| --- | --- | --- | --- | --- |
| 1688 | `b33ab75e-125e-4f34-a76e-3c044175d088` | 200; COMPLETED; BLOCKED / ACCESS_CHALLENGE; 1 attempt; PUBLIC_HTTP | absent | 404 |
| Taobao | `1a43fcce-bffa-46ef-8de0-b9f9a0f8bd5b` | 200; COMPLETED; BLOCKED / ACCESS_CHALLENGE; 1 attempt; PUBLIC_HTTP | absent | 404 |
| Alibaba | `9ce396d2-80b3-462e-90c7-2f8d5d3ca5d4` | 200; COMPLETED; PARTIAL; 1 attempt; PUBLIC_HTTP | present | 404 |

URLs: the representative 1688 offer `996518024136`, Taobao item `1076425861755`, and Alibaba product `1600147809763` named in the sample audits and latest release smoke. Unauthenticated capture and import each returned 401. Only status/provenance/count metadata was printed; credential or source-session material was not logged. The observed Alibaba PARTIAL result differs from the earlier BLOCKED outcome recorded in `tmp/story28-deployed-outcomes.json`; source access varies. The fresh observation is the current evidence, and neither result supports a guaranteed future accessibility claim. Exact field coverage and independent audit of the fresh Alibaba values were not performed.

These checks created three normal guest analysis records in the development service. No deployment or service configuration was changed. A rendered client click-through, signed-in capture, wire-payload inspection and actual Chromium execution were not performed in this run.

### Fresh deterministic checks and reproductions

Command: `.venv/Scripts/python.exe -m pytest backend/tests/test_refactor_parity.py backend/tests/test_extension_merge.py backend/tests/test_renormalize.py -q -p no:cacheprovider`, with bytecode writing disabled. **215 passed in 3.05 seconds.** This covers the recorded outcome cases, selected-text/secret guards, merge bounds/provenance and raw replay validation. It does not replace a database-backed merge exercise or actual Chromium qualification; prior release evidence records those separately.

Direct F1 reproduction called `backend.app.extraction.browser.access_wall` with an ordinary Product title and `Please sign in` body content in these five wrappers:

| Wrapper | Expected screen classification | Observed |
| --- | --- | --- |
| `.wall{display:none}.wall{display:block}` with `.wall` div | AUTH_REQUIRED | None |
| div `style="display:none;display:block"` | AUTH_REQUIRED | None |
| `visibility:hidden` div with `visibility:visible` child | AUTH_REQUIRED | None |
| `style media="print"` hiding `.wall` div | AUTH_REQUIRED | None |
| stylesheet `.wall{opacity:0%}` | None | AUTH_REQUIRED |

F2 reproduction: `compressed = gzip.compress(b'A' * 3000000)`; `httpx.Response(200, headers={'content-encoding':'gzip'}, stream=httpx.ByteStream(compressed))`; `len(next(response.iter_bytes()))`. Observed 2,942 compressed bytes and a 3,000,000-byte first decoded chunk, versus `MAX_HTML_BYTES=2_000_000`. This is a safe, finite local reproduction of allocation preceding the application's size guard.

### Existing evidence, explicitly reported rather than rerun here

Latest release plan `story-refactor-sweep-plan.md:138`–`:155` records final backend 850 passed/32 skipped, actual browser union of 78 passing cases after isolated retries, 12 actual Chromium queue cases, successful PR/main CI and development deployment, and an 82-test probe in the deployed image. The local `tmp/story28-image-probe-results.json` independently contains `82 passed in 0.65s` and `VCT_STORY28_PROBE result=0`. The release logs distinguish 31 browser cases run separately and the opt-in Azure Service Bus skip. Existing browser deadline flakes under concurrent load are disclosed in the plan; no claim of a fresh full-suite or Chromium pass is made here. Hosted run links were read from the release records; remote CI histories were not re-fetched.

The Taobao recovery plan records real user item capture (4/12 fields/four reviews), saved item import (6/12/two reviews), and saved shop import (4/12/20 products), with source-byte hashes; live shop extension capture remains explicitly deferred. The 1688 extension plan records the earlier accepted signed-in capture at 25% coverage and a subsequently added auto-open flow without a separately observed final Chrome run. These are existing acceptance records, not observations made in this retrospective.

## Previous-retro follow-through

The preceding epic in `tickets.py status` order is `epic-platform-foundation`. Its expected `epic-platform-foundation-retrospective.md` is absent from the inventoried folder. There is no previous retrospective action section to audit; this is missing historical evidence, not evidence of no outstanding foundation work. The separate deferred-work file was inspected for extraction follow-ups and provides the F2–F7 sources above.

## Action items

At the original assessment, all six items were **proposed**, with role owners because the epic/tickets contain no named assignee. The user subsequently approved applying them and proceeding on 2026-10-03. They are now tracked as tickets 2.9–2.14; see the [current execution record](retrospective-action-execution.md) for fixes, measurements, supporting checks and remaining human/runtime prerequisites. This dated assessment preserves its original evidence and acceptance verdict.

| ID | Proposed action and observable completion | Owner | Routing |
| --- | --- | --- | --- |
| A1 | Correct shared effective visibility for the five F1 cases, preserving valid platform layouts. Add regression assertions for screen-visible access walls and invisible text at helper and affected adapter/fallback boundaries; verify actual access status and absence of inappropriate snapshots. | Extraction developer; QA reviewer | fix now; F1 |
| A2 | Bound decompression output before oversized decoded allocation; preserve response-byte/provenance policy, finite retries and the 2 MB retained-body limit. Verify compressed input, repeated chunks, terminal rejection and preservation of worker results. | Backend transport developer | fix now; F2 |
| A3 | Propose and qualify a compatible supervised Chromium runtime before enabling fallback, with an exact-image deployed gain/preservation probe; alternatively submit an explicit human-approved reconciliation of the full epic's fallback scope. Preserve the current disabled setting until qualification. | Platform architect and product owner | deferred remediation or proposed spec reconciliation; F3 |
| A4 | Before browser activation, qualify abrupt runner death, slow cleanup and allocation failure under the existing resource/sandbox limits. Observe descendants, supervisor deadline, worker survival and retained HTTP evidence; convert demonstrated defects into normal development fixes. | Runtime engineer and QA reviewer | deferred qualification; F4–F6; not three presumed bugs |
| A5 | When the user's source session is available, resume latest-release signed-in extension acceptance: selected-only network JSON, owner-scoped merge/deduplication/provenance, result opening and live Taobao shop capture. Preserve prior item/import acceptances and the explicit manual deferral. | QA/release reviewer, coordinating with the user's source session | deferred operational check; F7 |
| A6 | Propose an epic completion gate that checks unresolved defects across ticket baselines, deployed capability versus local gates, and allocation boundaries; consolidate superseded extraction follow-ups with evidence rather than relying on built/done labels alone. The deferred-work extension-build item is superseded by the implemented capture/merge path, while runtime/manual/resource items remain open. | Engineering lead / ticket owner | process proposal; F1–F3 and inventory evidence |

A1 and A2 address confirmed defects. A3–A5 retain known deferrals and do not authorize runtime activation or require the user to perform manual checks during this run. A6 is motivated by concrete records: the same five CSS defects were deferred as pre-refactor behavior in 2.8 despite being part of this epic's final access classifier; `deferred-work.md:49` still proposes extension construction even though `storage.py:484` and the 2.6 done plan demonstrate it landed. No undocumented session root cause is inferred.

## Acceptance verdict

**rejected** — criteria **declared**. This is the machine assessment of the full epic; no human full-epic acceptance override has been supplied. It is **not accepted** under the current criteria while F1 remains unresolved. Ticket completeness does not force this verdict: `pending_tickets` is empty, and built tickets count as finished in this workflow.

| Declared Done when criterion (`epic-extraction.md:26`–`:31`) | Assessment |
| --- | --- |
| 1. Representative URLs from all platforms yield a snapshot or correct explicit status in the deployed path. | Demonstrated for the bounded representative forms: fresh 1688/Taobao blocked completions and Alibaba PARTIAL snapshot, with one attempt and ownership checks. This is conditional support, not universal page-family or live-success coverage. |
| 2. HTTP first; bounded justified fallback; auth/CAPTCHA/block directs to extension. | **Not fully met.** HTTP-first dispatch, eligibility, failure guidance and local fallback checks exist, but F1 demonstrably suppresses screen-visible login barriers in the shared classifier and invents a barrier for invisible text. F2 also leaves the shared fetch allocation bound incomplete. Browser enrichment is intentionally disabled in the deployed runtime; this is a separately tracked approved limitation, not silently counted as deployed fallback success. |
| 3. Raw/normalized snapshots retain provenance, missing fields, coverage and extractor version for replay/audit. | Demonstrated on the audited retained-field contract by replay/parity checks, existing persisted HTTP/browser tests and deployed snapshot behavior. Replay is limited to retained public fields; it cannot reconstruct omitted HTML. No fresh independent field-value audit of the Alibaba snapshot was performed. |
| 4. Extension merge avoids duplicate evidence and platform credentials/session state. | Backend schema/secret rejection, merge/provenance and ownership evidence support the implemented boundary; 215 fresh selected tests pass. Current signed-in wire/network acceptance remains a recorded limitation; prior accepted capture/import records are preserved. No credential leakage is established. |

The 2.5 inactive-runtime approval, 2.3 shop-capture deferral and 2.8 release acceptance do not expressly waive the epic's access-classification criterion. This document therefore does not infer such a waiver. A human may override the machine verdict; record that explicitly in a follow-up retrospective rather than changing statuses implicitly. Completing A1/A2 and resolving the named scope/verification limits supplies evidence for reassessment, not an automatic promise of acceptance.

## Open questions

1. Should full epic acceptance require a compatible deployed browser-gain path, or should that capability receive an explicit scoped deferral? The existing story runtime decision permits disablement, while the epic still names justified Playwright fallback. A3 proposes resolving that distinction; no scope edit was made.
2. Do forced runner death, slow cleanup or allocation failure produce a real orphan, budget overrun or worker loss? F4–F6 are unqualified paths; existing ordinary-limit tests do not answer these specific questions.
3. When an accessible signed-in shop is available, does the current deployed extension/merge flow pass the selected-payload, owner-result and auto-open checks? The earlier manual deferral remains in force.
4. Will the fresh Alibaba public success reproduce with similarly traceable field values across additional audited pages? This run establishes one PARTIAL deployed snapshot, not a platform-wide accessibility rate.

The user supplied no additional going-in concern. Team discussion was not requested and was skipped. At the original retrospective assessment, this document was the only authored project artifact; source code, plans, story/epic files and ticket statuses had not been edited. The renderer snapshot, temporary review diff/test files and three ordinary development guest submissions are operational artifacts/effects described above. Subsequent authorized remediation is recorded separately in the linked execution record.
