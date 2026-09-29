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

## Azure development deployment

The approved target is subscription `93bd5d96-c7a2-4072-9aa3-458ab6132d92`, resource group `VCT_Connect_Service_Bus`, region `southeastasia`. Do not create or alter the existing Standard namespace or queue. `scripts/verify_azure_target.py` checks subscription, group, region, queue status, one-minute lock, ten deliveries, and disabled duplicate detection before any deployment. Use interactive `az login` for operator setup; GitHub Actions uses the `main` branch's federated Azure identity. The repository is private at `vuongc4298/vct-connect`.

1. Run `python scripts/verify_azure_target.py` after selecting the target subscription with `az account set --subscription 93bd5d96-c7a2-4072-9aa3-458ab6132d92`. Resolve any mismatch before proceeding.
   Before the first resource rollout, register `Microsoft.Network`, `Microsoft.OperationalInsights`, `Microsoft.App`, `Microsoft.DBforPostgreSQL`, and `Microsoft.Insights` with `az provider register --namespace <name>` and wait until each reports `Registered` through `az provider show --namespace <name> --query registrationState -o tsv`.
2. As an operator with resource group role-assignment permission, deploy `infra/azure/bootstrap.bicep` with the signed-in operator's Entra object ID in `operatorObjectId`. This creates the registry, Key Vault, runtime identity, scoped queue roles, and `main` federated deployment identity. Read its `registryLoginServer`, `vaultName`, and `deployClientId` outputs; the template contains no credentials.
3. In the Key Vault portal, seed `postgres-admin-password` and `clerk-secret-key`. The PostgreSQL module writes the derived `database-url` into Key Vault. Never put any of these values in GitHub variables, build arguments, checked-in files, or command output.
4. Set repository variables `AZURE_CLIENT_ID` (bootstrap's `deployClientId`), `AZURE_TENANT_ID`, `AZURE_REGISTRY_NAME`, `AZURE_KEY_VAULT_NAME`, `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, and `CLERK_ISSUER`. Only the Clerk publishable key is allowed in the web build. Enable GitHub Actions on `main`. The federated identity accepts only the repository's immutable subject `repo:vuongc4298@156062555/vct-connect@1393991860:ref:refs/heads/main`.
5. The `CI` workflow runs Python and frontend tests, builds the web, scans its artifacts and build log, builds both images, and compiles both templates. Only a successful `main` CI run triggers `Deploy dev`; to rerun deployment, dispatch `CI` on `main` and wait for it to pass. Deployment resolves the pushed image digests, quiesces existing processors, applies the web/API/database and migration Job with queue processing disabled, waits for migrations, then activates the dispatcher and analysis Job. Its automatic smoke checks the web response, unauthenticated rejection, and blocked external API ingress. It does not depend on a stored Clerk session.
6. **Required acceptance gate:** After the first deployment, add the web HTTPS domain to the Clerk development instance's allowed origins. Sign in as a test customer on that domain, put a fresh short-lived session token in Key Vault as `smoke-session-token`, and run the `Verify dev fixture` workflow on `main`. This separate gate requires a signed-in fixture to reach `COMPLETED` with exactly the known result. Repeat it after material deployment changes and refresh the token immediately before each run. A stale token fails this gate without breaking automatic deployments. The development baseline is not accepted until this gate succeeds.

The web Container App has public HTTPS ingress. FastAPI has internal ingress only; the dispatcher has no ingress and stays at one replica. An event-driven Container Apps Job wakes on a Service Bus message and exits after one receive. Both workers use the runtime managed identity to access Service Bus; the API keeps Clerk verification and owner filtering. PostgreSQL Flexible Server uses a delegated private subnet and has public access disabled. Runtime secrets are Key Vault references. Log Analytics receives Container Apps logs and PostgreSQL diagnostics.

For manual verification, provide a fresh Clerk customer session token through the local process environment as `CLERK_SMOKE_TOKEN`, then run `python scripts/smoke_dev.py --web-url https://<web-fqdn> --api-url https://<api-fqdn>`. The script checks unauthenticated rejection, direct API ingress denial, and one completed fixture result. Inspect Job executions and the queue DLQ after injected failures. Cloud acceptance is recorded only after this succeeds against a deployed environment.

For rollback, record the last healthy backend and web registry digest references from the successful deployment, such as `vct-backend@sha256:...` and `vct-web@sha256:...`. Reapply `infra/azure/main.bicep` with the corresponding `backendImageDigest` and `webImageDigest` values and the same nonsecret configuration parameters; a Git SHA tag alone is not a rollback reference because tags can move. Set `enableProcessing=false`, run required migrations inside the private network, then reapply with `enableProcessing=true`. Migrations are not automatically reversed; rehearse database rollback in an isolated database using the command in the migration section before applying any destructive schema change to dev. Run the separate signed-in fixture gate after rollback.

The defaults in `.env.example` bound processing attempts, processing leases, lock renewal, outbox leases, and exponential publication backoff. Logs and API responses contain only stable failure codes; connection strings, payloads, and exception text are not logged.

To inspect the DLQ with Azure CLI, use `az servicebus queue show --resource-group <group> --namespace-name <namespace> --name <queue> --query countDetails.deadLetterMessageCount`. Inspect individual messages with Service Bus Explorer using Peek. Before replay, resolve the recorded failure and confirm the analysis is not already `COMPLETED`; resubmit from the DLQ with the original `MessageId`. Completed replay is safe, while a conflicting payload remains stored and is surfaced as `RESULT_CONFLICT` for operator action.

## Checks

Run `.venv/Scripts/python.exe -m pytest backend/tests`, `npm test --prefix frontend`, `npm run typecheck --prefix frontend`, `npm run build --prefix frontend`, and `docker compose config`. After the production build, run `.venv/Scripts/python.exe scripts/scan_frontend_secrets.py`; it compares configured server credentials without printing them and must report no matches. For PostgreSQL checks, set `VCT_TEST_DATABASE_URL` to a dedicated local test database URL. Migration tests create and remove an isolated schema per test; tracer tests remove their own analysis rows and users. To include the live Service Bus round trip, also set `VCT_TEST_AZURE=true` with Service Bus settings in the test shell; use a dedicated queue. Run `npx -y clerk@latest doctor` from `frontend/apps/web` after Clerk configuration changes.
