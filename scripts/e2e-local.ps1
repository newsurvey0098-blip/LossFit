$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$pgBin = 'C:\Program Files\PostgreSQL\18\bin'
$dbName = 'lossfit_e2e_' + [guid]::NewGuid().ToString('N')
$databaseUrl = "postgresql+psycopg://lossfit@127.0.0.1:55432/$dbName"
$apiPort = Get-Random -Minimum 31000 -Maximum 49000
$visionPort = Get-Random -Minimum 49001 -Maximum 56000
$apiProcess = $null
$visionProcess = $null
$outLog = Join-Path $root '.local/e2e-api.out.log'
$errLog = Join-Path $root '.local/e2e-api.err.log'
$visionErrLog = Join-Path $root '.local/e2e-vision.err.log'
New-Item -ItemType Directory -Force -Path (Join-Path $root '.local') | Out-Null

Push-Location $root
try {
  & (Join-Path $pgBin 'createdb.exe') -h 127.0.0.1 -p 55432 -U lossfit $dbName
  if ($LASTEXITCODE -ne 0) { throw 'Could not create the disposable E2E database. Start the isolated project PostgreSQL cluster first.' }

  $env:DATABASE_URL = $databaseUrl
  $env:ENVIRONMENT = 'development'
  $env:JWT_SECRET = 'local-e2e-secret-do-not-use-outside-tests-0123456789'
  $env:DELETION_LEDGER_SECRET = 'local-e2e-deletion-key-do-not-use-outside-tests-0123456789'
  $env:AI_BASE_URL = "http://127.0.0.1:$visionPort/v1"
  $env:AI_API_KEY = 'local-e2e-vision-key'
  $env:VISION_MODEL = 'deterministic-local-test'
  $env:AI_MODEL = 'deterministic-local-test'
  $env:CORS_ORIGINS = 'http://127.0.0.1:4173,http://localhost:4173'
  $env:LOSSFIT_API_PROXY = "http://127.0.0.1:$apiPort"
  $env:E2E_VISION_PORT = "$visionPort"
  $visionScript = '"' + (Join-Path $PSScriptRoot 'e2e-vision-provider.py') + '"'
  $visionProcess = Start-Process -FilePath (Join-Path $root '.venv/Scripts/python.exe') -ArgumentList $visionScript -WorkingDirectory $root -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $root '.local/e2e-vision.out.log') -RedirectStandardError $visionErrLog
  $visionHealthy = $false
  for ($attempt = 0; $attempt -lt 30; $attempt++) {
    if ($visionProcess.HasExited) { throw "Local vision test provider exited during startup. See $visionErrLog" }
    try { if ((Invoke-WebRequest "http://127.0.0.1:$visionPort/health" -TimeoutSec 1).StatusCode -eq 200) { $visionHealthy = $true; break } } catch { Start-Sleep -Milliseconds 200 }
  }
  if (-not $visionHealthy) { throw "Local vision test provider did not become ready. See $visionErrLog" }
  & (Join-Path $root '.venv/Scripts/python.exe') -m alembic -c backend/alembic.ini upgrade head
  if ($LASTEXITCODE -ne 0) { throw 'Could not migrate the disposable E2E database.' }

  $apiProcess = Start-Process -FilePath (Join-Path $root '.venv/Scripts/python.exe') -ArgumentList '-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port',"$apiPort",'--no-access-log' -WorkingDirectory $root -PassThru -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errLog
  Start-Sleep -Milliseconds 500
  if ($apiProcess.HasExited) { throw "API process exited during startup. See $errLog" }
  $healthy = $false
  for ($attempt = 0; $attempt -lt 60; $attempt++) {
    if ($apiProcess.HasExited) { throw "API process exited during startup. See $errLog" }
    try {
      if ((Invoke-RestMethod "http://127.0.0.1:$apiPort/api/v1/health/ready" -TimeoutSec 1).status -eq 'ready') { $healthy = $true; break }
    } catch { Start-Sleep -Milliseconds 500 }
  }
  if (-not $healthy) { throw "API did not become ready. See $errLog" }

  Push-Location (Join-Path $root 'frontend')
  try {
    & (Join-Path $root '.runtime/node-v22.23.4-win-x64/npm.cmd') run test:e2e
    if ($LASTEXITCODE -ne 0) { throw 'Browser E2E suite failed.' }
  } finally { Pop-Location }
} finally {
  if ($apiProcess -and -not $apiProcess.HasExited) { Stop-Process -Id $apiProcess.Id -Force }
  if ($visionProcess -and -not $visionProcess.HasExited) { Stop-Process -Id $visionProcess.Id -Force }
  if ($dbName -match '^lossfit_e2e_[0-9a-f]{32}$') {
    & (Join-Path $pgBin 'dropdb.exe') -h 127.0.0.1 -p 55432 -U lossfit --if-exists $dbName
    if ($LASTEXITCODE -ne 0) { Write-Warning "Could not drop disposable database $dbName; inspect it before removal." }
  }
  Pop-Location
}
