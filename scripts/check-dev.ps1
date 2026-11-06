$ErrorActionPreference = 'Stop'
$failed = $false
$frontendPort = $null
$frontend = $null
$health = $null
$ports = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
  Where-Object { $_.LocalAddress -eq '127.0.0.1' -and $_.LocalPort -ge 5173 -and $_.LocalPort -le 5193 } |
  Select-Object -ExpandProperty LocalPort -Unique |
  Sort-Object)

foreach ($port in $ports) {
  $candidateUrl = "http://127.0.0.1:$port/"
  $candidateReadinessUrl = "http://127.0.0.1:$port/api/v1/health/ready"
  try {
    $candidateFrontend = Invoke-WebRequest -Uri $candidateUrl -TimeoutSec 2 -UseBasicParsing
    if ($candidateFrontend.StatusCode -ne 200 -or $candidateFrontend.Content -notmatch '<div id="root">') {
      continue
    }

    $candidateHealth = Invoke-RestMethod -Uri $candidateReadinessUrl -TimeoutSec 2
    $healthFields = @($candidateHealth.PSObject.Properties.Name)
    if ($healthFields -contains 'database' -and $healthFields -contains 'migrations') {
      $frontendPort = $port
      $frontend = $candidateFrontend
      $health = $candidateHealth
      break
    }
  } catch {
    # Ignore unrelated local services and Vite instances without LossFit's API proxy.
  }
}

if ($null -eq $frontendPort) {
  Write-Error 'LossFit frontend and its API proxy were not found on ports 5173-5193. Start the app with scripts/start-dev.ps1.' -ErrorAction Continue
  $failed = $true
} else {
  Write-Host "Frontend: ready at http://127.0.0.1:$frontendPort/ (HTTP $($frontend.StatusCode))."
  if ($health.status -eq 'ready' -and $health.database -eq 'connected' -and $health.migrations -eq 'current') {
    Write-Host 'API and database: ready (proxied through Vite).'
  } else {
    $apiProblem = "API readiness through port $frontendPort reported status '$($health.status)', database '$($health.database)', and migrations '$($health.migrations)'."
    if ($health.status -eq 'ready' -and $health.database -eq 'connected' -and $health.migrations -ne 'current') {
      $listener = Get-NetTCPConnection -LocalPort 3001 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
      if ($listener) {
        $apiProblem = "The API listener on port 3001 (PID $($listener.OwningProcess)) is stale. Stop that process and rerun scripts/start-dev.ps1."
      } else {
        $apiProblem = "The API reports stale migrations ('$($health.migrations)'). Run scripts/setup-windows.ps1, then restart the API."
      }
    }
    Write-Error $apiProblem -ErrorAction Continue
    $failed = $true
  }
}

if ($failed) { exit 1 }
Write-Host 'LossFit local sign-in prerequisites are ready.'
