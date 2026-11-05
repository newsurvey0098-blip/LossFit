"""Prevent restored backups from reactivating accounts previously deleted."""
import argparse
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select
from backend.app.deletion_ledger import verify_ledger
from backend.app.main import AccountDeletionLedger, ScanSession, SessionLocal, User, queue_private_file_cleanup, drain_private_file_cleanup


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger-file", required=True, type=Path)
    parser.add_argument("--apply", action="store_true", help="Delete matching restored accounts; default is a dry run")
    args = parser.parse_args()
    secret = os.getenv("DELETION_LEDGER_SECRET")
    if not secret:
        raise SystemExit("Set DELETION_LEDGER_SECRET to verify and replay the ledger.")
    if not args.ledger_file.is_file() or args.ledger_file.stat().st_size > 10_000_000:
        raise SystemExit("Deletion ledger file is missing or exceeds 10 MB.")
    try:
        document = json.loads(args.ledger_file.read_text(encoding="utf-8"))
        digests = verify_ledger(document, secret)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise SystemExit(f"Cannot use deletion ledger: {error}") from error
    digest_set = set(digests)
    with SessionLocal() as session:
        matches = []
        for user in session.scalars(select(User)):
            digest = hmac.new(secret.encode(), user.email.lower().encode(), hashlib.sha256).hexdigest()
            if digest in digest_set:
                matches.append(user.id)
        print(f"Verified deletion ledger: {len(digests)} markers; {len(matches)} restored accounts match.")
        if not args.apply:
            print("Dry run only. Review the restored database, then repeat with --apply before serving traffic.")
            return 0
        existing = set(session.scalars(select(AccountDeletionLedger.email_digest).where(AccountDeletionLedger.email_digest.in_(digests)))) if digests else set()
        session.add_all(AccountDeletionLedger(email_digest=value) for value in digests if value not in existing)
        if matches:
            for private_path in session.scalars(select(ScanSession.private_path).where(ScanSession.owner_id.in_(matches))):
                queue_private_file_cleanup(session, private_path)
            session.execute(delete(User).where(User.id.in_(matches)))
        session.commit()
        cleanup = drain_private_file_cleanup(session)
    print(f"Replay applied. {len(matches)} accounts removed; {cleanup['remaining']} private files remain queued for cleanup.")
    return 1 if cleanup["remaining"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
