$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$pgBin = 'C:\Program Files\PostgreSQL\18\bin'
$dbName = 'lossfit_test_' + (Get-Date).ToUniversalTime().ToString('yyyyMMdd_HHmmss') + '_' + (Get-Random -Maximum 1000000)

& (Join-Path $pgBin 'createdb.exe') -h 127.0.0.1 -p 55432 -U lossfit $dbName
if ($LASTEXITCODE -ne 0) { throw 'Could not create a fresh LossFit test database. Start the isolated project PostgreSQL cluster first.' }
$env:DATABASE_URL = "postgresql+psycopg://lossfit@127.0.0.1:55432/$dbName"
Push-Location $root
try {
  & (Join-Path $root '.venv/Scripts/python.exe') -m alembic -c backend/alembic.ini upgrade head
  if ($LASTEXITCODE -ne 0) { throw 'Alembic migration failed.' }
  & (Join-Path $root '.venv/Scripts/python.exe') -m pytest -q backend/tests
  if ($LASTEXITCODE -ne 0) { throw 'LossFit tests failed.' }
  Write-Host "Test database retained for inspection: $dbName"
} finally {
  Pop-Location
}
