# VCT Connect authenticated developer tracer

This is a Clerk-authenticated **developer tracer**. It accepts exactly `https://detail.1688.com/offer/123456789012.html`; the result is a deterministic fixture, **not live supplier evidence**. Run the API on loopback only. Extraction, scoring, quotas, and production retry policy belong to later stories.

## Run locally

1. Fill the root `.env` file (or copy `.env.example` if it is missing). Set `QUEUE_TRANSPORT=azure`, `AZURE_SERVICE_BUS_CONNECTION_STRING`, and `AZURE_SERVICE_BUS_QUEUE`. Use a queue-scoped Shared Access Policy with Send and Listen rights for this developer tracer, and keep its connection string out of chat and source control.
2. Link the frontend to the existing Clerk application with `npx -y clerk@latest init --no-skills --app <application-id>` from `frontend/apps/web`. Pull the same development credentials into the ignored server file with `npx -y clerk@latest env pull --file ../../../.env.clerk --app <application-id> --instance dev`. The frontend secret remains server-only in Next.js; FastAPI reads its copy from `.env.clerk`. In Clerk Dashboard under **Sessions > Customize session token**, set `{ "aud": "vct-connect-api" }`.
3. Load `.env` and `.env.clerk` only into shells running the API or authenticated tests. In PowerShell, use `Get-Content .env,.env.clerk | ForEach-Object { if ($_ -match '^([^#=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process') } }` from the repository root. The worker and migration commands only require their existing database and queue settings.
4. `docker compose up -d db` and wait for its health check.
5. Create a Python environment and install `backend/requirements.txt`: `python -m venv .venv`, then `uv pip install --python .venv/Scripts/python.exe -r backend/requirements.txt` on Windows.
6. Apply the ordered database migrations: `.venv/Scripts/python.exe -m backend.app.init_db`. A fresh database receives the tracer baseline and core schema. An existing Story 1.1 database is catalog-validated before its baseline is recorded and upgraded; initialization stops on any mismatch.
7. In separate root-directory shells with the environment loaded, run `.venv/Scripts/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000` and `.venv/Scripts/python -m backend.worker.main`.
8. Run `npm run dev --prefix frontend` and open `http://127.0.0.1:3000`. Sign in or create an account before submitting the fixture. The server-side API proxy defaults to `http://127.0.0.1:8000`; if the API runs elsewhere, add `API_INTERNAL_ORIGIN` to `frontend/apps/web/.env.local` because Next.js does not load the repository-root `.env` file.

The API accepts Clerk session tokens only through the `Authorization: Bearer` header. It verifies the signature, expiry and activation times, issuer, `vct-connect-api` audience, and browser origin. A new Clerk subject is mapped to a PostgreSQL `CUSTOMER`; PostgreSQL remains the source of roles. Customers can submit and retrieve only their own analyses. `INTERNAL_REVIEWER` and `ADMIN` can retrieve analyses, while submissions remain customer-only.

`CLERK_SECRET_KEY` lets the Python SDK retrieve Clerk signing keys. For networkless verification, copy Clerk's PEM public key into the server-only `CLERK_JWT_KEY` variable. `CLERK_ISSUER` can override the issuer derived from the publishable key when a proxy or custom domain requires it.

## Live authorization matrix

1. Sign in as a new Clerk user, submit the fixture, and wait for `COMPLETED`. The first valid session creates a `CUSTOMER` row.
2. Sign in as a second Clerk user and confirm the first user's analysis ID returns the non-disclosing `Analysis not found` response.
3. In this local database only, find the second user's `clerk_user_id` and set its role to `INTERNAL_REVIEWER`: `docker compose exec db psql -U vct -d vct -c "UPDATE users SET role='INTERNAL_REVIEWER', updated_at=now() WHERE clerk_user_id='<subject>';"`. Confirm that user can retrieve the first analysis and receives `403` when submitting.
4. Repeat the update with `role='ADMIN'`. Confirm cross-customer retrieval remains allowed and submission remains `403`.
5. Restore development accounts to `CUSTOMER` after the matrix check.

