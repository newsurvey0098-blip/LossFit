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

try {
  $health = Invoke-RestMethod -Uri $readinessUrl -TimeoutSec 5
  if ($health.status -ne 'ready' -or $health.database -ne 'connected') {
    throw "API readiness reported status '$($health.status)' and database '$($health.database)'."
  }
  Write-Host 'API and database: ready (proxied through Vite).'
} catch {
  Write-Error "The API/database is unavailable through $readinessUrl. Check PostgreSQL and .local/dev-api.err.log. $($_.Exception.Message)" -ErrorAction Continue
  $failed = $true
}

if ($failed) { exit 1 }
Write-Host 'LossFit local sign-in prerequisites are ready.'
