param([switch]$ImportFoods)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$runtime = Join-Path $root '.runtime'
$nodeName = 'node-v22.23.4-win-x64'
$nodeRoot = Join-Path $runtime $nodeName
$nodeExe = Join-Path $nodeRoot 'node.exe'
$zipName = "$nodeName.zip"
$zipPath = Join-Path $runtime $zipName
$checksumLine = Get-Content (Join-Path $PSScriptRoot 'node-shasums.txt') | Where-Object { $_ -match "\s+$([regex]::Escape($zipName))$" } | Select-Object -First 1
if (-not $checksumLine) { throw "No pinned SHA256 is recorded for $zipName." }
$expectedHash = ($checksumLine -split '\s+')[0].ToLowerInvariant()
if (-not (Test-Path $nodeExe)) {
  New-Item -ItemType Directory -Force -Path $runtime | Out-Null
  Invoke-WebRequest -Uri "https://nodejs.org/dist/v22.23.4/$zipName" -OutFile $zipPath
  $actualHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actualHash -ne $expectedHash) {
    Remove-Item -LiteralPath $zipPath -Force
    throw 'The downloaded Node archive did not match the pinned SHA256.'
  }
  Expand-Archive -LiteralPath $zipPath -DestinationPath $runtime -Force
  Remove-Item -LiteralPath $zipPath -Force
}
$nodeVersion = (& $nodeExe --version).Trim()
if ($nodeVersion -ne 'v22.23.4') { throw "Expected project-local Node v22.23.4, found $nodeVersion." }

$py = Get-Command py.exe -ErrorAction SilentlyContinue
if (-not $py) { throw 'Install Python 3.12 and enable the Python launcher (py.exe), then rerun setup.' }
& py.exe -3.12 --version
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 was not found by the Windows Python launcher.' }
$python = Join-Path $root '.venv/Scripts/python.exe'
if (-not (Test-Path $python)) {
  & py.exe -3.12 -m venv (Join-Path $root '.venv')
  if ($LASTEXITCODE -ne 0) { throw 'Could not create the project virtual environment.' }
}
& $python -m pip install --disable-pip-version-check -r (Join-Path $root 'backend/requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Could not install the pinned backend dependencies.' }

$envFile = Join-Path $root '.env'
if (-not (Test-Path $envFile)) {
  function New-LocalSecret {
    $bytes = New-Object byte[] 48
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    [Convert]::ToBase64String($bytes)
  }
  $contents = [System.IO.File]::ReadAllText((Join-Path $root '.env.example'))
  $contents = $contents.Replace('JWT_SECRET=replace-with-a-random-secret-of-at-least-32-characters', "JWT_SECRET=$(New-LocalSecret)")
  $contents = $contents.Replace('DELETION_LEDGER_SECRET=replace-with-a-stable-random-secret-of-at-least-32-characters', "DELETION_LEDGER_SECRET=$(New-LocalSecret)")
  [System.IO.File]::WriteAllText($envFile, $contents, [System.Text.UTF8Encoding]::new($false))
  Write-Host 'Created .env with unique local secrets; it is ignored by Git.'
} else {
  Write-Host 'Keeping the existing .env and its stable deletion-ledger key.'
}

$npm = Join-Path $nodeRoot 'npm.cmd'
$frontend = Join-Path $root 'frontend'
$nodeModules = Join-Path $frontend 'node_modules'
$lockFile = Join-Path $frontend 'package-lock.json'
$installStamp = Join-Path $root '.local/frontend-node-lock.sha256'
$lockHash = (Get-FileHash -LiteralPath $lockFile -Algorithm SHA256).Hash.ToLowerInvariant()
Push-Location (Join-Path $root 'frontend')
try {
  if (-not (Test-Path $nodeModules)) {
    & $npm ci
    if ($LASTEXITCODE -ne 0) { throw 'Could not install the locked frontend dependencies.' }
  } elseif ((Test-Path $installStamp) -and ((Get-Content -LiteralPath $installStamp -Raw).Trim() -eq $lockHash)) {
    Write-Host 'Frontend dependencies already match package-lock.json.'
  } else {
    & $npm install --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'Could not reconcile frontend dependencies with package-lock.json.' }
  }
  New-Item -ItemType Directory -Force -Path (Join-Path $root '.local') | Out-Null
  [System.IO.File]::WriteAllText($installStamp, $lockHash, [System.Text.UTF8Encoding]::new($false))
} finally { Pop-Location }

& (Join-Path $PSScriptRoot 'start-db.ps1')
& $python -m alembic -c (Join-Path $root 'backend/alembic.ini') upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Could not apply database migrations.' }
if ($ImportFoods) {
  & $python (Join-Path $PSScriptRoot 'import-foods.py')
  if ($LASTEXITCODE -ne 0) { throw 'The USDA catalogue import failed.' }
}
Write-Host 'LossFit setup is ready. Run scripts/start-dev.ps1 to start the API and frontend.'
