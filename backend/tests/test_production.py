from pathlib import Path

import pytest
from backend.app.production import (
    configured_app_base_url,
    configured_cors_origins,
    is_production_environment,
    is_secure_cookie_environment,
    validate_production_environment,
)


def valid():
    return {
        "ENVIRONMENT": "production",
        "JWT_SECRET": "a" * 48,
        "DELETION_LEDGER_SECRET": "b" * 48,
        "CORS_ORIGINS": "https://lossfit.example",
        "APP_BASE_URL": "https://lossfit.example",
        "PRIVATE_UPLOAD_DIR": str(Path.cwd() / "private-uploads"),
    }


@pytest.mark.parametrize(
    "name,value",
    [
        ("JWT_SECRET", "replace-with-a-random-secret-of-at-least-32-characters"),
        ("DELETION_LEDGER_SECRET", "short"),
        ("CORS_ORIGINS", "*"),
        ("CORS_ORIGINS", "http://localhost:5173"),
        ("APP_BASE_URL", "https://user:secret@example.com"),
        ("CORS_ORIGINS", "https://example.com/private"),
        ("APP_BASE_URL", ""),
    ],
)
def test_production_rejects_unsafe_configuration(name, value):
    env = valid()
    env[name] = value
    with pytest.raises(RuntimeError):
        validate_production_environment(env)


def test_production_accepts_explicit_https_origins_and_development_remains_local():
    validate_production_environment(valid())
    validate_production_environment({"ENVIRONMENT": "development"})


def test_production_requires_durable_private_file_storage():
    env = valid()
    env.pop("PRIVATE_UPLOAD_DIR")
    with pytest.raises(RuntimeError, match="private Blob storage"):
        validate_production_environment(env)
    env = valid()
    env["BLOB_STORE_ID"] = "store_lossfit"
    validate_production_environment(env)


def test_production_rejects_relative_private_upload_directory():
    env = valid()
    env["PRIVATE_UPLOAD_DIR"] = "uploads"
    with pytest.raises(RuntimeError, match="absolute persistent directory"):
        validate_production_environment(env)


def test_vercel_production_uses_system_environment_and_fails_closed():
    env = valid()
    env.pop("ENVIRONMENT")
    env["VERCEL_ENV"] = "production"
    validate_production_environment(env)
    assert is_production_environment(env)
    assert is_secure_cookie_environment(env)

    env.pop("APP_BASE_URL")
    with pytest.raises(RuntimeError, match="explicit HTTPS APP_BASE_URL"):
        validate_production_environment(env)


def test_vercel_preview_derives_its_https_origin_and_still_requires_secrets_and_storage():
    env = {
        "VERCEL_ENV": "preview",
        "VERCEL_URL": "lossfit-feature-branch.vercel.app",
        "JWT_SECRET": "a" * 48,
        "DELETION_LEDGER_SECRET": "b" * 48,
        "BLOB_STORE_ID": "store_lossfit",
    }
    validate_production_environment(env)
    assert configured_app_base_url(env) == "https://lossfit-feature-branch.vercel.app"
    assert configured_cors_origins(env) == ["https://lossfit-feature-branch.vercel.app"]
    assert is_secure_cookie_environment(env)

    env.pop("VERCEL_URL")
    with pytest.raises(RuntimeError, match="explicit HTTPS CORS_ORIGINS"):
        validate_production_environment(env)


def test_production_system_environment_overrides_misleading_development_mode():
    env = valid()
    env["VERCEL_ENV"] = "production"
    env["ENVIRONMENT"] = "development"
    with pytest.raises(RuntimeError, match="cannot use a non-production ENVIRONMENT"):
        validate_production_environment(env)


def test_vercel_preview_auth_cookies_are_secure_even_without_environment_override(monkeypatch):
    from fastapi import Response
    from backend.app.main import set_auth_cookies

    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("VERCEL_ENV", "preview")
    response = Response()
    set_auth_cookies(response, "refresh-token")
    cookies = response.headers.getlist("set-cookie")
    refresh = next(cookie for cookie in cookies if cookie.startswith("lf_refresh="))
    csrf = next(cookie for cookie in cookies if cookie.startswith("lf_csrf="))
    assert "HttpOnly" in refresh and "Secure" in refresh and "SameSite=lax" in refresh
    assert "Secure" in csrf and "SameSite=lax" in csrf
