"""Check LossFit's Vercel Services routing contract without platform credentials."""

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "vercel.json"


def validate_config(config):
    errors = []
    if config.get("$schema") != "https://openapi.vercel.sh/vercel.json":
        errors.append("$schema must point to Vercel's published vercel.json schema")

    services = config.get("services")
    if not isinstance(services, dict):
        errors.append("services must be an object")
        services = {}

    frontend = services.get("frontend")
    if not isinstance(frontend, dict):
        errors.append("services.frontend must be configured")
    else:
        if frontend.get("root") != "frontend":
            errors.append("services.frontend.root must be frontend")
        if {
            "source": "/(.*)",
            "destination": "/index.html",
        } not in frontend.get("rewrites", []):
            errors.append("the frontend service must preserve React Router deep links")

    backend = services.get("backend")
    if not isinstance(backend, dict):
        errors.append("services.backend must be configured")
    else:
        if backend.get("root") != "backend":
            errors.append("services.backend.root must be backend")
        if backend.get("entrypoint") != "app.main:app":
            errors.append("services.backend.entrypoint must target the FastAPI ASGI app")

    expected_rewrites = [
        {"source": "/api/(.*)", "destination": {"service": "backend"}},
        {"source": "/(.*)", "destination": {"service": "frontend"}},
    ]
    if config.get("rewrites") != expected_rewrites:
        errors.append("top-level rewrites must route /api/* to backend and other paths to frontend")

    return errors


def main():
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"Invalid Vercel config: {error}", file=sys.stderr)
        return 1

    errors = validate_config(config)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("Vercel Services routing contract is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
