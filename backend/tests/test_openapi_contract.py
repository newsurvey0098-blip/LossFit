from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("lossfit_api_type_generator", ROOT / "scripts" / "generate-api-types.py")
GENERATOR = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(GENERATOR)


def test_generated_openapi_and_frontend_contract_are_current():
    import json

    from backend.app.main import app

    openapi = app.openapi()
    snapshot = json.loads((ROOT / "backend" / "openapi.json").read_text(encoding="utf-8"))
    assert snapshot == openapi
    generated = (ROOT / "frontend" / "src" / "api-types.ts").read_text(encoding="utf-8")
    assert generated == GENERATOR.render_types(openapi)


def test_openapi_schema_mapping_handles_optional_fields_and_nulls():
    schema = {
        "type": "object",
        "required": ["name"],
        "properties": {
            "name": {"type": "string"},
            "amount": {"anyOf": [{"type": "number"}, {"type": "null"}]},
            "items": {"type": "array", "items": {"type": "integer"}},
        },
    }
    assert GENERATOR.schema_type(schema) == '{ "name": string; "amount"?: (number) | (null); "items"?: Array<number>; }'


def test_openapi_paths_include_generated_request_body_contracts():
    generated = (ROOT / "frontend" / "src" / "api-types.ts").read_text(encoding="utf-8")
    assert '"register_api_v1_auth_register_post"' in generated
    assert '"add_food_api_v1_foods_post"' in generated
    assert '"add_meal_api_v1_meals_post"' in generated
    assert '"application/json": components["schemas"]["MealIn"]' in generated
