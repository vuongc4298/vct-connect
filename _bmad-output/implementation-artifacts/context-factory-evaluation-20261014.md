# Supplier context and factory evidence evaluation — 2026-10-14

## Scope and method

Compared the owner's latest two completed reports for 1688 offer 990526456516, created on 2026-10-13 at 17:39 and 18:59 UTC. The product, supplier, factory, ten review bodies and structured facts match. Only the later report includes the v6 page-context packet. The exact downloaded product/shop/factory HTML hashes match that later snapshot.

Read-only diagnostics and authorized YEScale verification replays did not change either saved report. The three baseline variants used gpt-4o-mini, temperature 0.1, 3000 output tokens, the same v6 prompt and the same latest structured facts. Complete cleaned text means all text in the downloaded sanitized captures, not an unrestricted original page or scripts/session state. Each baseline was replayed twice. The final candidate, including its revised prompt/schema/grounding policy, was replayed three times.

## Results

| Input strategy | Prompt tokens | Observed latency | Evidence/scoring outcome |
| --- | ---: | --- | --- |
| Structured only, v6 | 4293 | 8.5–9.2 s | Pricing scored twice; quality once; after-sales remained unknown. |
| Current same-zone packet, v6 | 7290 on successful call | 28.3 s successful call | One run failed validation after repair. The other scored quality but treated missing final terms as a pricing concern; policy wording failed the after-sales keyword gate. |
| All cleaned capture text, v6 | 6571 | 10.9–12.4 s | More text did not consistently improve grounding: quality scored once, pricing twice, after-sales remained unknown. |
| Final structured facts + targeted excerpts, v7 | 4042 | 6.4–7.5 s | All three runs scored quality, advertised after-sales protection and pricing from exact source evidence; no schema repair. |

The stored v5 report used 4114 input tokens and took 24.6 s; the stored v6 report used 7290 and took 26.9 s. Provider latency varies independently of context size. The final strategy uses about 45% fewer input tokens than the current packet. These small replay samples support this specific implementation choice, not a universal latency/accuracy claim. Intermediate candidates were rejected when they produced schema failures or treated unverified positive protections as material concerns.

## Implemented strategy

Keep structured facts as the main input. Add at most 4 KB of targeted policy/term excerpts, deduplicate overlapping passages, and omit universal platform price definitions. Retain one concise policy excerpt when it is otherwise buried in a general field. Full source URLs and HTML hashes remain in the audit record, while repetitive per-section metadata is omitted from model text. Supplemental capture text also yields to structured facts before the 48 KB normalization gate.

Replace accumulated prompt blocks with one explicit three-category routing contract. Legal identity and review-pattern assessment remain separate deterministic modules. Publish canonical field names and quote length limits in the JSON schema. Recover the observed services_display_text alias only when its quotation exactly matches the captured product service field; record that normalization in run settings. Invented quotations still fail validation/grounding.

Recognize published return/quality-compensation protections as preliminary after-sales evidence, with confidence capped at 0.6. They do not verify policy fulfillment. An unverified positive promise alone cannot create a material concern; unsupported categories are not automatically changed to LOW.

## Factory diagnosis and remedy

Factory captures previously retained display strings while the identity adapter read only unrelated structured keys. The two audited reports therefore had no identity evidence and displayed the 0.5/0.5 prior.

Capture and normalize explicitly labeled area, staffing range, processing method, production lines, equipment and business type. Preserve company area separately from factory area and preserve staffing ranges as displayed. The sample contains company area 2100 m² and four employees; these do not establish manufacturing capacity. Its factory-profile presence is a weak unverified claim, so its classification remains UNCERTAIN with three considered evidence records and confidence 0.125.

Hide probability bars below the existing 0.4 classification confidence threshold and show the considered profile claims instead. Older reports retain their original stored assessment and use the uncertainty presentation; new collections use the corrected evidence adapter.

## Delivery and verification

Extension version 0.6.2 packages the supplied VCT mark for the toolbar and extension list, with localized description/title. The live app URL remains unchanged at the user's request. Reload the live unpacked extension after rebuilding; existing source identity and extension ID are preserved.

Local checks: backend 1015 passed / 165 infrastructure-dependent skipped before the final policy and capture-budget guard; final relevant policy tests passed; frontend 170 passed; type checking, production build and frontend secret scan passed. The exact downloaded bundle normalized with ten reviews preserved. Release CI and live revision verification are recorded after deployment.

BMad launcher failed with Windows error 123; work continued under the user's existing waiver. This file records implementation/evaluation evidence and does not claim a completed BMad workflow.
