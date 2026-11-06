function Test-LossFitPortAvailable([int]$Port) {
  $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
  try {
    $listener.Start()
    return $true
  } catch {
    return $false
  } finally {
    $listener.Stop()
  }
}

function Get-LossFitFrontendPort([int]$FirstPort = 5173, [int]$LastPort = 5193) {
  for ($port = $FirstPort; $port -le $LastPort; $port++) {
    if (Test-LossFitPortAvailable $port) { return $port }
  }
  throw "No free frontend port is available in the range $FirstPort-$LastPort."
}
