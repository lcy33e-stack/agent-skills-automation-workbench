$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root

$electronCli = Join-Path $root "node_modules\electron\cli.js"
if (-not (Test-Path -LiteralPath $electronCli)) {
  npm install
}

Start-Process -FilePath "node" -ArgumentList @($electronCli, ".") -WorkingDirectory $root

