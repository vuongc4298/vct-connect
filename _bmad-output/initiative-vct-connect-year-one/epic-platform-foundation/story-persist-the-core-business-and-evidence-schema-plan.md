---
title: 'Persist the core business and evidence schema'
type: 'feature'
ticket: '3'
created: '2026-09-27'
status: 'built'
baseline_revision: 'NO_VCS'
route: 'full'
route_source: 'auto'
review: 'thorough'
review_source: 'auto'
lenses_ran: ['blind-hunter', 'edge-case-hunter', 'verification-gap', 'intent-alignment']
review_loop_iteration: 1
context:
  - 'VCT_Connect_MVP_Technical_Specification_EN.pdf'
  - '_bmad-output/initiative-vct-connect-year-one/epic-platform-foundation/epic-platform-foundation.md'
  - '_bmad-output/initiative-vct-connect-year-one/epic-platform-foundation/story-trace-one-queued-analysis-through-the-platform-plan.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Story 1.1 stores its tracer schema in application code, has no migration history, and lacks the user, entitlement, supplier, snapshot, and analysis relations required by later stories. This prevents safe schema evolution and leaves Clerk identity without a canonical local user record.

**Approach:** Introduce versioned PostgreSQL migrations with a validated adoption path for the populated Story 1.1 database, then add the core business and evidence tables and nullable analysis relations. Keep the tracer flow operational while making both fresh installation and rollback reproducible.

## Boundaries & Constraints

**Always:** Preserve existing analysis, result, and local queue rows; use UUID keys, UTC `timestamptz`, explicit foreign keys, and typed relational columns for identity and lifecycle data; reserve JSONB for raw and normalized evidence documents; support fresh databases and the existing populated Story 1.1 schema; keep `analyses.user_id` nullable for guest analyses; validate an existing baseline before recording it as migrated; make the Story 1.3 migration reversible to the Story 1.1 baseline.

**Never:** Fabricate suppliers or snapshots from Story 1.1 fixture results; silently accept baseline schema drift; add Clerk request authentication or later-owned review, scoring, report, watchlist, payment, credit, media, or annotation tables; define extraction payload fields, quota policy, plan defaults, or trial dates owned by later stories; remove or rename Story 1.1 columns used by the API and worker.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Fresh install | Empty PostgreSQL database | Baseline and core migrations apply in order and all required tables, constraints, and indexes exist | Transaction rolls back and initialization exits nonzero on migration failure |
| Existing install | Populated, exact Story 1.1 schema with no migration metadata | Baseline is validated and adopted, then the additive core migration runs without changing existing row values or counts | Refuse adoption with a clear schema mismatch if required baseline objects differ |
| Core relation | Analysis linked to a user and supplier snapshot; user has an entitlement | One query joins analysis, user, entitlement, snapshot, and supplier with intact JSONB evidence | Foreign keys reject nonexistent references |
| Guest analysis | Existing or new analysis has no user | Row remains valid with a null `user_id` | No synthetic user or entitlement is created |
| Story rollback | Database is at the Story 1.3 revision | Reversing the core revision removes only Story 1.3 objects and columns; Story 1.1 rows and flow remain | Destructive downgrade is tested only on an isolated database |

</frozen-after-approval>

## Code Map

- `backend/db/migrations/0001_tracer_baseline.py` — reproducible Story 1.1 baseline revision.
- `backend/db/migrations/0002_core_business_schema.py` — immutable first-pass core revision already recorded by the local database.
- `backend/db/migrations/0003_align_core_schema_to_spec.py` — forward correction to the canonical section 19 schema, reversible together with 0002.
- `backend/app/migrations.py` — migration runner and validated adoption of an existing tracer schema.
- `backend/app/init_db.py` — invokes the migration runner instead of application-owned DDL.
- `backend/app/storage.py` — removes inline schema initialization while retaining tracer persistence queries.
- `backend/tests/test_migrations.py` — isolated fresh, adoption, constraints, join, and downgrade coverage.
- `backend/tests/test_postgres_tracer.py` — initializes test storage through migrations and protects the Story 1.1 flow.
- `backend/requirements.txt` — pins the migration dependency compatible with psycopg 3.
- `README.md` — documents migration initialization and rollback safeguards.

## Tasks & Acceptance

