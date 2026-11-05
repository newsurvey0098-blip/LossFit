"""Exercise a local custom-format backup, isolated restore, and deletion-ledger replay."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from fastapi.testclient import TestClient
from alembic.config import Config
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parent.parent
PG_BIN = Path(r"C:\Program Files\PostgreSQL\18\bin")
sys.path.insert(0, str(ROOT))


def invoke(args: list[str], *, env: dict[str, str], step: str) -> str:
    completed = subprocess.run(args, env=env, cwd=ROOT, text=True, capture_output=True, check=False)
    if completed.returncode:
        details = completed.stderr[-1200:].strip()
        raise RuntimeError(f"{step} failed ({completed.returncode}): {details}")
    if completed.stdout.strip():
        print(completed.stdout.strip())
    return completed.stdout


def libpq_url(url):
    return url.set(drivername="postgresql", password=None).render_as_string(hide_password=False)


def postgres_process_env(url, base_env):
    env = base_env.copy()
    if url.host:
        env["PGHOST"] = url.host
    if url.port:
        env["PGPORT"] = str(url.port)
    if url.username:
        env["PGUSER"] = url.username
    if url.password:
        env["PGPASSWORD"] = url.password
    return env


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-source-mutation", action="store_true", help="allow creation then deletion of one synthetic user in the source development DB")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    source_url = make_url(os.getenv("DATABASE_URL", "postgresql+psycopg://lossfit@127.0.0.1:55432/lossfit"))
    secret = os.getenv("DELETION_LEDGER_SECRET")
    if not args.confirm_source_mutation:
        raise SystemExit("Pass --confirm-source-mutation to add and delete one synthetic account in the local source DB.")
    if source_url.host not in {"127.0.0.1", "localhost", "::1"} or not (source_url.database or "").startswith("lossfit"):
        raise SystemExit("Restore drill is restricted to a local database whose name begins with 'lossfit'.")
    if not secret or len(secret) < 32:
        raise SystemExit("Set DELETION_LEDGER_SECRET to a stable secret of at least 32 characters.")
    if any(not (PG_BIN / f"{tool}.exe").is_file() for tool in ("pg_dump", "pg_restore", "createdb")):
        raise SystemExit(f"PostgreSQL 18 backup tools were not found in {PG_BIN}.")

    drill_id = uuid4().hex
    target_name = f"lossfit_restore_drill_{drill_id[:16]}"
    artifact_dir = ROOT / ".local" / "restore-drills" / drill_id
    artifact_dir.mkdir(parents=True, exist_ok=False)
    backup_file = artifact_dir / "pre-deletion.dump"
    ledger_file = artifact_dir / "deletion-ledger.json"
    source_env = os.environ.copy()
    source_env["DATABASE_URL"] = source_url.render_as_string(hide_password=False)
    source_env["DELETION_LEDGER_SECRET"] = secret
    process_env = postgres_process_env(source_url, source_env)

    from backend.app.deletion_ledger import export_ledger
    from backend.app.main import AccountDeletionLedger, Food, Meal, SessionLocal, User, app
    import backend.app.main as main_module
    main_module.request_ip = lambda request: "restore-drill-" + drill_id

    user_id = None
    deleted = False
    drill_email = None
    drill_password = None
    try:
        with TestClient(app) as client:
            drill_email = f"restore-drill-{drill_id}@example.com"
            drill_password = "Restore-drill-" + uuid4().hex
            registered = client.post("/api/v1/auth/register", json={"name": "Restore Drill", "email": drill_email, "password": drill_password})
            if registered.status_code != 201:
                raise RuntimeError(f"Could not create the synthetic restore-drill account ({registered.status_code}).")
            owner = registered.json()
            user_id = owner["id"]
            csrf = client.cookies["lf_csrf"]
            headers = {"origin": "http://localhost:5173", "x-csrf-token": csrf, "authorization": f"Bearer {owner['access_token']}"}
            food = client.post("/api/v1/foods", headers=headers, json={"name": f"Restore drill food {drill_id[:8]}", "kcal": 135})
            if food.status_code != 201:
                raise RuntimeError("Could not create synthetic personal food for the restore drill.")
            meal = client.post("/api/v1/meals", headers=headers, json={"name": "Restore drill meal", "meal_type": "lunch", "items": [{"food_id": food.json()["id"], "grams": 100}]})
            if meal.status_code != 201:
                raise RuntimeError("Could not create synthetic meal for the restore drill.")

            source_engine = create_engine(source_url)
            with source_engine.connect() as connection:
                public_foods_before = connection.scalar(select(func.count(Food.id)).where(Food.owner_id.is_(None)))
            source_engine.dispose()
            invoke([str(PG_BIN / "pg_dump.exe"), "--format=custom", "--file", str(backup_file), "--dbname", libpq_url(source_url)], env=process_env, step="pg_dump")
            if not backup_file.is_file() or backup_file.stat().st_size == 0:
                raise RuntimeError("pg_dump did not produce a usable backup file.")

            deletion = client.request("DELETE", "/api/v1/account", headers=headers, json={"password": drill_password, "confirmation": "DELETE MY ACCOUNT"})
            if deletion.status_code != 204:
                raise RuntimeError("The synthetic source account could not be deleted after the backup.")
            deleted = True

        with SessionLocal() as session:
            digests = list(session.scalars(select(AccountDeletionLedger.email_digest).order_by(AccountDeletionLedger.email_digest)))
        document = export_ledger(digests, secret)
        ledger_file.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

        target_env = source_env.copy()
        target_env["DATABASE_URL"] = source_url.set(database=target_name).render_as_string(hide_password=False)
        process_env = postgres_process_env(source_url, target_env)

        invoke([str(PG_BIN / "createdb.exe"), target_name], env=process_env, step="create isolated restore database")
        invoke([str(PG_BIN / "pg_restore.exe"), "--no-owner", "--no-privileges", "--dbname", libpq_url(source_url.set(database=target_name)), str(backup_file)], env=target_env, step="pg_restore")
        invoke([sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"], env=target_env, step="post-restore migrations")
        replay_script = str(ROOT / "scripts" / "replay-deletion-ledger.py")
        dry_run = invoke([sys.executable, replay_script, "--ledger-file", str(ledger_file)], env=target_env, step="deletion-ledger dry run")
        if "1 restored accounts match" not in dry_run:
            raise RuntimeError("The signed ledger dry run did not match exactly the synthetic account in the backup.")
        invoke([sys.executable, replay_script, "--ledger-file", str(ledger_file), "--apply"], env=target_env, step="deletion-ledger replay")

        target_engine = create_engine(source_url.set(database=target_name))
        expected_revision = ScriptDirectory.from_config(Config(str(ROOT / "backend" / "alembic.ini"))).get_current_head()
        try:
            with target_engine.connect() as connection:
                restored_user = connection.scalar(select(func.count()).select_from(User).where(User.id == user_id))
                restored_private_foods = connection.scalar(select(func.count(Food.id)).where(Food.owner_id == user_id))
                restored_meals = connection.scalar(select(func.count(Meal.id)).where(Meal.owner_id == user_id))
                public_foods_after = connection.scalar(select(func.count(Food.id)).where(Food.owner_id.is_(None)))
                version = connection.exec_driver_sql("select version_num from alembic_version").scalar_one()
            if restored_user or restored_private_foods or restored_meals or public_foods_after != public_foods_before or version != expected_revision:
                raise RuntimeError("Restored database verification failed after deletion-ledger replay.")
        finally:
            target_engine.dispose()

        print(f"Restore drill passed. Snapshot user {user_id} and its meal/custom food were deleted by ledger replay; public catalogue count remained {public_foods_after}.")
        print(f"Inspect the retained isolated database '{target_name}' and artifacts under '{artifact_dir}'.")
        return 0
    finally:
        if user_id and not deleted:
            try:
                with TestClient(app) as cleanup_client:
                    login = cleanup_client.post("/api/v1/auth/login", json={"email": drill_email, "password": drill_password})
                    if login.status_code == 200:
                        owner = login.json()
                        cleanup_headers = {"origin": "http://localhost:5173", "x-csrf-token": cleanup_client.cookies["lf_csrf"], "authorization": f"Bearer {owner['access_token']}"}
                        cleanup = cleanup_client.request("DELETE", "/api/v1/account", headers=cleanup_headers, json={"password": drill_password, "confirmation": "DELETE MY ACCOUNT"})
                        deleted = cleanup.status_code == 204
            except Exception:
                pass
            if not deleted:
                print("Restore drill could not remove the synthetic source account; clean it up manually before continuing.")


if __name__ == "__main__":
    raise SystemExit(main())
