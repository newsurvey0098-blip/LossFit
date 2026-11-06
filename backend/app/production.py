"""Fail-closed deployment checks and origin helpers."""
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


_LOCAL_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def is_production_environment(env):
    return env.get("ENVIRONMENT") == "production" or env.get("VERCEL_ENV") == "production"


def is_secure_cookie_environment(env):
    return env.get("ENVIRONMENT") == "production" or env.get("VERCEL_ENV") in {"preview", "production"}


def _vercel_preview_origin(env):
    if env.get("VERCEL_ENV") not in {"preview", "production"} or not env.get("VERCEL_URL"):
        return None
    host = env["VERCEL_URL"].strip()
    parsed = urlsplit(f"https://{host}")
    if (
        parsed.hostname
        and parsed.netloc == host
        and parsed.path == ""
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
    ):
        return f"https://{host}"
    return None


def configured_app_base_url(env):
    value = env.get("APP_BASE_URL", "").strip()
    return value or _vercel_preview_origin(env) or "http://127.0.0.1:5173"


def configured_cors_origins(env):
    value = env.get("CORS_ORIGINS", "").strip()
    if value:
        return [origin.strip() for origin in value.split(",") if origin.strip()]
    inferred = _vercel_preview_origin(env)
    return [inferred] if inferred else list(_LOCAL_ORIGINS)


def _validate_https_origin(name, value):
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or "*" in value
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise RuntimeError(f"Production {name} must contain explicit HTTPS origins")


def _validate_database_url(env):
    value = env.get("DATABASE_URL", "")
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"postgresql", "postgresql+psycopg"}
        or not parsed.hostname
        or parsed.hostname.lower() in {"localhost", "127.0.0.1", "::1"}
    ):
        raise RuntimeError("Production requires a remote PostgreSQL DATABASE_URL")
    sslmode = parse_qs(parsed.query).get("sslmode", [""])[0].lower()
    if sslmode not in {"require", "verify-ca", "verify-full"}:
        raise RuntimeError("Production DATABASE_URL must require TLS with sslmode=require or stronger")


def validate_production_environment(env):
    """Validate production and preview deployments; local development stays simple."""
    deployment = env.get("VERCEL_ENV", "")
    managed_deployment = deployment in {"preview", "production"}
    if not managed_deployment and env.get("ENVIRONMENT") != "production":
        return
    if deployment == "production" and env.get("ENVIRONMENT") not in {None, "", "production"}:
        raise RuntimeError("A Vercel production deployment cannot use a non-production ENVIRONMENT")

    for name in ("JWT_SECRET", "DELETION_LEDGER_SECRET"):
        value = env.get(name, "")
        if len(value) < 32 or value.lower().startswith(("replace", "local-only", "local-e2e", "change-me")):
            raise RuntimeError(f"Production requires a non-placeholder {name} of at least 32 characters")

    _validate_database_url(env)

    origins = configured_cors_origins(env)
    base_url = configured_app_base_url(env)
    if deployment == "production" or not _vercel_preview_origin(env):
        if not env.get("CORS_ORIGINS"):
            raise RuntimeError("Production requires explicit HTTPS CORS_ORIGINS")
        if not env.get("APP_BASE_URL"):
            raise RuntimeError("Production requires an explicit HTTPS APP_BASE_URL")
    for value in origins:
        _validate_https_origin("CORS_ORIGINS", value)
    _validate_https_origin("APP_BASE_URL", base_url)

    has_blob = bool(
        env.get("BLOB_STORE_ID")
        or env.get("BLOB_READ_WRITE_TOKEN")
        or env.get("VERCEL_BLOB_READ_WRITE_TOKEN")
    )
    upload_dir = env.get("PRIVATE_UPLOAD_DIR", "")
    if not has_blob and not upload_dir:
        raise RuntimeError("Production requires private Blob storage or an explicitly configured durable upload directory")
    if not has_blob and not Path(upload_dir).is_absolute():
        raise RuntimeError("Production PRIVATE_UPLOAD_DIR must be an absolute persistent directory")


def database_engine_options(env):
    """Keep each serverless instance's client pool small and pooler-compatible."""
    if env.get("VERCEL_ENV") in {"preview", "production"}:
        return {
            "pool_pre_ping": True,
            "pool_size": 1,
            "max_overflow": 0,
            "pool_recycle": 1800,
            "connect_args": {"prepare_threshold": None},
        }
    return {"pool_pre_ping": True}
