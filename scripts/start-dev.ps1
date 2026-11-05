$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Start-Process -FilePath (Join-Path $root '.venv/Scripts/python.exe') -ArgumentList '-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port','3001','--no-access-log' -WorkingDirectory $root -WindowStyle Hidden
Push-Location (Join-Path $root 'frontend')
try { & (Join-Path $root '.runtime/node-v22.23.4-win-x64/npm.cmd') run dev } finally { Pop-Location }
