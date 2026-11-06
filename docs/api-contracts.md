# API contract generation

FastAPI is the source of truth for request schemas and route parameters. The committed `backend/openapi.json` snapshot and `frontend/src/api-types.ts` declarations are generated from the live application schema; do not edit either generated file by hand.

From the repository root on Windows, activate the project environment or run:

```powershell
.\.venv\Scripts\python.exe scripts\generate-api-types.py
```

The backend CI job runs `python scripts/generate-api-types.py --check` and fails if either artifact differs from FastAPI's current OpenAPI output. Backend tests also compare the committed artifacts with the live schema and exercise schema-to-TypeScript conversion for required, optional, nullable, array, and request-body fields.

Frontend code can use `jsonBody(operationId, value)` from `src/api.ts` to serialize a request body whose shape is checked against the generated operation contract. Responses whose FastAPI handlers do not declare response models are represented as `unknown` in generated OpenAPI types; frontend response models remain explicit at call sites until those API handlers are given concrete response models. This prevents an empty OpenAPI response schema from being mistaken for a validated response type.