**Execution:**
- [x] `backend/requirements.txt`, `backend/db/migrations/` — add Yoyo and ordered baseline/core revisions so raw psycopg remains the application data layer and schema changes are transactional and reversible.
- [x] `backend/app/migrations.py`, `backend/app/init_db.py`, `backend/app/storage.py` — centralize migration execution, validate and adopt an exact pre-migration Story 1.1 database, and remove semicolon-split embedded DDL.
- [x] `backend/db/migrations/0002_core_business_schema.py`, `backend/db/migrations/0003_align_core_schema_to_spec.py` — preserve the already-applied 0002 history and forward-correct to the specification section 19 schema: `users(id, clerk_user_id, email, role, created_at)`; `entitlements(id, user_id, entitlement, source, starts_at, expires_at, status)`; `suppliers(id, platform, platform_supplier_id, name, source_url)`; `supplier_snapshots(id, supplier_id, raw_payload, normalized_data, extraction_method, analysis_mode, completeness, extractor_version, extracted_at)`; add nullable `user_id`, `supplier_snapshot_id`, `mode`, and `scoring_version` to `analyses`. Supporting timestamps are allowed, but alternate aliases for canonical columns are not. Add role, platform, time-range, JSON-object, completeness, nonblank-required-identifier, uniqueness, foreign-key, and lookup constraints/indexes without altering legacy rows.
- [x] `backend/tests/test_migrations.py` — cover every matrix scenario, required constraints, data preservation, and the sample cross-table join using an isolated database.
- [x] `backend/tests/test_postgres_tracer.py`, `README.md` — run existing integration coverage against migrated storage and document apply, status, and safe rollback commands.

**Acceptance Criteria:**
- Given a clean database, when initialization runs, then all ordered migrations apply once and a second run is idempotent.
- Given an exact populated Story 1.1 database, when initialization runs, then it is adopted and upgraded with unchanged tracer IDs, statuses, timestamps, JSONB payloads, and row counts.
- Given a deliberately altered baseline, when adoption is attempted, then initialization fails before applying Story 1.3 changes and identifies the mismatch.
- Given valid linked fixtures, when the representative evidence query runs, then an analysis returns its user, qualifying entitlement, supplier snapshot, supplier, and JSONB documents.
- Given the core revision is reversed in an isolated database, when the Story 1.1 tracer tests run at the baseline revision, then enqueue, processing, and result retrieval still work.

## Implementation Notes

- 2026-09-27: Added Yoyo 9.0.0, reversible baseline/core revisions, catalog-validated legacy adoption, guarded migration commands, and isolated PostgreSQL migration coverage. Full backend verification reported `17 passed, 1 skipped`; the skip is the credential-gated live Azure test. The workspace has no version control, so review uses a complete changed-file audit bundle rather than a Git diff.
- 2026-09-27 review loop 1: No version-control baseline exists, so a literal automated revert is unavailable. The first implementation is treated as disposable and the context-free implementer must replace affected schema, runner, tests, and documentation from the amended plan rather than preserve its alternate domain model.
- 2026-09-28 review loop 1 completion: The delegated reimplementation stopped at its usage limit after partially replacing code and deleting the migration test file. Direct implementation restored tests, preserved the already-applied 0002 revision, added reversible 0003 as the forward canonical correction, applied it to the active database, and verified the retained Story 1.1 counts `(4 analyses, 4 results, 0 queue rows)`. Verification completed with `14 passed` for migrations and `25 passed, 1 skipped` for the backend; only the credential-gated live Azure test was skipped.
- 2026-09-28 thorough review completion: Fixed populated-core rollback, exact baseline index/constraint validation, unmanaged-table rejection, shared psycopg URL handling, and all cited verification gaps. Final verification: `19 passed` for migrations and `30 passed, 1 skipped` for the backend, with only the opt-in live Azure round trip skipped. Three pre-existing Story 1.1 queue/repair concerns were recorded in deferred work.

## Plan Change Log

- 2026-09-27, review loop 1: The implementation invented alternate domain columns (`plan_code`, `valid_from`, `external_id`, `captured_at`, `raw_document`) and omitted fields defined by technical specification section 19 because the plan did not give the context-free implementer the canonical field map. Amend the Code Map, execution task, design notes, and verification expectations with the exact specification-owned columns and nullability boundary. Avoid the known-bad schema that later Clerk, entitlement, extraction, and evidence stories cannot consume. KEEP: Yoyo with raw psycopg, ordered reversible baseline/core revisions, exact legacy adoption, preserved Story 1.1 data and behavior, isolated-schema tests, guarded rollback, transactional failure coverage, and UTC sessions.

