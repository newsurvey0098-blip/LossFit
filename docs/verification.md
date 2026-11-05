# Implementation evidence

## Verified setup
- Empty workspace inspected; local Git initialized.
- ZIP extracted with path traversal checks: 21 HTML exports, 21 screenshots, and Obsidian design guide.
- All export text read; all screenshots visually reviewed in three contact sheets. Supplementary screenshots reviewed in conversation.
- Python virtual environment created and dependencies installed; exact installed versions recorded in backend/requirements.txt.
- Project-local Node 22.23.4 downloaded with SHA256 verification.
- Isolated PostgreSQL cluster created, started on port 55432, and `lossfit` database connected successfully.
- Frontend production build succeeded with Vite 6.4.5.
- API smoke flow verified: readiness, registration, authenticated user lookup, CSRF-protected meal creation, and persisted meal retrieval. A 150g entry at 100 kcal and 10g protein per 100g returned 150 kcal and 15g protein.
- On 2026-11-06, Alembic upgraded a newly created empty PostgreSQL database through all eleven revisions. Current head: `41c6a2d8e903`. The configured `lossfit` development database was also upgraded from its prior early revision to this head.
- On 2026-11-06, `scripts/test.ps1` created a unique empty PostgreSQL test database, applied all migrations, and the core API suite reported `23 passed`. Coverage includes registration, persisted meal calculations/summary/export, CSRF/origin checks, refresh-token rotation and replay rejection, logout/session revocation, cross-user isolation, profile goals, nullable nutrition, meal edits/deletes, conversations, deterministic mocked assistant context, onboarding/weight persistence, expiring single-use password resets, confirmed account deletion with personal-data cleanup, server-side catalogue nutrition resolution, nutrition snapshot preservation after catalogue edits/deletion, serving privacy, invalid-nutrient rejection, user-local history/export date boundaries, private image validation/access control, candidate resolution, idempotent scanner confirmation, persistent upload rate limiting, lesson sources and variants, quiz completion and private progress persistence.
- On 2026-11-06, the frontend TypeScript/Vite production build passed after adding forgot/reset password, account deletion, custom food editing, serving selection, new-meal composition, adding foods to existing meals, date-filtered food log, 7/30/90-day analytics, scanner/review pages, in-memory access tokens, automatic refresh, authorized private scan-image retrieval, and sourced learning lessons with quizzes.

## In progress
- The first dashboard and catalogue views and initial persisted API are foundations only.
- Dashboard numbers and hydration, catalogue search, manual foods, food detail portion selection, meal logging, profile goals, and data exports now use the authenticated API.
- Short-lived access JWTs are kept in frontend memory; rotating 30-day refresh tokens are hashed in PostgreSQL and sent in HttpOnly SameSite=Lax cookies, with the Secure flag enabled in production. CSRF and configured-origin checks cover refresh and logout. Refresh rotation, replay rejection, logout revocation, and authorization checks are included in the automated suite. Verified imported public catalogue data, RAG ingestion and citations, OAuth linking, browser E2E, backup restore drill, and broad security/accessibility review remain outstanding. Persistent database-backed limits cover registration, login, reset requests/attempts, scanner uploads/confirmation, assistant calls, and refresh; only scanner limits currently have an explicit regression test. Scanner upload/review/confirmation flows are implemented and provider behavior was tested with a deterministic mock; live vision credentials are unavailable and the live provider is unverified. Analytics/log/scanner routes have not received browser/manual visual verification. Password recovery endpoints and screens are implemented; SMTP delivery is unverified. Account deletion removes personal records and scanner files and stores an HMAC email marker; automated restore-time replay and retryable file cleanup are not yet implemented.
- The configured AI integration uses an OpenAI-compatible chat endpoint; live provider credentials are not configured and no live-provider call has been verified. Source-linked learning lessons, explanation levels, quizzes, and private progress persistence are implemented and API-tested. Retrieval-augmented assistant citations remain outstanding.
- npm reported three dependency audit findings (one moderate, two critical); they require review before release.

No application feature is yet claimed complete. No deployment has been performed.

Browser preview was not verified. No deployment has been performed.
