# LossFit

LossFit is a nutrition tracking application being built from the supplied screen references. The UI reference assets live under `references/` and are intentionally excluded from Git.

## Local Windows setup

1. Install Python 3.12 and PostgreSQL 18. Node 22.23.4 is project-local in `.runtime/` (the setup downloads it and verifies its published SHA256).
2. Copy `.env.example` to `.env`, then set unique `JWT_SECRET` and stable `DELETION_LEDGER_SECRET` values. Do not rotate the deletion-ledger key while retained backups may need replay.
3. Create the Python environment and install `backend/requirements.txt`.
4. Run `scripts/start-db.ps1` to initialize/start the isolated project cluster on port 55432.
5. Run `alembic -c backend/alembic.ini upgrade head` from the repository root.
6. Run `scripts/start-dev.ps1`. Frontend is at `http://127.0.0.1:5173`; API at `http://127.0.0.1:3001/docs`.

The initial migration was applied to an empty local database. The current schema is an early foundation and is not production ready.

Password reset is enabled only when `SMTP_HOST` and `SMTP_FROM` are set. Configure an SMTP relay with `SMTP_SECURITY=ssl` (typically port 465) or `SMTP_SECURITY=starttls` (typically port 587), credentials where required, and `APP_BASE_URL` for the reset link. TLS certificates and hostnames are verified against the system trust store. Without SMTP, the endpoint returns the same privacy-preserving response but cannot deliver a reset email.

Google account linking is optional. Set backend-only `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REDIRECT_URI`; register that exact callback URI in Google Cloud Console. For local development, the callback is `http://127.0.0.1:3001/api/v1/auth/google/callback`. Without all three values, the connected-accounts screen clearly reports that Google linking is unavailable.

Authentication returns a 20-minute access token held only in frontend memory. A rotating 30-day refresh token is stored as a hash in PostgreSQL and sent in an HttpOnly, SameSite=Lax cookie scoped to `/api/v1/auth`; production sets `Secure`. Refresh and logout require the readable double-submit CSRF token and an allowed `Origin`. To configure a separate test database, set `DATABASE_URL` for both Alembic and pytest before running them; do not point tests at a production database.

Run repeatable API tests with `scripts/test.ps1` after the isolated PostgreSQL cluster is running. The script creates a uniquely named database, applies all migrations, runs the suite, and retains that database so failures can be inspected.

Frontend tests run with `npm.cmd test` from `frontend/`. The Chromium browser smoke flow runs with `npm.cmd run test:e2e`; it starts Vite on port 4173 and expects Google Chrome Stable to be installed. This browser flow stubs API responses to verify the signed-out redirect, login return path, and layout overflow at 390px, 768px, and 1440px. For a real browser-to-API persistence flow, run `npm.cmd run test:e2e:local`; it creates a fresh temporary PostgreSQL database, migrates it, starts the API and Vite, tests registration through meal reload, then drops only its uniquely named temporary database. Start the isolated PostgreSQL cluster first.

Reviewed nutrition documents are curated in `backend/knowledge/sources.json`; ingest them with `.venv/Scripts/python.exe scripts/ingest-knowledge.py` after migrations. Each source version is immutable: edit the text only when you also increase its version. Set backend-only `EMBEDDING_MODEL` alongside the AI provider URL/key to create embeddings. Without that setting the portable lexical retrieval adapter is used. The assistant supplies source markers and links from retrieved chunks and is instructed to abstain on unsupported general nutrition claims. Live provider answers and embeddings still require separate verification.

Populate the shared food catalogue with `.venv/Scripts/python.exe scripts/import-foods.py` after migrations. This pins and SHA-256 checks the USDA Foundation Foods October 2026 release and FNDDS 2021–2023 release, imports preparation variants and measured household portions, and retains FDC IDs and source links. Analytical Foundation values are marked verified; calculated Foundation and FNDDS values are marked reviewed. Negative or non-finite nutrient values are left unavailable with an explicit note; nutrients absent from a source remain null. Branded Foods are not included. The data archives are cached under ignored `.local/cache/` and can be downloaded again by the importer.

Account deletion removes the account's application records in one database transaction and records a keyed email digest in a restricted ledger. Failed private-file removals remain in the internal cleanup queue; retry them with `.venv/Scripts/python.exe scripts/cleanup-private-files.py`. Configure vision credentials in backend-only `AI_BASE_URL`, `AI_API_KEY`, and `VISION_MODEL` values to enable the photo scanner. A restore procedure must replay a separately preserved deletion ledger against restored user tables before serving traffic. Database backups may retain old personal data until their configured retention expires; the ledger is intended to prevent those restores from reactivating deleted accounts.

## Production operations

See [deployment and monitoring](docs/deployment.md) for the production environment template, fail-closed HTTPS/secret checks, sanitized JSON request events, production launcher, reverse-proxy template, and verification gates. No deployment or external alert destination has been verified.

Set `ENVIRONMENT=production`, a random secret, HTTPS origins, restricted CORS, provider credentials only in the backend secret store, and private upload storage outside the web root. Enable database backups with `pg_dump -Fc`; restore to an isolated database with `pg_restore --clean --if-exists`. Establish encrypted offsite retention and deletion-ledger replay before production. Configure error monitoring with request-body and credential scrubbing.

See [backup and restore procedures](docs/backup-restore.md) for Windows PowerShell commands, protected deletion-ledger export, dry-run review, replay, and private-file cleanup.

## Implementation status

See [screen inventory](docs/screen-inventory.md), [verification record](docs/verification.md), and [GitHub milestone workflow](docs/github-workflow.md). LossFit has persisted account, nutrition, meal, assistant, analytics, privacy, and learning workflows with automated API and browser verification. The acceptance record identifies features that remain partial or unavailable. Live AI/OAuth integrations and production deployment have not been verified; the application is not yet production ready.
