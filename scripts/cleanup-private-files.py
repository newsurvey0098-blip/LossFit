"""Retry queued private-upload deletions without displaying sensitive paths."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.main import SessionLocal, drain_private_file_cleanup


def main() -> int:
    removed = failed = 0
    with SessionLocal() as session:
        while True:
            result = drain_private_file_cleanup(session)
            removed += result["removed"]
            failed += result["failed"]
            if result["remaining"] == 0 or result["removed"] == 0:
                print(f"Private file cleanup: {removed} removed, {failed} still pending, {result['remaining']} queued.")
                return 1 if result["remaining"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