The API commits a `QUEUED` analysis, its initial status event, and an outbox row in one PostgreSQL transaction. It returns `202` without waiting for Azure. The worker publishes pending outbox rows with the analysis UUID as `MessageId`; ambiguous publication is retried with the same ID. PostgreSQL sessions use UTC and return `TIMESTAMPTZ` values through FastAPI.

Poll responses expose `QUEUED`, `PROCESSING`, `FAILED_RETRYABLE`, `FAILED_FINAL`, and `COMPLETED`, plus ordered status events, attempt count, next retry time, a sanitized failure code, and final DLQ disposition. The browser keeps polling retryable states and stops on `COMPLETED` or `FAILED_FINAL`; it never automatically repeats a submission.

## Database migrations

The application continues to use psycopg directly; Yoyo owns only schema history and migration execution. Run these commands from the repository root with only `DATABASE_URL` loaded into the process; migration administration does not require Service Bus credentials or developer-mode configuration:

- Apply pending migrations: `.venv/Scripts/python.exe -m backend.app.migrations apply`
- Show each revision as `applied` or `pending`: `.venv/Scripts/python.exe -m backend.app.migrations status`

The isolated-database rollback reverses the processing-hardening and Story 1.3 revisions, removes their tables and columns, and retains the Story 1.1 tracer tables and rows. Rehearse it only against a dedicated, disposable database: `.venv/Scripts/python.exe -m backend.app.migrations rollback-core --confirm-isolated-database`. The confirmation flag is mandatory because rollback deletes later-story data. Reapply with the normal `apply` command.

## Azure development transport

The approved development queue is the existing Service Bus **Standard** `vct-connect-standard/vct-analyse`. Correctness does not depend on broker duplicate detection: the transactional outbox republishes ambiguous sends, and the worker compares completed replays against the immutable stored result. Messages use Peek-Lock with automatic lock renewal and settle only after database commit. Retry waits retain and renew the same broker lock within its renewal budget; on budget expiry the Job exits without settlement so a later delivery resumes durable state. Exhausted, malformed, and unknown messages are dead-lettered with bounded reasons. The queue's ten-delivery limit matches the application's bounded attempts. The PostgreSQL-backed local queue remains an optional fallback (`QUEUE_TRANSPORT=local`) and uses the same token-checked transition rules.

## Guest admission and provenance

`POST /api/v1/guest-analyses` accepts the fixture without a Clerk account. The web route issues a random, HttpOnly, SameSite=Lax `vct_guest` cookie and uses it to scope `GET /api/v1/guest-analyses/{id}`; the existing `/api/v1/analyses` routes still require Clerk. Guest analyses create no user row. Accepted guest and customer rows record `GUEST_PUBLIC` or `ACCOUNT_PUBLIC`, actor type, `FIXTURE` extraction method, and scoring version `v0.1.0`. The guest page shows only a fixture preview.

Development admission limits are configurable with `GUEST_BROWSER_LIMIT`, `GUEST_GLOBAL_LIMIT`, `CUSTOMER_LIMIT`, and `ADMISSION_WINDOW_SECONDS`. Their current defaults are 3, 100, 20, and 86400 seconds. These are temporary development guardrails, not final product quotas. PostgreSQL counters enforce each fixed time window in the same transaction as analysis and queue/outbox creation, so a rejected request adds no work. Clearing the browser cookie can reset its individual count; the shared guest cap still bounds total fixture submissions. Set lower values in a test environment to exercise 429 responses without consuming the dev deployment's shared budget.

## Azure development deployment

The approved target is subscription `93bd5d96-c7a2-4072-9aa3-458ab6132d92`, resource group `VCT_Connect_Service_Bus`, region `southeastasia`. Do not create or alter the existing Standard namespace or queue. `scripts/verify_azure_target.py` checks subscription, group, region, queue status, one-minute lock, ten deliveries, and disabled duplicate detection before any deployment. Use interactive `az login` for operator setup; GitHub Actions uses the `main` branch's federated Azure identity. The repository is private at `vuongc4298/vct-connect`.

