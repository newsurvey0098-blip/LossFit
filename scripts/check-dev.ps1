$ErrorActionPreference = 'Stop'
$frontendUrl = 'http://127.0.0.1:5173/'
$readinessUrl = 'http://127.0.0.1:5173/api/v1/health/ready'
$failed = $false

try {
  $frontend = Invoke-WebRequest -Uri $frontendUrl -TimeoutSec 5 -UseBasicParsing
  if ($frontend.StatusCode -ne 200 -or $frontend.Content -notmatch '<div id="root">') {
    throw 'The frontend response did not contain the LossFit app shell.'
  }
  Write-Host 'Frontend: ready (HTTP 200).'
} catch {
  Write-Error "Frontend is unavailable at $frontendUrl. Start it with scripts/start-dev.ps1. $($_.Exception.Message)" -ErrorAction Continue
  $failed = $true
}

$apiProblem = $null
try {
  $health = Invoke-RestMethod -Uri $readinessUrl -TimeoutSec 5
  if ($health.status -eq 'ready' -and $health.database -eq 'connected' -and $health.migrations -ne 'current') {
    $listener = Get-NetTCPConnection -LocalPort 3001 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($listener) {
      $apiProblem = "The API listener on port 3001 (PID $($listener.OwningProcess)) is stale. Stop that process and rerun scripts/start-dev.ps1."
    } else {
      $apiProblem = "The API reports stale migrations ('$($health.migrations)'). Run scripts/setup-windows.ps1, then restart the API."
    }
  } elseif ($health.status -ne 'ready' -or $health.database -ne 'connected' -or $health.migrations -ne 'current') {
    $apiProblem = "API readiness reported status '$($health.status)', database '$($health.database)', and migrations '$($health.migrations)'."
  } else {
    Write-Host 'API and database: ready (proxied through Vite).'
  }
} catch {
  $apiProblem = "API request failed through Vite. Check PostgreSQL and .local/dev-api.err.log. $($_.Exception.Message)"
}
if ($apiProblem) {
  Write-Error $apiProblem -ErrorAction Continue
  $failed = $true
}

if ($failed) { exit 1 }
Write-Host 'LossFit local sign-in prerequisites are ready.'
