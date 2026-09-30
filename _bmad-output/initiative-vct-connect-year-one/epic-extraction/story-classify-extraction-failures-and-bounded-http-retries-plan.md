---
title: 'Classify extraction failures and bounded HTTP retries'
type: 'feature'
ticket: '2'
created: '2026-09-30'
status: 'built'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['blind-hunter', 'edge-case-hunter', 'verification-gap', 'intent-alignment']
review_loop_iteration: 0
baseline_revision: 'e3c5a4a69f02fe84140981a38d17e1bbd6e7c582'
context:
  - '_bmad-output/initiative-vct-connect-year-one/epic-extraction/epic-extraction.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Public 1688 extraction already exposes seven statuses, but login HTML is classified as a challenge, temporary HTTP failures are never retried, and the web result gives little guidance. Some malformed page structures can escape classification and trigger unrelated worker retries.

**Approach:** Complete the shared failure contract, retry temporary public-fetch failures within one bounded extraction, and show Vietnamese recovery guidance. Preserve evidence, source validation, and the existing extension capture path.

## Boundaries & Constraints

**Always:** Preserve the seven statuses, SupplierData v1 coverage, offer binding, checked public-IP connections, authorization, quota, and immutable completion. Reject invalid API submissions before queuing; direct extractor invalid input returns UNSUPPORTED_PAGE without fetching. Access failures produce no snapshot or risk claim. Retain the 2 MB cap and shared 25-second budget across requests, redirects and delays, with timeouts reduced to remaining budget. Distinguish temporary DNS failure from private-address rejection; never connect to an unverified address.

**Never:** Retry 401/403/429, login/challenge HTML, unsafe destinations, offer mismatches, unavailable pages, or parser failures. Send platform credentials, bypass challenges, alter queue settlement, add browser fallback/platform adapters, enrich selectors, merge snapshots, or invent evidence. Do not claim hard cancellation of blocking OS DNS resolution.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
| --- | --- | --- | --- |
| Accessible evidence | Verified offer with complete or missing contract fields | Existing SUCCESS/PARTIAL vocabulary; available evidence and coverage preserved | Missing fields stay unknown |
| Temporary failure | Timeout, temporary resolver/network error, or HTTP 500/502/503/504 | At most two retries, 0.5/1-second backoff, shared deadline | TIMEOUT for timeout/budget exhaustion; sanitized PARSE_FAILED reason for exhausted transport/upstream failure |
| Login or challenge | 401, login HTML or approved login redirect; 403/429, CAPTCHA/block HTML | AUTH_REQUIRED or BLOCKED; web guidance to open source and capture using extension | No automatic retry or snapshot; challenge takes precedence over login when both are observed |
| Unsafe or unavailable | Invalid URL, private DNS, foreign/cross-offer redirect, redirect loop, 404/410 | Reject at admission or explicit UNSUPPORTED_PAGE/BLOCKED outcome | Never fetch rejected target; global redirect limit remains bounded |
| Changed/malformed content | Non-HTML, oversize body, malformed embedded structures, missing/mismatched offer identity | Explicit PARSE_FAILED with fixed reason | No source exception details or fabricated snapshot |
| Budget or stream failure | Slow chunks or timeout after partial body | Discard failed body; retry only within remaining budget | No incomplete stream parsed as success |
| Final owner result | Completed queued extraction with any failure outcome | Polling stops; status, reason and appropriate Vietnamese next action shown | No promise of another automatic retry after terminal completion |

</frozen-after-approval>

## Code Map

