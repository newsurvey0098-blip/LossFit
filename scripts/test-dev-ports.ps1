$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'dev-ports.ps1')

$reserved = [System.Collections.Generic.List[System.Net.Sockets.TcpListener]]::new()
try {
  $firstPort = $null
  for ($candidate = 5400; $candidate -le 5497 -and $null -eq $firstPort; $candidate++) {
    $first = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $candidate)
    $second = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $candidate + 1)
    try {
      $first.Start()
      $second.Start()
      if (Test-LossFitPortAvailable ($candidate + 2)) {
        $firstPort = $candidate
        $reserved.Add($first)
        $reserved.Add($second)
        $first = $null
        $second = $null
      }
    } catch {
      # Find a free consecutive range if another local service owns these ports.
    } finally {
      if ($first) { $first.Stop() }
      if ($second) { $second.Stop() }
    }
  }
  if ($null -eq $firstPort) { throw 'Could not reserve a free three-port range for the regression test.' }

  if (Test-LossFitPortAvailable $firstPort) { throw "Port $firstPort was reported available while occupied." }
  if (Test-LossFitPortAvailable ($firstPort + 1)) { throw "Port $($firstPort + 1) was reported available while occupied." }
  $selected = Get-LossFitFrontendPort -FirstPort $firstPort -LastPort ($firstPort + 2)
  if ($selected -ne ($firstPort + 2)) { throw "Expected port $($firstPort + 2) after occupying the first two ports; got $selected." }
  Write-Host "Windows port-selection regression passed (occupied $firstPort/$($firstPort + 1) -> selected $selected)."
} finally {
  foreach ($listener in $reserved) { $listener.Stop() }
}

$tokens = $null
$errors = $null
foreach ($file in @('dev-ports.ps1', 'start-dev.ps1', 'check-dev.ps1')) {
  [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $file), [ref]$tokens, [ref]$errors) | Out-Null
  if ($errors.Count) { throw "PowerShell syntax errors in $file`: $($errors.Message -join '; ')" }
}
Write-Host 'Windows development scripts parse without syntax errors.'
