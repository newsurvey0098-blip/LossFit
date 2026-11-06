# Vercel deployment status

Updated 2026-11-06. LossFit is not deployed to Vercel. `vercel.json` now describes one Vercel Services deployment with a Vite frontend and FastAPI backend, routes `/api/*` to the API, and includes a frontend-service fallback for React Router deep links. Vercel Services is currently a Beta product; this routing has not yet been validated by a live Vercel deployment.

## Repository deployment shape

- `frontend/` builds the React/Vite browser app.
- `backend/` exports the FastAPI ASGI app as `app.main:app`.
- The root `vercel.json` routes `/api/(.*)` to the backend and other paths to the frontend. The API receives the original `/api/...` path.
- The API uses PostgreSQL and will not be functional in a deployment until it has a production database URL and the Alembic migrations have been applied.
- Private food and scan images use `backend/app/private_storage.py`. Local development uses a private filesystem directory; a configured Vercel Blob store uses private Blob objects. Image bytes are only read through owner-authorized API endpoints; the browser receives no Blob token or public object URL.

## Vercel access and production resources

- The connected Vercel account previously returned `403 Not authorized` for its default team. A temporary access-approval URL was generated, but it expires; request a fresh one through the connected Vercel integration when the owner is ready to approve it. GitHub collaborator access does not grant Vercel team access.
- A new, empty Supabase PostgreSQL project named `lossfit-production` was provisioned in `ap-south-1` on 2026-11-06. Its public schema has no application tables. The app still points to the local development database.
- Local AI, Google OAuth, and SMTP credentials are empty. Those integrations are unavailable until production credentials are set and live flows are verified.

## Required before preview deployment

1. Obtain Vercel team access and confirm the target project/repository.
2. Configure the project to use Vercel Services and validate the root `vercel.json` with Vercel's project/config validator. Services is in Beta and availability/configuration must be verified on the account's plan.
3. Enable automatic exposure of [Vercel system environment variables](https://vercel.com/docs/environment-variables/system-environment-variables) so the runtime receives `VERCEL_ENV` and `VERCEL_URL`. LossFit treats Vercel preview/production as hosted environments, uses secure cookies, and fails startup for missing secrets or durable private storage. Production requires explicit HTTPS `APP_BASE_URL` and `CORS_ORIGINS`; preview may derive its origin from `VERCEL_URL` but still needs its own secrets, database, and private Blob store.
4. Connect a **private** Vercel Blob store to the project and configure `BLOB_STORE_ID`. Private access is required and is selected at store creation. Ensure the runtime receives its Blob credentials through the connected Vercel integration; never place provider tokens in client variables or source control.
5. Configure a production PostgreSQL role with least privilege. For Supabase, use the shared transaction-mode pooler (port 6543), require TLS (`sslmode=require`), and disable prepared statements; the Vercel SQLAlchemy engine is configured with one connection per instance and `prepare_threshold=None`. Apply Alembic migrations through a direct migration connection, then verify them before routing user traffic.
6. Set environment-scoped JWT and deletion-ledger secrets, exact HTTPS production app/CORS origins, database configuration, and required runtime settings in the encrypted provider environment. Do not upload local `.env` values or reuse production signing keys in previews.
7. Deploy a preview and verify readiness, registration/login, onboarding, persistence across function instances, private image authorization, exports/deletion, cookie and CSRF behavior, and provider outage states.
8. Configure error monitoring without capturing credentials, tokens, request bodies, or health data; record tested backup/restore and deletion-ledger behavior.

## Verification status

The local API and private storage tests are the verification target for the current code change. A successful local test does not establish that Vercel's Python runtime, Blob credentials, project routing, database pooling, backup restore, or live AI/OAuth/SMTP integrations work. There is no deployment URL and no production readiness claim until a preview deployment passes the end-to-end checks above.