1. Run `python scripts/verify_azure_target.py` after selecting the target subscription with `az account set --subscription 93bd5d96-c7a2-4072-9aa3-458ab6132d92`. Resolve any mismatch before proceeding.
   Before the first resource rollout, register `Microsoft.Network`, `Microsoft.OperationalInsights`, `Microsoft.App`, `Microsoft.DBforPostgreSQL`, and `Microsoft.Insights` with `az provider register --namespace <name>` and wait until each reports `Registered` through `az provider show --namespace <name> --query registrationState -o tsv`.
2. As an operator with resource group role-assignment permission, deploy `infra/azure/bootstrap.bicep` with the signed-in operator's Entra object ID in `operatorObjectId`. This creates the registry, Key Vault, runtime identity, scoped queue roles, and `main` federated deployment identity. Read its `registryLoginServer`, `vaultName`, and `deployClientId` outputs; the template contains no credentials.
3. In the Key Vault portal, seed `postgres-admin-password` and `clerk-secret-key`. The PostgreSQL module writes the derived `database-url` into Key Vault. Never put any of these values in GitHub variables, build arguments, checked-in files, or command output.
4. Set repository variables `AZURE_CLIENT_ID` (bootstrap's `deployClientId`), `AZURE_TENANT_ID`, `AZURE_REGISTRY_NAME`, `AZURE_KEY_VAULT_NAME`, `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, and `CLERK_ISSUER`. Only the Clerk publishable key is allowed in the web build. Enable GitHub Actions on `main`. The federated identity accepts only the repository's immutable subject `repo:vuongc4298@156062555/vct-connect@1393991860:ref:refs/heads/main`.
5. The `CI` workflow runs Python tests against a PostgreSQL 16 service plus frontend tests, builds the web, scans its artifacts and build log, builds both images, and compiles both templates. Only a successful `main` CI run triggers `Deploy dev`; to rerun deployment, dispatch `CI` on `main` and wait for it to pass. Deployment resolves the pushed image digests, quiesces existing processors, applies the web/API/database and migration Job with queue processing disabled, waits for migrations, then activates the dispatcher and analysis Job. Its automatic smoke checks the web response, unauthenticated rejection, blocked external API ingress, and a completed guest fixture with exact result and provenance. It does not depend on a stored Clerk session.
6. **Required acceptance gate:** After the first deployment, add the web HTTPS domain to the Clerk development instance's allowed origins. Sign in as a test customer and submit the fixture. Verify that the Azure analysis Job succeeds, the queue has no active or dead-lettered messages, and the private PostgreSQL record is `COMPLETED` after one attempt with one result matching `scripts/smoke_dev.py`'s `EXPECTED_RESULT`. The `Verify dev fixture` workflow on `main` automates this gate when a fresh short-lived Clerk session token is stored in Key Vault as `smoke-session-token`; a stale token fails that workflow without breaking automatic deployments. Repeat the gate after material deployment changes.

The web Container App has public HTTPS ingress. FastAPI has internal ingress only; the dispatcher has no ingress and stays at one replica. An event-driven Container Apps Job wakes on a Service Bus message and exits after one receive. Both workers use the runtime managed identity to access Service Bus; the API keeps Clerk verification and owner filtering. PostgreSQL Flexible Server uses a delegated private subnet and has public access disabled. Runtime secrets are Key Vault references. Log Analytics receives Container Apps logs and PostgreSQL diagnostics.

For manual verification, provide a fresh Clerk customer session token through the local process environment as `CLERK_SMOKE_TOKEN`, then run `python scripts/smoke_dev.py --web-url https://<web-fqdn> --api-url https://<api-fqdn>`. The script checks unauthenticated rejection, direct API ingress denial, and one completed fixture result. An operator can also complete the gate through the signed-in web UI and inspect the Job execution, queue counts, and private database record. Inspect the queue DLQ after injected failures. Record cloud acceptance only after one of these paths succeeds against the deployed environment.

For rollback, record the last healthy backend and web registry digest references from the successful deployment, such as `vct-backend@sha256:...` and `vct-web@sha256:...`. Reapply `infra/azure/main.bicep` with the corresponding `backendImageDigest` and `webImageDigest` values and the same nonsecret configuration parameters; a Git SHA tag alone is not a rollback reference because tags can move. Set `enableProcessing=false`, run required migrations inside the private network, then reapply with `enableProcessing=true`. Migrations are not automatically reversed; rehearse database rollback in an isolated database using the command in the migration section before applying any destructive schema change to dev. Run the separate signed-in fixture gate after rollback.

The defaults in `.env.example` bound processing attempts, processing leases, lock renewal, outbox leases, and exponential publication backoff. Logs and API responses contain only stable failure codes; connection strings, payloads, and exception text are not logged.

To inspect the DLQ with Azure CLI, use `az servicebus queue show --resource-group <group> --namespace-name <namespace> --name <queue> --query countDetails.deadLetterMessageCount`. Inspect individual messages with Service Bus Explorer using Peek. Before replay, resolve the recorded failure and confirm the analysis is not already `COMPLETED`; resubmit from the DLQ with the original `MessageId`. Completed replay is safe, while a conflicting payload remains stored and is surfaced as `RESULT_CONFLICT` for operator action.

## Checks

Run `.venv/Scripts/python.exe -m pytest backend/tests`, `npm test --prefix frontend`, `npm run typecheck --prefix frontend`, `npm run build --prefix frontend`, and `docker compose config`. After the production build, run `.venv/Scripts/python.exe scripts/scan_frontend_secrets.py`; it compares configured server credentials without printing them and must report no matches. For PostgreSQL checks, set `VCT_TEST_DATABASE_URL` to a dedicated local test database URL. Migration tests create and remove an isolated schema per test; tracer tests remove their own analysis rows and users. To include the live Service Bus round trip, also set `VCT_TEST_AZURE=true` with Service Bus settings in the test shell; use a dedicated queue. Run `npx -y clerk@latest doctor` from `frontend/apps/web` after Clerk configuration changes.

### Saved-evidence Vietnamese text reports (Oct 6)

Migration `0010_text_reports` adds an independent snapshot-linked report queue and
pre-dispatch spend ledger. Owned completed imports, browser captures, public
extractions, and snapshot replays atomically enqueue a report. Existing owned
completed analyses are backfilled when the migration is applied. Guests never
receive a full report; fixture or blocked extraction has an insufficient state
and incurs no model spend. Extraction status, evidence, admission quotas, and
ownership checks remain authoritative and unchanged.

Reports use the existing authenticated analysis polling endpoint (`text_report`)
with QUEUED, PROCESSING, READY, UNAVAILABLE, INSUFFICIENT, FAILED, or UNCERTAIN
states. The buyer screen continues polling after extraction completes, displays
Vietnamese findings with inspectable evidence IDs, separates observations from
inferences, and shows limitations and pre-order actions. Extraction evidence is
always available as the fallback. Demo scores remain explicitly illustrative
and never enter real interpretation.

**Activation is separate from implementation.** Leave `TEXT_REPORT_ENABLED=false`
until the YEScale chat-completions endpoint, backend-only API key, exact model ID
and model version, contractual conservative input/output USD rates, lifetime
budget, and per-call ceiling are configured. The endpoint must be HTTPS and
accept the OpenAI-compatible chat-completions JSON contract (`messages`, `model`,
`max_tokens`, `response_format`). The returned model must exactly match the
configured ID; an alias that changes its returned model is rejected. Configure
an immutable provider model identifier; the configured version is retained as
operator-provided provenance, not independent proof of provider version.
All missing, malformed, zero, or non-finite cost configuration fails closed.
See `.env.example` for the complete variables. No live activation is performed
by migration or by the tests.

Input is selected normalized business text, bounded to 24,000 serialized UTF-8
bytes by default. Raw HTML, account IDs, supplier identifiers, reviewer names,
contact fields, and URLs are excluded from model input; contact-like text is
redacted. Free text cannot be guaranteed free of every form of personal data.
The prompt treats evidence as untrusted and requires Vietnamese structured JSON.
Output is capped at 2,400 tokens and 48,000 response bytes; requests have a
45-second settlement deadline by default. A late provider response is discarded
and marked uncertain. The underlying HTTP call may finish later; it cannot write
to the database or cause an automatic retry.

Reservations conservatively bound input by UTF-8 bytes plus protocol overhead,
and output by the configured token limit and conservative contractual rates.
Concurrent workers reserve under a PostgreSQL advisory transaction lock against
the total lifetime database budget. Unknown and uncertain costs keep the full
reservation; deleting an analysis does not release that spend ledger entry.
Returned usage may provide a labeled estimate, but actual cost remains null
until independently reconciled: no invoice cost is inferred from usage. Model,
model version, prompt/schema/pipeline versions, returned model, usage, latency,
request ID, and cost provenance are persisted for completed dispatches.

Local and Azure combined/dispatcher loops drain the database report queue;
Azure finite jobs additionally attempt one report before exiting. In Azure,
keep the existing dispatcher active to process report-only imports/captures,
which do not create Service Bus extraction messages. No Azure infrastructure
or deployment is changed by this feature.

A committed READY report is reused. An expired lease before dispatch is safe to
reclaim; an expired lease after the dispatch ledger is committed becomes
UNCERTAIN. Stale settlements are fenced. There is no paid-call replay and no
exactly-once billing claim. For reconciliation, inspect the dispatch ID, provider
request ID, timestamps and usage against provider records; do not reset uncertain
jobs blindly. Requeue an UNAVAILABLE job only after configuration is corrected
and you verify it has no dispatch ledger entry. Actual invoice costs can be
reconciled into `actual_usd` by an operator after confirming their provenance;
do not replace unknown costs with zero.

Offline verification: `python -m pytest backend/tests/test_text_reports.py`;
PostgreSQL verification: set `VCT_TEST_DATABASE_URL` to a disposable database and
run `python -m pytest backend/tests/test_postgres_text_reports.py
backend/tests/test_migrations.py backend/tests/test_postgres_tracer.py`.
The tests create disposable isolated schemas and use a fake provider. Run
`npm test`, `npm run typecheck`, and `npm run build` from `frontend`.
Extension compilation also needs a Clerk publishable key; a test-only placeholder
verifies compilation but cannot verify authentication. Live quality, factual
support of model prose, latency/cost, provider model-version guarantees, and
Azure acceptance require credentials, model pin, approved budget, and a separately
authorized release.

## Interpretation confidence and validation diagnostics

New reports use prompt `vi-text.v8`, schema `text-report.v2`, and prose validation
`vi-prose.v5`. They require
`self_reported_confidence` with a score from 0 to 1 and a Vietnamese basis.
The application labels it `model_self_reported` and `uncalibrated`. It describes
the model's interpretation uncertainty; it is not supplier safety, factual
accuracy, or deterministic assessment confidence. Stored v1 reports reopen
without invented confidence or another provider request.

Rejected output remains `FAILED / INVALID_OUTPUT`. Dispatch metadata retains
only fixed `validation_reason` and allowlisted `validation_location` values:
`SCHEMA_INVALID`, `UNKNOWN_CITATION`, `UNSUPPORTED_SCORE`,
`NON_VIETNAMESE_PROSE`, or `CREDENTIAL_ECHO`. Rejected response text, dynamic
keys and exception messages are not retained. Existing reservations and
one-dispatch fencing apply; neither failed nor uncertain calls auto-retry.
Offline Chinese fixture checks verify transport and persistence only. Live
translation acceptance remains a separate bounded rehearsal.
