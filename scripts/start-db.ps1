$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$pg = 'C:\Program Files\PostgreSQL\18\bin'
if (-not (Test-Path (Join-Path $root '.local/pgdata/PG_VERSION'))) {
  & (Join-Path $pg 'initdb.exe') -D (Join-Path $root '.local/pgdata') -U lossfit --auth-local=trust --auth-host=trust --encoding=UTF8
}
& (Join-Path $pg 'pg_ctl.exe') -D (Join-Path $root '.local/pgdata') -l (Join-Path $root '.local/postgres.log') -o '-p 55432 -h 127.0.0.1' start
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL did not start. Check .local/postgres.log' }
& (Join-Path $pg 'createdb.exe') -h 127.0.0.1 -p 55432 -U lossfit lossfit
