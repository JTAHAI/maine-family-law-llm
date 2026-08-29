[CmdletBinding()]
param(
  [string]$RepoRoot = "",
  [string]$FinalMsix = "",
  [string]$EvidenceRoot = "",
  [string]$WorkRoot = "",
  [ValidateLength(38, 50)]
  [ValidatePattern('^TAHAIWebServices\.MaineFamilyLawLLM\.QA[A-Za-z0-9.-]{1,13}$')]
  [string]$QaIdentity = ("TAHAIWebServices.MaineFamilyLawLLM.QA" + [Guid]::NewGuid().ToString("N").Substring(0, 12))
)

$ErrorActionPreference = "Stop"
if (-not $RepoRoot) { $RepoRoot = Split-Path -Parent $PSScriptRoot }
Import-Module Appx -ErrorAction Stop
$root = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $FinalMsix) { throw "final_msix_required: pass -FinalMsix for the exact candidate under qualification" }
$final = (Resolve-Path -LiteralPath $FinalMsix).Path
$work = if ($WorkRoot) { [IO.Path]::GetFullPath($WorkRoot) } else { Join-Path $env:LOCALAPPDATA ("MaineFamilyLawLLM\QA\v700-msix-" + [Guid]::NewGuid().ToString("N")) }
if (Test-Path -LiteralPath $work) { throw "qa_work_root_must_be_new: preserve existing qualification data" }
if (Get-AppxPackage -Name $QaIdentity -ErrorAction Stop) { throw "qa_identity_already_registered: use a new isolated identity" }
if (-not $EvidenceRoot) {
  $candidateRoot = Split-Path -Parent (Split-Path -Parent $final)
  $EvidenceRoot = Join-Path $candidateRoot "evidence\isolated-qa"
}
if (Test-Path -LiteralPath (Join-Path $EvidenceRoot "install-report.json")) { throw "qa_evidence_already_exists: use a new evidence directory" }
New-Item -ItemType Directory -Force -Path $EvidenceRoot | Out-Null
$evidence = (Resolve-Path -LiteralPath $EvidenceRoot).Path

function Find-SdkTool([string]$Name) {
  $tool = Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin" -Recurse -Filter $Name -ErrorAction Stop |
    Where-Object { $_.FullName -match "\\x64\\" } | Sort-Object FullName -Descending | Select-Object -First 1
  if (-not $tool) { throw "Windows SDK tool missing: $Name" }
  return $tool.FullName
}

function Get-Sha256Hex([string]$Path) {
  $stream = [System.IO.File]::OpenRead($Path)
  try {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace("-", "").ToLowerInvariant() }
    finally { $sha.Dispose() }
  } finally { $stream.Dispose() }
}

