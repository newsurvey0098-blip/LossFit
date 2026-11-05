"""Export the deletion digests for protected storage outside database backups."""
import argparse
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from backend.app.deletion_ledger import export_ledger
from backend.app.main import AccountDeletionLedger, SessionLocal


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(".local/account-deletion-ledger.json"))
    args = parser.parse_args()
    secret = os.getenv("DELETION_LEDGER_SECRET")
    if not secret:
        raise SystemExit("Set DELETION_LEDGER_SECRET before exporting the ledger.")
    with SessionLocal() as session:
        digests = list(session.scalars(select(AccountDeletionLedger.email_digest).order_by(AccountDeletionLedger.email_digest)))
    document = export_ledger(digests, secret)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_name(args.output.name + "." + uuid4().hex + ".tmp")
    temp.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    if os.name != "nt":
        temp.chmod(0o600)
    temp.replace(args.output)
    print(f"Exported {len(digests)} deletion markers. Store this signed file separately from database backups.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
