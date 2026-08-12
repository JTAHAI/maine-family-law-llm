param(
  [Parameter(Mandatory=$true)][string]$RepoRoot,
  [Parameter(Mandatory=$true)][string]$PackagePath,
  [Parameter(Mandatory=$true)][string]$EvidenceRoot
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path $RepoRoot).Path
$PackagePath = (Resolve-Path $PackagePath).Path
New-Item -ItemType Directory -Force -Path $EvidenceRoot | Out-Null
$EvidenceRoot = (Resolve-Path $EvidenceRoot).Path

function Require-Command([string]$Name) {
  $cmd = Get-Command $Name -ErrorAction SilentlyContinue
  if (-not $cmd) { throw "Required tool unavailable: $Name" }
  return $cmd.Source
}

$syft = Require-Command "syft"
$grype = Require-Command "grype"
$semgrep = Require-Command "semgrep"
$pipAudit = Require-Command "pip-audit"

& $syft "dir:$RepoRoot" -o "cyclonedx-json=$EvidenceRoot\sbom.cyclonedx.json" -o "spdx-json=$EvidenceRoot\sbom.spdx.json"
& $grype "sbom:$EvidenceRoot\sbom.cyclonedx.json" -o json | Set-Content -Encoding utf8 "$EvidenceRoot\grype.json"
& $pipAudit --format json --output "$EvidenceRoot\pip-audit.json"
& $semgrep --config "$RepoRoot\.semgrep\maine-family-law-llm.yml" --json --output "$EvidenceRoot\semgrep.json" "$RepoRoot"

$packageHash = (Get-FileHash -Algorithm SHA256 $PackagePath).Hash.ToLowerInvariant()
$qualification = [ordered]@{
  schema_version = "msix_qualification_v1"
  package_filename = [IO.Path]::GetFileName($PackagePath)
  package_sha256 = $packageHash
  package_version = ""
  architecture = "x64"
  signature_report_filename = ""
  signature_report_sha256 = ""
  install_smoke_filename = ""
  install_smoke_sha256 = ""
  wack_report_filename = ""
  wack_report_sha256 = ""
  signed = $false
  signature_verified = $false
  install_passed = $false
  launch_passed = $false
  api_health_passed = $false
  ui_load_passed = $false
  uninstall_passed = $false
  reinstall_passed = $false
  wack_status = "not_run"
  note = "Populate only from completed Windows signing, install, launch, uninstall, reinstall, and WACK evidence."
}
$qualification | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 "$EvidenceRoot\msix-qualification.json"

Write-Host "Supply-chain reports created. The MSIX qualification file remains fail-closed until real Windows evidence is recorded."
