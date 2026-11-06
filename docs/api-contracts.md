# API contract generation

FastAPI is the source of truth for request schemas and route parameters. The committed `backend/openapi.json` snapshot and `frontend/src/api-types.ts` declarations are generated from the live application schema; do not edit either generated file by hand.

From the repository root on Windows, activate the project environment or run:

```powershell
.\.venv\Scripts\python.exe scripts\generate-api-types.py
```

The backend CI job runs `python scripts/generate-api-types.py --check` and fails if either artifact differs from FastAPI's current OpenAPI output. Backend tests also compare the committed artifacts with the live schema and exercise schema-to-TypeScript conversion for required, optional, nullable, array, and request-body fields.

Frontend code can use `jsonBody(operationId, value)` from `src/api.ts` to serialize a request body whose shape is checked against the generated operation contract. JSON success responses declare Pydantic response models and the generator test rejects any unmodeled JSON success payload. CSV and private images declare their actual media types; the Google OAuth callback is documented as a redirect. This prevents empty OpenAPI response schemas from being mistaken for validated response types.
