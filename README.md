# LossFit

LossFit is a nutrition tracking application being built from the supplied screen references. The UI reference assets live under `references/` and are intentionally excluded from Git.

## Local Windows setup

1. Install Python 3.12 and PostgreSQL 18. Node 22.23.4 is project-local in `.runtime/` (the setup downloads it and verifies its published SHA256).
2. Copy `.env.example` to `.env`, then set a unique `JWT_SECRET`.
3. Create the Python environment and install `backend/requirements.txt`.
4. Run `scripts/start-db.ps1` to initialize/start the isolated project cluster on port 55432.
5. Run `alembic -c backend/alembic.ini upgrade head` from the repository root.
6. Run `scripts/start-dev.ps1`. Frontend is at `http://127.0.0.1:5173`; API at `http://127.0.0.1:3001/docs`.

The initial migration was applied to an empty local database. The current schema is an early foundation and is not production ready.

Password reset is enabled only when `SMTP_HOST` and `SMTP_FROM` are set. Configure an SSL SMTP relay (`SMTP_PORT`, default 465), credentials where required, and `APP_BASE_URL` for the reset link. Without SMTP, the endpoint returns the same privacy-preserving response but cannot deliver a reset email.

Account deletion removes the account's application records in one database transaction and records a keyed email digest in a restricted ledger. A restore procedure must replay this ledger against restored user tables before serving traffic. Database backups may retain old personal data until their configured retention expires; the ledger is intended to prevent those restores from reactivating deleted accounts.

## Production operations

Set `ENVIRONMENT=production`, a random secret, HTTPS origins, restricted CORS, provider credentials only in the backend secret store, and private upload storage outside the web root. Enable database backups with `pg_dump -Fc`; restore to an isolated database with `pg_restore --clean --if-exists`. Establish encrypted offsite retention and deletion-ledger replay before production. Configure error monitoring with request-body and credential scrubbing.

## Implementation status

See [screen inventory](docs/screen-inventory.md) and [verification record](docs/verification.md). Current screens and endpoints are foundations; the complete workflows and production security described in the requirements remain outstanding.
