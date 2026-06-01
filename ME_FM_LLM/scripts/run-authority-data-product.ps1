param(
    [string[]]$Args
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Push-Location $Root
try {
    python scripts/run-authority-data-product.py @Args
}
finally {
    Pop-Location
}
