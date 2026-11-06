# Vercel deployment status

Updated 2026-11-06. The repository is not deployed to Vercel yet. The current app is a Vite frontend, a FastAPI API, and PostgreSQL; deploying only `frontend/dist` would make the welcome page render, but sign-in, nutrition history, and other persisted workflows would fail without the API. Do not treat that static-only result as the LossFit deployment.

## Current setup

- The Vercel connection is signed in as the LossFit owner's account, but Vercel returned `403 Not authorized` for the owner's default team. A one-use access approval link was generated. The owner must approve the team access request before the connected Vercel tools can list or create projects. The expiring link is shared in the Codex conversation and must not be stored in Git.
- A new, empty Supabase PostgreSQL project named `lossfit-production` was provisioned in `ap-south-1` (Mumbai) on 2026-11-06. Its `public` schema currently has no tables. The current application still uses the local `127.0.0.1:55432` database. Production schema migration, application credentials, and a working Vercel connection are not configured.
- Local `.env` integration values for AI, Google OAuth, and SMTP are empty. Do not copy local secrets or placeholder values to Vercel. Those integrations remain unavailable until separately configured and tested.

## Required before a working deployment

1. Approve Vercel team access and verify the project/repository target.
2. Configure a production PostgreSQL role and TLS connection string with least privilege. Apply and verify the Alembic migrations against the new empty database; never use the local database URL in a deployment.
3. Add the FastAPI API to the Vercel deployment (or another production API runtime) and route `/api/v1/*` to it. Keep the existing browser session, cookie, CSRF, origin, and rate-limit protections intact.
4. Move private uploads from function-local filesystem paths to durable private object storage with owner-authorized reads and retryable deletion. Vercel function filesystems are not the app's persistent private-file store.
5. Set independent production JWT and deletion-ledger secrets, exact HTTPS app/CORS origins, and operational environment values in the provider's encrypted environment-variable store. Add AI/OAuth/SMTP credentials only when available.
6. Deploy a preview first. Verify health/readiness, fresh registration and login, onboarding, nutrition persistence after a new function instance, private-file authorization, export/deletion, cookie/CSRF behavior, and error handling. Promote to production only after the preview passes.

No deployment URL or production readiness is claimed until these checks pass. Vercel build and runtime limits, serverless database pooling, migrations, private storage, and live integrations still require deployment-specific verification.
