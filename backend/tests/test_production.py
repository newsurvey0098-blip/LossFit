from pathlib import Path
import os

import pytest
from backend.app.production import (
    configured_app_base_url,
    configured_cors_origins,
    is_production_environment,
    is_secure_cookie_environment,
    database_engine_options,
    validate_production_environment,
)
from backend.app.migration_config import configured_migration_database_url, include_alembic_object


def valid():
    return {
        "ENVIRONMENT": "production",
        "JWT_SECRET": "a" * 48,
        "DELETION_LEDGER_SECRET": "b" * 48,
        "DATABASE_URL": "postgresql+psycopg://lossfit_app:secret@db.example.com:6543/lossfit?sslmode=require",
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
        ("DATABASE_URL", ""),
        ("DATABASE_URL", "postgresql+psycopg://user:secret@localhost:5432/lossfit?sslmode=require"),
        ("DATABASE_URL", "postgresql+psycopg://user:secret@db.example.com:5432/lossfit"),
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
        "DATABASE_URL": "postgresql+psycopg://lossfit_app:secret@db.example.com:6543/lossfit?sslmode=require",
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


def test_vercel_database_pool_is_serverless_and_transaction_pooler_compatible():
    from sqlalchemy import create_engine, text

    options = database_engine_options({"VERCEL_ENV": "preview"})
    assert options["pool_size"] == 1
    assert options["max_overflow"] == 0
    assert options["pool_recycle"] == 1800
    assert options["connect_args"] == {"prepare_threshold": None}
    assert database_engine_options({"ENVIRONMENT": "development"}) == {"pool_pre_ping": True}

    engine = create_engine(os.environ["DATABASE_URL"], **options)
    try:
        assert engine.pool.size() == 1
        assert engine.pool._max_overflow == 0
        with engine.connect() as connection:
            assert connection.execute(text("select 1")).scalar_one() == 1
    finally:
        engine.dispose()


def test_production_migrations_require_a_separate_database_role():
    with pytest.raises(RuntimeError, match="separate MIGRATION_DATABASE_URL"):
        configured_migration_database_url({
            "ENVIRONMENT": "production",
            "DATABASE_URL": "postgresql+psycopg://lossfit_app@pooler.example:6543/lossfit?sslmode=require",
        })


def test_migrations_prefer_the_separate_migration_connection():
    runtime_url = "postgresql+psycopg://lossfit_app@pooler.example:6543/lossfit?sslmode=require"
    migration_url = "postgresql+psycopg://postgres@db.example:5432/lossfit?sslmode=require"
    assert configured_migration_database_url({
        "ENVIRONMENT": "production",
        "DATABASE_URL": runtime_url,
        "MIGRATION_DATABASE_URL": migration_url,
    }) == migration_url


def test_local_migrations_keep_using_the_disposable_database_url():
    local_url = "postgresql+psycopg://lossfit@127.0.0.1:55432/lossfit"
    assert configured_migration_database_url({"DATABASE_URL": local_url}) == local_url


def test_autogenerate_ignores_only_unmapped_pgvector_sidecar():
    assert not include_alembic_object(object(), "knowledge_vector_embeddings", "table", True, None)
    assert include_alembic_object(object(), "users", "table", True, None)
    assert include_alembic_object(object(), "knowledge_vector_embeddings", "table", False, object())
