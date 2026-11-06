"""Configuration helpers for one-off Alembic migration processes."""


def configured_migration_database_url(env):
    """Prefer the restricted app's separate migration connection when supplied.

    Hosted environments must never run schema changes using the app runtime URL.
    Local development and CI can keep using DATABASE_URL for their disposable DB.
    """
    migration_url = env.get("MIGRATION_DATABASE_URL")
    hosted = env.get("VERCEL_ENV") in {"preview", "production"}
    production = env.get("ENVIRONMENT", "").lower() == "production"
    if (hosted or production) and not migration_url:
        raise RuntimeError(
            "Hosted migrations require a separate MIGRATION_DATABASE_URL; "
            "do not use the application runtime database role"
        )
    return migration_url or env.get("DATABASE_URL")
