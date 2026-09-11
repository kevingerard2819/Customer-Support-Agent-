$nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
if (-not $nodeCommand) { throw 'Node.js 20+ is required.' }
$serverScript = Join-Path $PSScriptRoot 'scripts/rate_replies_server.mjs'
$existing = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
if (-not $existing) {
    Start-Process -FilePath $nodeCommand.Source -ArgumentList ('"' + $serverScript + '"') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
    Start-Sleep -Milliseconds 700
}
Start-Process 'http://127.0.0.1:8765/'