## Review Triage Log

- **false / reject (verification-gap 1):** PostgreSQL queue coverage is environment-gated by design, and this run executed it with `VCT_TEST_DATABASE_URL` (`17 passed, 1 skipped`); the only skip was the separately gated live Azure test. README also requires the database variable before these checks.
- **medium / patch (verification-gap 2):** Only status-check drift is rejected in tests, so regressions in catalog comparison for defaults, nullability, types, primary keys, or foreign keys could pass unnoticed. Add representative parameterized drift cases.
- **medium / patch (verification-gap 3):** Rollback tests do not assert removal of all four analysis columns or prove rollback followed by reapply. Extend the rollback scenario with exact column inspection and successful reapplication.
- **medium / patch (verification-gap 4):** Tests call the rollback helper directly and do not exercise the CLI confirmation guard. Add argument-dispatch tests proving the unconfirmed command cannot invoke rollback.
- **medium / bad_plan (blind-hunter 1):** Lowercasing full constraint text also lowercases status literals, so a lowercase-only status check can be adopted even though application writes use uppercase values. Re-derive validation without altering literal case.
- **medium / bad_plan (blind-hunter 2):** The same textual compaction erases quoted identifier case and can equate a foreign key to `analyses` with one to a different quoted relation. Re-derive foreign-key validation from catalog identities or case-safe parsing.
- **low / reject (blind-hunter 3):** Validation and Yoyo marking use different connections, leaving a narrow concurrent-DDL race. The outcome is real but requires an operator to alter these tables during first adoption, and a cross-connection locking protocol would add disproportionate complexity for this developer migration.
- **medium / patch (blind-hunter 4):** `rollback_core_migration` checks application state before taking the Yoyo lock, so concurrent callers can both attempt rollback. Move the state check inside the lock.
- **medium / patch (blind-hunter 5):** Directly rolling back revision 0002 does not reject applied dependent revisions, which will become reachable as later stories add migrations. Refuse core rollback unless it is the latest applied revision.
- **low / patch (blind-hunter 6):** Column drift diagnostics show only equal name lists when a type, nullability, or default differs. Report the mismatched property tuples.
- **medium / patch (blind-hunter 7):** Migration entry points load full tracer settings, so an Azure-configured shell must provide Service Bus credentials for database-only apply/status/rollback. Read and validate only `DATABASE_URL` in migration commands.
- **medium / patch (blind-hunter 8):** The populated-adoption fixture leaves `local_queue` empty and therefore does not prove preservation of availability, claim, and attempt values. Seed and compare an active queue row.
- **medium / patch (blind-hunter 9):** Rollback coverage creates tracer data only after downgrade and cannot show that preexisting analysis/result/queue rows survive it. Seed before downgrade and compare afterward.
- **low / patch (edge-case-hunter 1):** A `postgresql+psycopg://` URL accepted by the migration URL converter is passed unchanged to direct psycopg baseline inspection and fails. Normalize it for direct connections or reject it consistently.
- **low / reject (edge-case-hunter 2):** Once migration history exists, manually introduced baseline drift is not revalidated before applying core. The plan requires validation before adopting an unmanaged baseline; continuously policing later manual DDL is outside that rule and unlikely in normal operation.
- **medium / patch (edge-case-hunter 3):** Duplicate of blind-hunter 4; the pre-lock applied check allows concurrent rollback attempts. Move the check under the migration lock.
- **medium / defer (edge-case-hunter 4):** Story 1.1 deletes the analysis when publish raises after an ambiguous broker acceptance. This outbox/idempotency issue predates the migration change and belongs to the later queue reliability story.
- **medium / defer (edge-case-hunter 5):** Story 1.1 can publish successfully and fail its later `QUEUED` update, allowing a duplicate client retry. This predates Story 1.3 and belongs to the later queue reliability story.
- **medium / defer (edge-case-hunter 6):** Story 1.1 has no lease token to prevent a stale worker from completing or releasing a reclaimed local item. This predates Story 1.3 and belongs to retry/idempotency work.
- **medium / defer (edge-case-hunter 7):** Story 1.1 can mark an analysis complete when a conflicting result already exists without verifying payload identity. This predates Story 1.3 and belongs to idempotent processing work.
- **low / patch (edge-case-hunter 8):** New canonical text identifiers accept blank strings. Add nonblank checks only to identifiers the specification makes required.
- **low / patch (edge-case-hunter 9):** Tests assert only index names, so wrong column order or predicates could pass. Assert index definitions for the required lookup paths.
- **false / reject (intent-alignment):** The reviewer identified a possible runtime-Clerk reading, but the approved boundary explicitly assigns authentication to Story 1.2 and limits Story 1.3 to its schema substrate; no runtime identity behavior is missing from this story.
- **high / bad_plan (parent specification audit):** The core revision diverges from specification section 19: `users.email` is absent; entitlements omit `entitlement`, `source`, `starts_at`, `expires_at`, and `status`; suppliers omit `platform_supplier_id`, `name`, and `source_url`; snapshots omit `raw_payload`, `normalized_data`, `extraction_method`, `analysis_mode`, `extractor_version`, and `extracted_at`. The plan failed to expose the canonical map to a context-free implementer, so amend it and re-derive the migration while preserving the working migration machinery.
- **medium / patch (verification-gap loop 2.1):** The 0003 refusal path for populated provisional tables had no test. Added a through-0002 fixture proving the row survives, the explicit error is raised, and 0003 stays pending.
- **medium / patch (verification-gap loop 2.2):** Nullable canonical fields were only exercised with values. Added successful inserts omitting user email, supplier platform ID/name, and snapshot completeness, plus catalog nullability assertions.
- **medium / patch (verification-gap loop 2.3):** Several nonblank and JSON-object checks lacked negative cases. Added cases for entitlement source/status, snapshot method/mode/version, and normalized JSON shape.
- **medium / patch (verification-gap loop 2.4):** Business-key uniqueness and several foreign-key edges lacked failure coverage. Added duplicate identity/entitlement/supplier/snapshot and orphan entitlement/snapshot/analysis cases.
- **high / patch (verification-gap loop 2.5):** Rollback was tested only with empty core tables. It now runs with populated users, source-distinct entitlements, nullable supplier IDs, and nullable completeness.
- **high / patch (verification-gap loop 2 other):** The 0003 reverse migration set nullable canonical fields back to `NOT NULL` before 0002 could drop their tables. Destructive rollback now nulls analysis links and deletes Story 1.3 rows before reversing the provisional shape.
- **high / patch (blind-hunter loop 2.1):** Nullable snapshot completeness could abort rollback. The destructive data-clear step and populated rollback test prove the baseline is restored.
- **high / patch (blind-hunter loop 2.2):** Nullable platform supplier IDs could abort rollback. The same correction and test cover this path.
- **high / patch (blind-hunter loop 2.3):** Source-distinct entitlements could collide after dropping `source` during reverse migration. Core rows are deleted before shape reversal, and the test includes two such entitlements.
- **medium / patch (blind-hunter loop 2.4):** A migrationless database containing tracer tables plus provisional managed tables could be baseline-marked before a later duplicate-table failure. Adoption now rejects any managed-table set other than the exact tracer baseline before creating Yoyo metadata.
- **medium / patch (blind-hunter loop 2.5):** Standalone unique or exclusion behavior was not part of baseline comparison. Exact baseline indexes are now compared, unexpected constraint kinds are rejected, and a unique-index drift test is present.
- **medium / patch (blind-hunter loop 2.6):** Primary-key deferrability was read but discarded. It is now part of the expected primary-key tuple and tested with a deferrable replacement.
- **medium / patch (blind-hunter loop 2.7):** `postgresql+psycopg://` worked for migrations but failed in `Store.connect`. Storage now uses the same psycopg URL normalization and exercises a real connection with that scheme.
- **high / patch (blind-hunter loop 2.8):** Duplicate of loop 2 rollback-data findings; populated canonical rollback coverage was added.
- **medium / patch (blind-hunter loop 2.9):** Duplicate of the unobserved constraint finding; negative cases now cover every cited check and relationship.
- **medium / patch (blind-hunter loop 2.10):** Canonical metadata assertions checked only names. Tests now assert types and nullability for the cited contract fields.
- **high / patch (edge-case-hunter loop 2.1):** Duplicate rollback-data finding; destructive reversal now removes core relationships and rows before provisional constraints are restored.
- **medium / patch (edge-case-hunter loop 2.2):** Baseline adoption ignored extra indexes, unexpected constraint kinds, and validation state. It now compares exact indexes, rejects unrecognized constraints, and rejects non-validated constraints.
- **low / reject, carried (edge-case-hunter loop 2.3):** The concurrent-DDL adoption race remains real but requires schema alteration during first adoption; cross-connection table locking is disproportionate for this developer migration.
- **low / reject (edge-case-hunter loop 2.4):** Status can theoretically observe a concurrent migration between per-revision reads, but it is informational and the transient display causes no schema or data harm.
- **medium / defer (edge-case-hunter loop 2.5):** Story 1.1 can delete an analysis after an ambiguous broker acceptance. This predates Story 1.3 and belongs to queue idempotency/outbox work.
- **medium / defer (edge-case-hunter loop 2.6):** Story 1.1 can return an error after publish succeeds but the queued-status update fails. This predates Story 1.3 and belongs to queue reconciliation work.
- **medium / defer (edge-case-hunter loop 2.7):** Story 1.1 skips result repair when a completed analysis lacks its result row. The state cannot arise through its atomic completion transaction but should be considered in later repair/idempotency work.
- **low / reject (edge-case-hunter loop 2.8):** A queue attempt counter can overflow only after more than two billion claims; adding saturation logic is unnecessary for the current developer tracer.
- **high / patch (edge-case-hunter loop 2.9):** Duplicate rollback claim; populated canonical reversal now passes.
- **medium / patch (edge-case-hunter loop 2.10):** Duplicate exact-adoption claim; index, constraint-kind, validation, and deferrability checks were added.
- **medium / patch (edge-case-hunter loop 2.11):** Duplicate verification claim; migration tests now cover rollback data, nullable fields, unobserved checks, uniqueness, foreign keys, and catalog contracts.
- **false / reject (intent-alignment loop 2):** The diff implements the approved structural schema and migration reading. Runtime Clerk identity, entitlement enforcement, and evidence population remain assigned to later stories by the frozen boundary.

