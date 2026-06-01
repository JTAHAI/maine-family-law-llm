param(
  [string]$RepoRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path),
  [string]$OutputZip = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repo = [System.IO.Path]::GetFullPath($RepoRoot)
Set-Location -LiteralPath $repo
python .\scripts\clean-local-artifacts.py --repo-root $repo --include-venv | Out-Host
python .\scripts\doctor-local-repo.py --repo-root $repo --json
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not $OutputZip) {
  $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
  $OutputZip = Join-Path -Path (Split-Path -Parent $repo) -ChildPath "ME_FM_LLM_review_$stamp.zip"
}
$output = [System.IO.Path]::GetFullPath($OutputZip)
if (Test-Path -LiteralPath $output) { Remove-Item -LiteralPath $output -Force }

$parent = Split-Path -Parent $repo
$name = Split-Path -Leaf $repo
Push-Location -LiteralPath $parent
try {
  Compress-Archive -Path $name -DestinationPath $output -Force
} finally {
  Pop-Location
}
Write-Output "review_zip=$output"
