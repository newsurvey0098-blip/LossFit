$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$apiUrl = 'http://127.0.0.1:3001/api/v1/health/ready'
$localDirectory = Join-Path $root '.local'
$apiOutLog = Join-Path $localDirectory 'dev-api.out.log'
$apiErrLog = Join-Path $localDirectory 'dev-api.err.log'
$apiProcess = $null
$apiReady = $false

function Test-ApiReady($Health) {
  return $Health.status -eq 'ready' -and $Health.database -eq 'connected' -and $Health.migrations -eq 'current'
}

New-Item -ItemType Directory -Force -Path $localDirectory | Out-Null

try {
  $health = Invoke-RestMethod -Uri $apiUrl -TimeoutSec 2
  $apiReady = Test-ApiReady $health
} catch {
  # The API is not running yet; start the local instance below.
}

if (-not $apiReady) {
  $existingListener = Get-NetTCPConnection -LocalPort 3001 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($existingListener) {
    throw "An API process (PID $($existingListener.OwningProcess)) is already listening on port 3001 but did not report current migrations. Stop that old process and rerun scripts/start-dev.ps1."
  }

  $python = Join-Path $root '.venv/Scripts/python.exe'
  if (-not (Test-Path -LiteralPath $python)) {
    throw 'LossFit Python environment is missing. Run scripts/setup-windows.ps1 first.'
  }

  $apiProcess = Start-Process -FilePath $python `
    -ArgumentList '-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port','3001','--no-access-log' `
    -WorkingDirectory $root `
    -WindowStyle Hidden `
    -PassThru `
    -RedirectStandardOutput $apiOutLog `
    -RedirectStandardError $apiErrLog

  for ($attempt = 0; $attempt -lt 40; $attempt++) {
    if ($apiProcess.HasExited) { break }
    try {
      $health = Invoke-RestMethod -Uri $apiUrl -TimeoutSec 1
      if (Test-ApiReady $health) {
        $apiReady = $true
        break
      }
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }
}

if (-not $apiReady) {
  if ($apiProcess -and -not $apiProcess.HasExited) {
    Stop-Process -Id $apiProcess.Id -Force -ErrorAction SilentlyContinue
  }
  throw "LossFit API/database did not become ready at http://127.0.0.1:3001. Check '$apiErrLog' and run scripts/setup-windows.ps1 if the local database is stopped."
}

Write-Host 'LossFit API ready; PostgreSQL is connected.'
Write-Host 'Frontend: http://127.0.0.1:5173'
Write-Host 'API docs: http://127.0.0.1:3001/docs'

Push-Location (Join-Path $root 'frontend')
try {
  & (Join-Path $root '.runtime/node-v22.23.4-win-x64/npm.cmd') run dev
} finally {
  Pop-Location
  if ($apiProcess -and -not $apiProcess.HasExited) {
    Stop-Process -Id $apiProcess.Id -Force -ErrorAction SilentlyContinue
  }
}
