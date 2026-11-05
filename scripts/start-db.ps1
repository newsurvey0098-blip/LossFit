$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$pg = 'C:\Program Files\PostgreSQL\18\bin'
$pgData = Join-Path $root '.local/pgdata'
if (-not (Test-Path (Join-Path $pgData 'PG_VERSION'))) {
  & (Join-Path $pg 'initdb.exe') -D $pgData -U lossfit --auth-local=trust --auth-host=trust --encoding=UTF8
  if ($LASTEXITCODE -ne 0) { throw 'Could not initialize the isolated LossFit PostgreSQL cluster.' }
}
$pgCtl = Join-Path $pg 'pg_ctl.exe'
& $pgCtl status -D $pgData *> $null
if ($LASTEXITCODE -ne 0) {
  & $pgCtl -D $pgData -l (Join-Path $root '.local/postgres.log') -o '-p 55432 -h 127.0.0.1' start
  if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL did not start. Check .local/postgres.log' }
}
$databaseExists = & (Join-Path $pg 'psql.exe') -h 127.0.0.1 -p 55432 -U lossfit -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = 'lossfit'"
if (($databaseExists | Out-String).Trim() -ne '1') {
  & (Join-Path $pg 'createdb.exe') -h 127.0.0.1 -p 55432 -U lossfit lossfit
  if ($LASTEXITCODE -ne 0) { throw 'Could not create the isolated LossFit development database.' }
}
