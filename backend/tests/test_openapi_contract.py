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
    assert '"201": { content: { "application/json": components["schemas"]["AuthSessionOut"]' in generated
    assert '"201": { content: { "application/json": components["schemas"]["FoodOut"]' in generated
    assert '"201": { content: { "application/json": components["schemas"]["MealOut"]' in generated


def test_every_json_success_response_has_a_declared_schema():
    import json

    schema = json.loads((ROOT / "backend" / "openapi.json").read_text(encoding="utf-8"))
    missing = [
        f"{method.upper()} {path} -> {status}"
        for path, path_item in schema["paths"].items()
        for method, operation in path_item.items()
        for status, response in operation.get("responses", {}).items()
        if status.startswith("2")
        and response.get("content", {}).get("application/json", {}).get("schema") == {}
    ]
    assert missing == []


def test_every_private_api_route_requires_an_authenticated_user():
    from fastapi.routing import APIRoute

    from backend.app.main import app, current_user

    public_routes = {
        "/api/v1/health/live",
        "/api/v1/health/ready",
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/forgot-password",
        "/api/v1/auth/reset-password",
        "/api/v1/auth/logout",
        "/api/v1/auth/google/callback",
    }

    def has_authenticated_user_dependency(dependant) -> bool:
        return dependant.call is current_user or any(
            has_authenticated_user_dependency(child) for child in dependant.dependencies
        )

    unprotected = [
        f"{method} {route.path}"
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path.startswith("/api/v1/")
        and route.path not in public_routes
        and not has_authenticated_user_dependency(route.dependant)
        for method in route.methods or []
    ]
    assert unprotected == []
