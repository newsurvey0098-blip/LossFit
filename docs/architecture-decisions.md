# Architecture decisions

## User recipes

Recipes are private catalogue foods with a JSON ingredient snapshot and finished yield. Creation and editing share the authoritative meal-item resolver and nutrient calculator. Each nutrient remains unknown if any contributing ingredient lacks it; known totals are divided by the finished yield for per-100g values. Recipe nutrition is estimated and explicitly does not model cooking retention losses. Editing portions or yield preserves ingredient snapshots; removing and re-adding an ingredient resolves the latest accessible catalogue version. Meal snapshots embed recipe provenance so editing/deleting a recipe cannot rewrite logged nutrition. Self-inclusion, oversized snapshots, invalid quantities, and implausibly small yields are rejected. Existing manual-food editing cannot override recipe-calculated values.

## Authentication sessions

- Access JWTs last 20 minutes and stay in browser memory. Refresh credentials are random opaque tokens, stored only as SHA-256 digests in PostgreSQL and delivered through a path-scoped HttpOnly cookie.
- Every access JWT refers to a revocable database session. Logout revokes that session; a password reset revokes every session for the account.
- CSRF is enforced for refresh/logout when the ambient refresh cookie is present. Requests also need a configured origin and matching double-submit token.

## Meal reminders

- Reminder enablement and validated 24-hour meal times are stored in the existing owner-scoped preferences JSON. The authenticated shell checks the configured profile timezone while a browser tab is open, emits an accessible in-app notice during the scheduled minute, and records that user/date/meal notice in the current browser's local storage to avoid repeating it on reload. Dismissal, opening the meal form, and settings persistence are available without a push-service dependency.
- Background reminders are not delivered when the application is closed or suspended. Web Push credentials and a service worker subscription lifecycle are not configured; the profile explains this limit and does not imply that a saved schedule guarantees a notification.

## Google account linking

- Linking starts only after password reauthentication. The server stores a one-use, ten-minute state digest, nonce, and JWT-secret-derived encrypted PKCE verifier; Google secrets remain server-side.
- The callback validates Google’s ID token signature, issuer, audience, and expiry through `google-auth`, then checks the one-time nonce and verified email claim. The stable Google subject is unique and is attached only to the account that initiated the flow. Email equality never merges LossFit users.
- Unlink also requires the LossFit password. Every account has a password login method, so unlinking Google cannot remove the last usable login method. Live linking stays unavailable until credentials and an exactly matching redirect URI are configured.

## Assistant retries

- Each assistant turn uses a client-generated idempotency key scoped to its conversation. The backend serializes writes per conversation and stores prompt, final answer, and citations under a unique key. A retry returns that saved result without calling the provider or appending another message pair; reusing a key with different prompt text is rejected.
- Provider failures do not persist partial turns. The browser retains the key while offering a retry for the same pending text.
- Daily assistant totals use the same profile-local calendar bounds as dashboard history. User-entered preference text is treated as untrusted data and cannot override assistant safety and evidence rules.

## Assistant action confirmation

- Assistant actions are registered server operations. `log_water` stores an owner-scoped preview bound to an owned conversation and an idempotency key; the preview includes the user's local date and current hydration total. `log_meal` resolves catalogue nutrition and stores a preparation-specific item snapshot with server-calculated totals.
- A preview does not write health data. Confirmation rechecks ownership, expiry, supported action, local date, and whether the hydration total changed. It then writes the water entry and confirmation audit in one transaction; repeated confirmation returns the saved result.
- The UI asks the user to confirm each action before it is recorded. Confirmations recheck private-food ownership and store the meal, water entry, result, and audit status atomically. Model tool calls are bounded and strictly schema-validated; read-only catalogue search results are tracked so a proposed meal cannot reference an unseen or fabricated food ID. The registered write actions are water and meals with 1–10 catalogue-resolved items; both model proposals and the manual quick-action form support up to ten foods. Proposal creation and the assistant turn share one transaction; the generated request key is namespaced away from user preview keys, and confirmed writes continue through the shared idempotent action service. Adding new action types requires its own validation, authorization, replay, and confirmation tests.

## Private file deletion

- Scan-file paths are placed in an internal cleanup queue in the same transaction that removes the owning scan/account. Files are unlinked only after resolving under the configured private-upload root; failed or unsafe paths remain queued for operator review/retry.
- `scripts/cleanup-private-files.py` drains the queue without printing file paths. The queue survives account deletion and has no user-facing API.

## Nutrition and history

- The API resolves catalogue food nutrition and portions before writing a meal. Scanner and assistant suggestions cannot set authoritative nutrients.
- Meal items retain copied food, portion, preparation, nutrition, verification, and source fields so later catalogue edits do not change historical meals.
- Missing values remain null. They are never silently interpreted as measured zero.
- Public catalogue imports pin SHA-256 checked USDA Foundation Foods and FNDDS archives. Each nutrient carries its own analytical/reviewed status and source derivation; negative source values are withheld with a visible data note. USDA Branded products are searched on demand with a server-side data.gov API key, then imported into the requesting user's private catalogue with `imported` nutrient provenance and a historical meal snapshot. No periodic branded-catalog refresh runs; a missing API key is reported as unavailable, while barcode and manual entry continue to work.

## Knowledge retrieval

- Reviewed documents are human-curated paraphrases stored in `backend/knowledge/sources.json`; ingestion records their source URL, organization, content hash, and version. A changed source requires a new version, retaining the old record for auditability.
- Ingestion splits text into overlapping word windows and requests embeddings only when `AI_BASE_URL`, `AI_API_KEY`, and `EMBEDDING_MODEL` are configured. Provider secrets remain server-side.
- Embeddings remain in PostgreSQL JSON for portable recovery. When the `vector` extension is available, an optional backend-role-only pgvector sidecar stores and ranks exact cosine-nearest candidates; the current reviewed corpus is small enough to use exact search. On local PostgreSQL builds without the extension, the same retrieval boundary uses Python cosine similarity and token overlap. If the corpus grows substantially, add model/dimension-specific HNSW indexes or a managed vector index without changing the source-version or citation contracts. Supabase supports the extension when enabled in its database settings; see the [Supabase pgvector guide](https://supabase.com/docs/guides/database/extensions/pgvector) and the [pgvector project documentation](https://github.com/pgvector/pgvector).
- Assistant prompts receive only matched chunks and source metadata. The assistant must cite retrieved facts with stable in-answer markers and abstain when reviewed evidence is missing. Citation metadata is persisted on the assistant message and returned with conversation history.

## Test data isolation

- `scripts/test.ps1` creates a new uniquely named database for each run, applies all migrations, and retains it for inspection. Persistent abuse limits therefore cannot make a later test run fail due to earlier test traffic.
