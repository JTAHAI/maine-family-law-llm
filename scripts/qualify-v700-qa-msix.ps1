param(
  [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
  [string]$FinalMsix = "",
  [string]$EvidenceRoot = "",
  [string]$WorkRoot = ""
)

$ErrorActionPreference = "Stop"
Import-Module Appx -ErrorAction Stop
$root = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $FinalMsix) { $FinalMsix = Join-Path $root "dist\release\v7.0.0\msix\MaineFamilyLawLLM_7.0.0.0_x64.msix" }
if (-not $EvidenceRoot) { $EvidenceRoot = Join-Path $root "dist\release\v7.0.0\evidence\qa-install" }
$final = (Resolve-Path -LiteralPath $FinalMsix).Path
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

function Invoke-InstalledProbe([string]$Executable, [string]$InstallRoot, [int]$Port) {
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
    $authority = Invoke-RestMethod -Uri "$base/api/authority/status" -TimeoutSec 20
    $search = Invoke-RestMethod -Uri "$base/api/authority/sources?query=parental%20rights&limit=3" -TimeoutSec 20
    $html = (Invoke-WebRequest -UseBasicParsing -Uri $base -TimeoutSec 20).Content
    return [ordered]@{
      status = if ($health.status -eq "ok" -and $authority.active -and $search.sources.Count -gt 0 -and $html.Contains("7.0.0")) { "pass" } else { "fail" }
      process_id = $process.Id
      health = $health
      authority_build_id = $authority.build_id
      authority_source_count = $authority.source_count
      search_result_count = $search.sources.Count
      ui_has_v700 = $html.Contains("7.0.0")
    }
  } finally {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    Wait-Process -Id $process.Id -Timeout 15 -ErrorAction SilentlyContinue
  }
}

$qaIdentity = "TAHAIWebServices.MaineFamilyLawLLM.QA7"
$publisher = "CN=MFL-v700-Isolated-QA"
$work = if ($WorkRoot) { [IO.Path]::GetFullPath($WorkRoot) } else { Join-Path $env:LOCALAPPDATA ("MaineFamilyLawLLM\QA\v700-msix-" + [Guid]::NewGuid().ToString("N")) }
$unpacked = Join-Path $work "unpacked"
New-Item -ItemType Directory -Force -Path $unpacked | Out-Null

$realBefore = @(Get-AppxPackage -Name "TAHAIWebServices.MaineFamilyLawLLM" -ErrorAction SilentlyContinue | ForEach-Object { $_.PackageFullName })
if (-not (Test-Path -LiteralPath (Join-Path $unpacked "AppxManifest.xml") -PathType Leaf)) {
  $makeAppx = Find-SdkTool "makeappx.exe"
  & $makeAppx unpack /o /p $final /d $unpacked | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "makeappx_unpack_failed" }
}
[xml]$manifest = Get-Content -Raw -LiteralPath (Join-Path $unpacked "AppxManifest.xml")
$manifest.Package.Identity.Name = $qaIdentity
$manifest.Package.Identity.Publisher = $publisher
$settings = New-Object System.Xml.XmlWriterSettings
$settings.Encoding = New-Object System.Text.UTF8Encoding($false)
$settings.Indent = $true
$writer = [System.Xml.XmlWriter]::Create((Join-Path $unpacked "AppxManifest.xml"), $settings)
try { $manifest.Save($writer) } finally { $writer.Dispose() }

$existingQa = @(Get-AppxPackage -Name $qaIdentity -ErrorAction SilentlyContinue)
foreach ($package in $existingQa) { Remove-AppxPackage -Package $package.PackageFullName -Confirm:$false }
$qaManifest = Join-Path $unpacked "AppxManifest.xml"
Add-AppxPackage -Register $qaManifest
$installed = Get-AppxPackage -Name $qaIdentity -ErrorAction Stop
$env:MFL_AUTHORITY_DATA_ROOT = "C:\dev\ME_FM_LLM_data"
$first = Invoke-InstalledProbe (Join-Path $installed.InstallLocation "MaineFamilyLawLLM.exe") $installed.InstallLocation 53471
$restart = Invoke-InstalledProbe (Join-Path $installed.InstallLocation "MaineFamilyLawLLM.exe") $installed.InstallLocation 53472
Remove-AppxPackage -Package $installed.PackageFullName -Confirm:$false
$uninstalled = -not [bool](Get-AppxPackage -Name $qaIdentity -ErrorAction SilentlyContinue)
Add-AppxPackage -Register $qaManifest
$reinstalled = Get-AppxPackage -Name $qaIdentity -ErrorAction Stop
$reinstallProbe = Invoke-InstalledProbe (Join-Path $reinstalled.InstallLocation "MaineFamilyLawLLM.exe") $reinstalled.InstallLocation 53473
$realAfter = @(Get-AppxPackage -Name "TAHAIWebServices.MaineFamilyLawLLM" -ErrorAction SilentlyContinue | ForEach-Object { $_.PackageFullName })

$report = [ordered]@{
  schema_version = "v700_isolated_qa_install_v1"
  generated_at = (Get-Date).ToUniversalTime().ToString("o")
  status = if ($first.status -eq "pass" -and $restart.status -eq "pass" -and $uninstalled -and $reinstallProbe.status -eq "pass" -and (($realBefore -join "|") -eq ($realAfter -join "|"))) { "pass" } else { "fail" }
  isolation = "unique QA identity via unpacked developer registration; real Store identity untouched"
  final_msix_sha256 = Get-Sha256Hex $final
  qa_payload_source = $final
  qa_manifest = $qaManifest
  qa_identity = $qaIdentity
  qa_package_full_name = $reinstalled.PackageFullName
  qa_install_location = $reinstalled.InstallLocation
  signing_classification = "unpacked isolated QA registration; final Store MSIX remains unsigned for Partner Center signing"
  real_store_package_before = $realBefore
  real_store_package_after = $realAfter
  clean_install = $first
  restart = $restart
  uninstall = if ($uninstalled) { "pass" } else { "fail" }
  reinstall = $reinstallProbe
  upgrade_from_v604_package = "NOT_EXECUTED: no isolated prior package; direct prior-schema migration passed"
  cleanup_required = [ordered]@{ qa_package = $reinstalled.PackageFullName; work_root = $work }
}
$report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $evidence "install-report.json") -Encoding utf8
$report | ConvertTo-Json -Depth 6 -Compress