## Design Notes

Yoyo is used because the application already uses psycopg directly and does not need an ORM solely for migrations. The baseline migration represents the exact Story 1.1 schema. A separate preflight may mark that baseline as applied only after catalog validation; fresh databases apply it normally. Catalog comparison must preserve SQL literal and quoted-identifier case, explain property-level mismatches, and serialize applied-state checks under the migration lock.

`analyses` links to entitlements through `user_id`, matching the technical specification and allowing entitlement history without inventing a direct admission-time entitlement relation. Tests select the entitlement valid at the analysis timestamp. Existing anonymous tracer rows retain null new foreign keys and are not assigned invented evidence.

Stable code values use uppercase text with checks where the specification defines the vocabulary (`CUSTOMER`, `INTERNAL_REVIEWER`, `ADMIN`; `1688`, `TAOBAO`, `ALIBABA`). Fields whose vocabulary or optionality belongs to extraction and product stories remain minimally constrained.

Canonical field semantics follow specification section 19. `users.email`, `suppliers.platform_supplier_id`, and `suppliers.name` are nullable so a verified Clerk subject or partially extracted supplier can be recorded without invented data; `suppliers.source_url` is required. Entitlement values (`entitlement`, `source`, `status`) are required nonblank text, `starts_at` is required, and `expires_at` is nullable but later than `starts_at` when present. Snapshot JSON fields must be objects; `extraction_method`, `analysis_mode`, `extractor_version`, and `extracted_at` are required, while `completeness` may be null until extraction policy is defined and otherwise lies from 0 through 1. Do not substitute product concepts such as `plan_code` for the specification's entitlement record.

Rollback refuses to remove the core revision while any dependent revision is applied, checks state while holding the migration lock, and reads only `DATABASE_URL`. Tests cover property-level baseline drift, a populated queue through adoption and rollback, exact index definitions, the CLI confirmation guard, removal of added analysis columns, and rollback followed by reapply.

## Verification

**Commands:**
- `uv pip install --python .venv/Scripts/python.exe -r backend/requirements.txt` — expected: migration dependency installs successfully.
- `.venv/Scripts/python.exe -m pytest backend/tests/test_migrations.py -q` — expected: clean apply/reapply, populated adoption, mismatch rejection, joins, constraints, and rollback pass.
- `.venv/Scripts/python.exe -m pytest backend/tests/test_postgres_tracer.py -q` — expected: Story 1.1 PostgreSQL and queue behavior remains green on the migrated schema.
- `.venv/Scripts/python.exe -m pytest backend/tests -q` — expected: complete backend suite passes.