function Invoke-InstalledProbe([string]$Executable, [string]$InstallRoot, [int]$Port, [string]$ExpectedProductVersion) {
  $process = Start-Process -FilePath $Executable -ArgumentList @("--serve-local-api", "--port", $Port) `
    -WorkingDirectory $InstallRoot -WindowStyle Hidden -PassThru
  $base = "http://127.0.0.1:$Port"
  try {
    $health = $null
    foreach ($attempt in 1..180) {
      try { $health = Invoke-RestMethod -Uri "$base/api/health" -TimeoutSec 2; break }
      catch { Start-Sleep -Milliseconds 250 }
    }
    if (-not $health) { throw "installed_runtime_health_timeout" }
    $version = Invoke-RestMethod -Uri "$base/api/version" -TimeoutSec 20
    $html = (Invoke-WebRequest -UseBasicParsing -Uri $base -TimeoutSec 20).Content
    return [ordered]@{
      status = if ($health.status -eq "ok" -and $version.version -eq $ExpectedProductVersion -and $html.Contains("workbench")) { "pass" } else { "fail" }
      process_id = $process.Id
      health = $health
      api_version = $version.version
      ui_has_workbench = $html.Contains("workbench")
      authority_note = "No authority corpus is mounted for this isolated package-payload check. Authority admission is separately evidence-gated."
    }
  } finally {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    Wait-Process -Id $process.Id -Timeout 15 -ErrorAction SilentlyContinue
  }
}

$unpacked = Join-Path $work "unpacked"
New-Item -ItemType Directory -Force -Path $unpacked | Out-Null

$realBefore = @(Get-AppxPackage -Name "TAHAIWebServices.MaineFamilyLawLLM" -ErrorAction SilentlyContinue | ForEach-Object { $_.PackageFullName })
if (-not (Test-Path -LiteralPath (Join-Path $unpacked "AppxManifest.xml") -PathType Leaf)) {
  $makeAppx = Find-SdkTool "makeappx.exe"
  & $makeAppx unpack /o /p $final /d $unpacked | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "makeappx_unpack_failed" }
}
[xml]$manifest = Get-Content -Raw -LiteralPath (Join-Path $unpacked "AppxManifest.xml")
$packageVersion = [string]$manifest.Package.Identity.Version
$expectedProductVersion = $packageVersion -replace '\.0$', ''
$manifest.Package.Identity.Name = $qaIdentity
$settings = New-Object System.Xml.XmlWriterSettings
$settings.Encoding = New-Object System.Text.UTF8Encoding($false)
$settings.Indent = $true
$writer = [System.Xml.XmlWriter]::Create((Join-Path $unpacked "AppxManifest.xml"), $settings)
try { $manifest.Save($writer) } finally { $writer.Dispose() }

function Write-BlockedQualification([string]$Reason, [string]$Detail) {
  $blocked = [ordered]@{
    schema_version = "isolated_qa_package_payload_install_v2"
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    status = "blocked"
    isolation = "unique QA identity via unpacked developer registration; real Store identity untouched"
    final_msix_sha256 = Get-Sha256Hex $final
    qa_payload_source = $final
    candidate_package_version = $packageVersion
    expected_product_version = $expectedProductVersion
    qa_identity = $qaIdentity
    qa_registration = [ordered]@{ status = "blocked"; reason = $Reason; detail = $Detail }
    signing_classification = "unpacked isolated QA payload registration; this does not qualify the unsigned final MSIX for Partner Center signing"
    real_store_package_before = $realBefore
    real_store_package_after = @(Get-AppxPackage -Name "TAHAIWebServices.MaineFamilyLawLLM" -ErrorAction SilentlyContinue | ForEach-Object { $_.PackageFullName })
    cleanup_required = [ordered]@{ qa_package = "not_registered"; work_root = $work }
  }
  $blocked | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $evidence "install-report.json") -Encoding utf8
  $blocked | ConvertTo-Json -Depth 6 -Compress
}

function Get-QARegistrationFailureReason([string]$Detail) {
  # A broken QA manifest is a harness defect, not proof of a host policy block.
  if ($Detail -match '0x80080204|0xC00CE169') { return "qa_manifest_invalid" }
  if ($Detail -match '0x80073CFF') { return "qa_registration_host_policy" }
  return "qa_registration_failed"
}

$qaManifest = Join-Path $unpacked "AppxManifest.xml"
try {
  Add-AppxPackage -Register $qaManifest
} catch {
  $detail = $_.Exception.Message
  Write-BlockedQualification (Get-QARegistrationFailureReason $detail) $detail
  exit 2
}
$installed = Get-AppxPackage -Name $qaIdentity -ErrorAction Stop
$isolatedAuthorityRoot = Join-Path $work "empty-authority-root"
New-Item -ItemType Directory -Force -Path $isolatedAuthorityRoot | Out-Null
$env:MFL_AUTHORITY_DATA_ROOT = $isolatedAuthorityRoot
$first = Invoke-InstalledProbe (Join-Path $installed.InstallLocation "MaineFamilyLawLLM.exe") $installed.InstallLocation 53471 $expectedProductVersion
$restart = Invoke-InstalledProbe (Join-Path $installed.InstallLocation "MaineFamilyLawLLM.exe") $installed.InstallLocation 53472 $expectedProductVersion
Remove-AppxPackage -Package $installed.PackageFullName -Confirm:$false
$uninstalled = -not [bool](Get-AppxPackage -Name $qaIdentity -ErrorAction SilentlyContinue)
Add-AppxPackage -Register $qaManifest
$reinstalled = Get-AppxPackage -Name $qaIdentity -ErrorAction Stop
$reinstallProbe = Invoke-InstalledProbe (Join-Path $reinstalled.InstallLocation "MaineFamilyLawLLM.exe") $reinstalled.InstallLocation 53473 $expectedProductVersion
$realAfter = @(Get-AppxPackage -Name "TAHAIWebServices.MaineFamilyLawLLM" -ErrorAction SilentlyContinue | ForEach-Object { $_.PackageFullName })

$report = [ordered]@{
  schema_version = "isolated_qa_package_payload_install_v2"
  generated_at = (Get-Date).ToUniversalTime().ToString("o")
  status = if ($first.status -eq "pass" -and $restart.status -eq "pass" -and $uninstalled -and $reinstallProbe.status -eq "pass" -and (($realBefore -join "|") -eq ($realAfter -join "|"))) { "pass" } else { "fail" }
  isolation = "unique QA identity via unpacked developer registration; real Store identity untouched"
  final_msix_sha256 = Get-Sha256Hex $final
  qa_payload_source = $final
  candidate_package_version = $packageVersion
  expected_product_version = $expectedProductVersion
  qa_manifest = $qaManifest
  qa_identity = $qaIdentity
  qa_package_full_name = $reinstalled.PackageFullName
  qa_install_location = $reinstalled.InstallLocation
  signing_classification = "unpacked isolated QA payload registration; this does not qualify the unsigned final MSIX for Partner Center signing"
  real_store_package_before = $realBefore
  real_store_package_after = $realAfter
  clean_install = $first
  restart = $restart
  uninstall = if ($uninstalled) { "pass" } else { "fail" }
  reinstall = $reinstallProbe
  upgrade_from_prior_package = "NOT_EXECUTED: no isolated prior package was provided."
  cleanup_required = [ordered]@{ qa_package = $reinstalled.PackageFullName; work_root = $work }
}
$report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $evidence "install-report.json") -Encoding utf8
$report | ConvertTo-Json -Depth 6 -Compress
