# Database backup and restore

Run restore drills against an isolated database and private-file directory. Keep application traffic disabled until the restored database has completed ledger replay, file cleanup, and health checks.

## Create a backup (Windows PowerShell)

Set `DATABASE_URL` to the source database and `DELETION_LEDGER_SECRET` to the stable key from the application secret store. Protect the secret independently; changing it prevents verification of earlier exports. Keep the ledger file in encrypted, access-restricted storage separate from the database backup.

```powershell
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = "D:\LossFitBackups\lossfit-$stamp.dump"
$ledger = "E:\RestrictedDeletionLedger\lossfit-$stamp.json"
.\.venv\Scripts\python.exe scripts\export-deletion-ledger.py --output $ledger
pg_dump --format=custom --file $backup --dbname $env:DATABASE_URL
```

Also back up the private upload directory using encrypted storage and a retention policy. Database backups can retain personal records until their retention expires; exported deletion markers prevent older backups from reactivating deleted accounts when replayed.

## Restore to an isolated database

Create an empty target database and set `DATABASE_URL` to it. Restore the dump, apply any migrations added since the backup, then run the signed ledger in dry-run mode and inspect the matching-account count. The replay command never prints email addresses or file paths.

```powershell
pg_restore --no-owner --no-privileges --dbname $env:DATABASE_URL $backup
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
.\.venv\Scripts\python.exe scripts\replay-deletion-ledger.py --ledger-file $ledger
```

If the ledger signature validates and the dry-run result is expected, apply it before serving traffic:

```powershell
.\.venv\Scripts\python.exe scripts\replay-deletion-ledger.py --ledger-file $ledger --apply
.\.venv\Scripts\python.exe scripts\cleanup-private-files.py
```

The replay copies all signed deletion markers into the restored database, removes matching accounts and their database-cascaded personal records, queues their scan files, and invokes the path-restricted cleanup worker. Failed file removals remain in the queue. Investigate the storage permissions or path configuration, then rerun cleanup. Verify readiness, representative non-deleted user data, and expected deletion counts before switching traffic.

## Current verification limit

The full dump/restore and deletion replay was exercised on 2026-11-06 with `scripts/restore-drill.py`. It created a synthetic account, food, and meal in the local `lossfit` development database, took a custom-format `pg_dump`, deleted the source account, exported a signed ledger, restored the dump into a new isolated database, ran Alembic migrations, verified exactly one ledger match, applied replay, and confirmed the user/meal/private food were removed while all 5,856 public catalogue foods remained. The restored database and artifacts were retained under the ignored `.local/` directory for inspection.

Repeat locally with PostgreSQL 18 running, a stable `DELETION_LEDGER_SECRET`, and `DATABASE_URL` pointed only at the local LossFit development database:

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://lossfit@127.0.0.1:55432/lossfit'
.\.venv\Scripts\python.exe scripts\restore-drill.py --confirm-source-mutation
```

The script rejects remote or non-LossFit source databases. It adds and deletes one uniquely named synthetic source account and creates a new isolated restore database; it does not drop databases.
