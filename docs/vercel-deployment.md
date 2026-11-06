# Vercel deployment status

Updated 2026-11-06. A Vercel project named `lossfit` was created from `newsurvey0098-blip/LossFit` (project ID `prj_5bfTvSY47w2TDk1HfktyUWq9qiJN`, team `team_W2KanS4wc8XeYdHi1KzMJFiY`). GitHub reports the Vercel check succeeded for commit `aa2ed7c`, and the preview host responds by redirecting to Vercel sign-in. This confirms a protected deployment was produced, but its API settings, build logs, application health, and user flows have not been inspected because this connection still receives 403 for team project APIs. Approve team access before further deployment inspection/configuration. `vercel.json` describes one Vercel Services deployment with a Vite frontend and FastAPI backend, routes `/api/*` to the API, and includes a frontend-service fallback for React Router deep links. Vercel Services is currently a Beta product; live routing and runtime health remain unverified.

## Repository deployment shape

- `frontend/` builds the React/Vite browser app.
- `backend/` exports the FastAPI ASGI app as `app.main:app`.
- The root `vercel.json` routes `/api/(.*)` to the backend and other paths to the frontend. The API receives the original `/api/...` path.
- The API uses PostgreSQL and will not be functional in a deployment until it has a production database URL and the Alembic migrations have been applied.
- Private food and scan images use `backend/app/private_storage.py`. Local development uses a private filesystem directory; a configured Vercel Blob store uses private Blob objects. Image bytes are only read through owner-authorized API endpoints; the browser receives no Blob token or public object URL.

## Vercel access and production resources

- GitHub's Vercel check for `aa2ed7c` is `success`, and the preview host redirects to Vercel sign-in. The connected Vercel account returns `403 Not authorized` for team `newsurvey0098-3154`, preventing project/deployment inspection. Team authorization is pending; GitHub collaborator access does not grant Vercel team access.
- Supabase project `lossfit-production` (`gwvmbkjuggacwnckrwow`) is `ACTIVE_HEALTHY` in `ap-south-1`, running PostgreSQL 17.11.0.018. A read-only inspection on 2026-11-06 found no public tables, no migration history, and no health or security advisor findings. It remains an empty provisioned database; production credentials, a least-privilege runtime role, and remote migrations are not configured. The app still points to the local development database.
- Local AI, Google OAuth, and SMTP credentials are empty. Those integrations are unavailable until production credentials are set and live flows are verified.
- USDA Branded search/import is implemented but unavailable until a server-side `FDC_API_KEY` is configured. The key is never sent to the browser. Searches and imports are rate-limited, and imported records are private to the requesting user. USDA requires an API key and directs developers to keep it out of public code; see the [USDA FoodData Central API Guide](https://fdc.nal.usda.gov/api-guide/).

## Required to verify and prepare the protected preview

1. Obtain Vercel team access and inspect the generated deployment for the target project/repository.
2. Verify the project uses Vercel Services. CI checks the manifest's frontend/backend roots, ASGI entrypoint, API routing, and SPA deep-link fallback; the account-level project/config validator still must be run after access is granted. Services availability/configuration must also be verified on the account's plan.
3. Enable automatic exposure of [Vercel system environment variables](https://vercel.com/docs/environment-variables/system-environment-variables) so the runtime receives `VERCEL_ENV` and `VERCEL_URL`. LossFit treats Vercel preview/production as hosted environments, uses secure cookies, and fails startup for missing secrets or durable private storage. Production requires explicit HTTPS `APP_BASE_URL` and `CORS_ORIGINS`; preview may derive its origin from `VERCEL_URL` but still needs its own secrets, database, and private Blob store.
4. Connect a **private** Vercel Blob store to the project and configure `BLOB_STORE_ID`. Private access is required and is selected at store creation. Ensure the runtime receives its Blob credentials through the connected Vercel integration; never place provider tokens in client variables or source control.
5. Configure a production PostgreSQL role with least privilege. For Supabase runtime traffic, use the shared transaction-mode pooler (port 6543), require TLS (`sslmode=require`), and disable prepared statements; the Vercel SQLAlchemy engine is configured with one connection per instance and `prepare_threshold=None`. Run Alembic once from a trusted operator/CI environment with `MIGRATION_DATABASE_URL` set to a separate migration connection (direct port 5432, or session pooler port 5432 where required). Hosted migrations now refuse to run with only the app runtime URL. Keep the migration credential out of Vercel Function environment variables, then verify the schema before routing user traffic.
6. Set environment-scoped JWT and deletion-ledger secrets, exact HTTPS production app/CORS origins, database configuration, and required runtime settings in the encrypted provider environment. Do not upload local `.env` values or reuse production signing keys in previews.
7. Deploy a preview and verify readiness, registration/login, onboarding, persistence across function instances, private image authorization, exports/deletion, cookie and CSRF behavior, and provider outage states.
8. Configure error monitoring without capturing credentials, tokens, request bodies, or health data; record tested backup/restore and deletion-ledger behavior.

## Verification status

The local API and private storage tests are the verification target for the current code change. A successful local test does not establish that Vercel's Python runtime, Blob credentials, project routing, database pooling, backup restore, or live AI/OAuth/SMTP integrations work. There is no deployment URL and no production readiness claim until a preview deployment passes the end-to-end checks above.
