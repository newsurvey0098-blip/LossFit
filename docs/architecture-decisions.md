# Architecture decisions

## Authentication sessions

- Access JWTs last 20 minutes and stay in browser memory. Refresh credentials are random opaque tokens, stored only as SHA-256 digests in PostgreSQL and delivered through a path-scoped HttpOnly cookie.
- Every access JWT refers to a revocable database session. Logout revokes that session; a password reset revokes every session for the account.
- CSRF is enforced for refresh/logout when the ambient refresh cookie is present. Requests also need a configured origin and matching double-submit token.

## Assistant retries

- Each assistant turn uses a client-generated idempotency key scoped to its conversation. The backend serializes writes per conversation and stores prompt, final answer, and citations under a unique key. A retry returns that saved result without calling the provider or appending another message pair; reusing a key with different prompt text is rejected.
- Provider failures do not persist partial turns. The browser retains the key while offering a retry for the same pending text.

## Nutrition and history

- The API resolves catalogue food nutrition and portions before writing a meal. Scanner and assistant suggestions cannot set authoritative nutrients.
- Meal items retain copied food, portion, preparation, nutrition, verification, and source fields so later catalogue edits do not change historical meals.
- Missing values remain null. They are never silently interpreted as measured zero.
- Public catalogue imports pin SHA-256 checked USDA Foundation Foods and FNDDS archives. Each nutrient carries its own analytical/reviewed status and source derivation; negative source values are withheld with a visible data note. The initial catalogue deliberately excludes the much larger branded-food release; imported source record IDs can be extended without changing the food or snapshot contract.

## Knowledge retrieval

- Reviewed documents are human-curated paraphrases stored in `backend/knowledge/sources.json`; ingestion records their source URL, organization, content hash, and version. A changed source requires a new version, retaining the old record for auditability.
- Ingestion splits text into overlapping word windows and requests embeddings only when `AI_BASE_URL`, `AI_API_KEY`, and `EMBEDDING_MODEL` are configured. Provider secrets remain server-side.
- Embeddings use PostgreSQL JSON storage and a Python cosine-similarity adapter, with token overlap as the portable offline fallback. This avoids requiring a PostgreSQL extension in the Windows development setup. Large corpora should migrate behind the same retrieval boundary to pgvector or a managed vector index.
- Assistant prompts receive only matched chunks and source metadata. The assistant must cite retrieved facts with stable in-answer markers and abstain when reviewed evidence is missing. Citation metadata is persisted on the assistant message and returned with conversation history.

## Test data isolation

- `scripts/test.ps1` creates a new uniquely named database for each run, applies all migrations, and retains it for inspection. Persistent abuse limits therefore cannot make a later test run fail due to earlier test traffic.
