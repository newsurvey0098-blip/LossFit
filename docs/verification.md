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
- On 2026-11-05, Alembic upgraded a newly created empty PostgreSQL database through all six revisions. Current head: `7f83ad201c4a`.
- On 2026-11-05, the core API regression suite reported `15 passed` against the isolated `lossfit_migrationcheck` database. Coverage includes registration, persisted meal calculations/summary/export, CSRF/origin checks, cross-user isolation, profile goals, nullable nutrition, meal edits/deletes, conversations, deterministic mocked assistant context, onboarding/weight persistence, expiring single-use password resets, and confirmed account deletion with personal-data cleanup.
- On 2026-11-05, the frontend TypeScript/Vite production build passed after adding forgot/reset password and account deletion flows.

## In progress
- The first dashboard and catalogue views and initial persisted API are foundations only.
- Dashboard numbers and hydration, catalogue search, manual foods, food detail portion selection, meal logging, profile goals, and data exports now use the authenticated API.
- Refresh-token rotation, catalogue provenance/serving data migration, scanner, RAG, learning, OAuth linking, persistent rate limits, private uploads, browser E2E, backup restore drill, and broad security/accessibility review remain outstanding. Password recovery endpoints and screens are implemented; SMTP delivery has not been verified against a live mail service. Account deletion removes personal records and stores an HMAC email marker; automated restore-time replay of this ledger and file cleanup retries are not yet implemented.
- The configured AI integration uses an OpenAI-compatible chat endpoint; live provider credentials are not configured and no live-provider call has been verified. RAG citations and learning features remain outstanding.
- npm reported three dependency audit findings (one moderate, two critical); they require review before release.

No application feature is yet claimed complete. No deployment has been performed.

Browser preview was not verified. No deployment has been performed.