- `backend/app/extraction/offer1688.py` — fetcher, checked-IP transport, DNS and parser; preserve byte cap and source checks, split access classification and guard malformed models.
- `backend/app/extraction/contracts.py`, `urls.py` — preserve seven statuses, SupplierData v1 and strict URL validation.
- `backend/worker/main.py`, `backend/app/storage.py` — source outcomes complete; exceptions trigger processing retries. Verify persistence without changing queue policy/schema.
- `frontend/apps/web/app/analysis-status.ts`, `extraction-evidence.tsx` — terminal status/provenance; share recovery guidance.
- `frontend/packages/contracts/src/index.ts` — preserve matching status union and optional safe reason.
- `backend/tests/test_extraction.py`, `test_postgres_tracer.py`, frontend status/render tests — deterministic fetch and owner-result verification.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/extraction/offer1688.py` — classify URL/HTTP/redirect/page failures, malformed data and temporary DNS errors without weakening safety.
- [x] `backend/app/extraction/offer1688.py` — two transient retries, injected clock/sleep, 0.5/1-second delays, remaining-budget timeouts, globally bounded three redirects, response cleanup and partial-body discard.
- [x] `frontend/apps/web/app/analysis-status.ts`, `extraction-evidence.tsx` — Vietnamese recovery guidance, extension instructions for login/challenges, and safe-destination errors.
- [x] `backend/tests/test_extraction.py` — matrix, retries, DNS changes, redirects, budgets, streams and malformed layouts; verify shared SUCCESS acceptance without inventing fields.
- [x] `backend/tests/test_postgres_tracer.py`, frontend status/render tests — final owner polling, no failed snapshots, processing-attempt separation, sparse evidence and guidance.

**Acceptance Criteria:**
- Given temporary source failures, when extraction runs, then it can recover within its finite budget or stores one classified terminal outcome without changing queue processing attempts.
- Given login or access challenges, when the owner views the result, then it explains using the existing extension and retains no unsupported supplier claims.
- Given existing fixture, upload, and extension paths, when regression checks run, then authorization, provenance, coverage and result presentation remain valid.

## Implementation Notes

- Retries remain local to one computation; no queue/schema/authentication changes. Transient DNS and upstream exhaustion have fixed `DNS_ERROR` and `UPSTREAM_UNAVAILABLE` reasons. The checked-IP transport clamps socket operations to remaining budget; blocking OS DNS remains an explicit limitation.
- Login title/redirect detection is separate from body prompts. Ordinary navigation login text retains verified accessible evidence; CAPTCHA takes precedence. Malformed embedded objects and recursive JSON produce fixed parser failures.
- Vietnamese guidance is shared between terminal status and evidence rendering. Failed results retain only a validated offer source link and no supplier claims.
- Independent blind/edge reviews completed. Additional verification-gap and intent reviewers hit the account usage limit; their independent reviews did not complete. The primary agent continued the consumer/test audit locally after the user's instruction to continue, and applied verified corrections directly because the implementer could not be re-engaged under that limit.
- Review corrections classify malformed redirects (including HTTPX's invalid Location errors), permit JSON whitespace, prioritize real login walls, validate retained JSON for nonfinite numbers/NUL/surrogates, stop on access HTML returned with a transient HTTP status, and stop certificate failures without retries. Redirect-loop detection now uses the canonical destination actually fetched. The strict URL contract permits only that one destination, so a query-only self-redirect stops immediately.

## Plan Change Log

## Review Triage Log

| Finding | Verdict | Route and evidence |
| --- | --- | --- |
| Blind 1: malformed redirect escapes | medium | patch: reproduced ValueError from URL construction; guarded construction and added single-request tests. |
| Blind 2: JSON whitespace loses evidence | medium | patch: reproduced malformed outcome for valid whitespace; trim JSON whitespace before decoding and test preserved evidence. |
| Blind 3: malformed login page becomes parse failure | medium | patch: reproduced body login plus malformed model; parser exception recovery now recognizes the login wall without accepting evidence. |
| Blind 4: nested nonfinite raw JSON fails persistence | medium | patch: reproduced PARTIAL with raw NaN; recursively validate retained raw/normalized values, with parser and owner-polling tests. |
| Blind 5: surrogate string fails JSONB persistence | medium | patch: reproduced PARTIAL with an unpaired surrogate; UTF-8 and NUL checks produce fixed parser failure, tested through persistence. |
| Blind 6: HTTP 503 challenge is retried | medium | patch: reproduced three attempts on CAPTCHA HTML; inspect bounded transient HTML for access markers before retry. |
| Blind 7: raw query redirects repeat canonical request | low | patch: request destination is always canonical; detect a repeated normalized destination immediately and verify no further request. |
| Blind 8: certificate failure is retried | low | patch: NetworkError includes ConnectError wrapping certificate verification; inspect the exception chain for the concrete permanent TLS failure. |
| Blind 9: decompression allocates before byte-cap check | medium | defer: the baseline already used HTTPX iter_bytes with automatic decompression before checking size. Check capacity before appending now; bounded decompression remains a pre-existing transport concern. |
| Edge 1: urllib rejects malformed Location | medium | patch: same reproduced URL-construction defect as Blind 1; single-request malformed redirect tests pass. |
| Edge 2: HTTPX rejects Location before extractor sees response | medium | patch: installed HTTPX raises RemoteProtocolError with a fixed invalid-Location prefix; classify this case as unsafe redirect, retaining retries for ordinary remote protocol errors. |
| Edge 3: body login plus login canonical becomes mismatch | medium | patch: reproduced OFFER_MISMATCH; classify login after evidence inspection and before canonical validation. |
| Edge claim 1: redirect classification promise violated | medium | patch: same verified URL-construction defect; catch and terminal outcome preserve the source-failure contract. |
| Edge claim 2: login recovery promise violated | medium | patch: same verified body/canonical login defect; AUTH_REQUIRED now selects extension guidance. |

Local verification-gap audit: changed fetch behavior is exercised at extraction and queued owner-result boundaries; deadline socket operations have deterministic tests and a real TLS smoke check. Shared recovery guidance is exercised through both status and rendered evidence tests. Real Azure roundtrip remains opt-in and skipped; queue code was unchanged. No additional material gap identified beyond the documented incomplete independent lenses.

Local intent audit: the diff implements classified source outcomes and bounded retries inside one worker computation, plus Vietnamese web guidance. It preserves existing capture, source safety and coverage. It does not increase extraction coverage or claim that the current 1688 adapter can populate every optional field; shared SUCCESS acceptance is verified at the contract/presentation boundary.

## Design Notes

HTTP retries stay inside one worker computation. HTTP 429 remains terminal. Recognize exact login destinations without following them; keep redirects bounded across retries. No new credentials or live source access are required for deterministic checks.

## Verification

Final post-review verification: 229 backend tests passed on the isolated database, one opt-in live Azure test skipped, one existing Starlette deprecation warning (148.13 seconds). All 107 extraction cases passed separately. Frontend regression rerun: 46 passed; TypeScript rerun passed. Web and extension production builds and credential scan passed on the unchanged frontend code. Final whitespace check passed. Two independent review lenses completed; two additional lenses failed on account usage limits and were audited locally. The pre-existing automatic-decompression allocation concern remains deferred.

Observed before review: full backend regression on isolated `vct_story22_20260930`: 212 passed, one opt-in live Azure check skipped, one existing deprecation warning. Extraction suite: 92 passed. Frontend: 46 passed; TypeScript passed. Staged whitespace check, web/extension production builds and frontend credential scan passed. Restarted API/web returned HTTP 200. A real public fetch through the new TLS/deadline transport returned BLOCKED/ACCESS_CHALLENGE in 3.03 seconds with no snapshot.

Matrix audit: accessible evidence and shared SUCCESS/PARTIAL acceptance are covered by parser/contract presentation tests; temporary failure by recovery/exhaustion and queue-attempt tests; login/challenge by precedence and non-followed redirect tests; unsafe/unavailable by URL, DNS, redirect and HTTP cases; changed content by malformed/non-HTML/oversize/offer tests; budget/stream failure by fake-clock and socket/cleanup tests; final owner result by PostgreSQL owner polling and rendered terminal guidance. All covering suites ran and passed.

- `.venv/Scripts/python.exe -m pytest backend/tests -q` with a dedicated isolated `VCT_TEST_DATABASE_URL` — backend regressions and owner polling pass without interference from app jobs.
- `npm test --prefix frontend`, `npm run typecheck --prefix frontend`, `npm run build --prefix frontend` — presentation tests, TypeScript and web/extension builds pass.
- `git diff --check` — no whitespace errors; independent build review triaged before local commit.
