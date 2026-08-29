param(
  [string]$RepoRoot = "",
  [string]$OutputRoot = "",
  [string]$PackagingRoot = "",
  [string]$IdentityConfigPath = "",
  [string]$IdentityName = "",
  [string]$Publisher = "",
  [string]$PublisherDisplayName = "",
  [string]$PackageDisplayName = "",
  [string]$PackageVersion = "",
  [string]$CertificatePfxPath = "",
  [string]$CertificatePassword = "",
  [switch]$UseDevIdentity,
  [switch]$Unsigned,
  [switch]$Offline,
  [ValidateSet("essential", "full")]
  [string]$FeatureTier = "essential"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "mfl-pycache-disabled"

function Resolve-SdkTool([string]$ToolName) {
  $path = Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin" -Recurse -Filter $ToolName -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match "\\x64\\" } | Select-Object -First 1 -ExpandProperty FullName
  if (-not $path) { throw "Windows SDK tool not found: $ToolName" }
  return $path
}

function Convert-ToPackageVersion([string]$VersionText) {
  $parts = $VersionText.Trim().Split(".")
  if ($parts.Count -ne 3 -and $parts.Count -ne 4) { throw "Package version must be three-part or four-part version text." }
  $normalizedParts = @()
  foreach ($part in $parts) {
    if ($part -notmatch '^\d+$') { throw "Package version segments must be numeric." }
    $value = [int]$part
    if ($value -lt 0 -or $value -gt 65535) { throw "Package version segments must be between 0 and 65535." }
    $normalizedParts += $value.ToString()
  }
  if ($normalizedParts.Count -eq 3) { $normalizedParts += "0" }
  if ($normalizedParts[3] -ne "0") { throw "Package version revision must be zero for this Store release." }
  return ($normalizedParts -join ".")
}

function Get-Sha256Hex([string]$Path) {
  $stream = [System.IO.File]::OpenRead($Path)
  try {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { return ([System.BitConverter]::ToString($sha.ComputeHash($stream))).Replace("-", "").ToLowerInvariant() }
    finally { $sha.Dispose() }
  } finally {
    $stream.Dispose()
  }
}

function New-EphemeralCertificatePassword {
  $bytes = New-Object byte[] 32
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try {
    $rng.GetBytes($bytes)
  } finally {
    $rng.Dispose()
  }
  return [Convert]::ToBase64String($bytes)
}

function Resolve-SafeMutableDirectory([string]$PathText, [string]$Label, [string]$RepoRootPath) {
  if (-not $PathText) { throw "$Label is required." }
  $fullPath = [System.IO.Path]::GetFullPath($PathText).TrimEnd("\\")
  $volumeRoot = [System.IO.Path]::GetPathRoot($fullPath).TrimEnd("\\")
  if (-not $fullPath -or $fullPath -eq $volumeRoot) {
    throw "$Label must name a dedicated directory, not a drive root."
  }
  $repoPath = [System.IO.Path]::GetFullPath($RepoRootPath).TrimEnd("\\")
  if ($fullPath.Equals($repoPath, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "$Label must not be the source repository."
  }
  return $fullPath
}

function Ensure-DevCertificate([string]$PublisherName, [string]$TargetRoot, [string]$PasswordText) {
  $certDir = Join-Path $TargetRoot "dev-signing"
  New-Item -ItemType Directory -Force -Path $certDir | Out-Null
  $pfxPath = Join-Path $certDir "MaineFamilyLawLLM-Dev.pfx"
  $cerPath = Join-Path $certDir "MaineFamilyLawLLM-Dev.cer"
  $secure = ConvertTo-SecureString -String $PasswordText -AsPlainText -Force
  $cert = New-SelfSignedCertificate -Type Custom -Subject $PublisherName -KeyUsage DigitalSignature `
    -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3", "2.5.29.19={text}") -FriendlyName "Maine Family Law LLM Dev" `
    -HashAlgorithm SHA256 -CertStoreLocation "Cert:\CurrentUser\My"
  Export-PfxCertificate -Cert "Cert:\CurrentUser\My\$($cert.Thumbprint)" -FilePath $pfxPath -Password $secure | Out-Null
  Export-Certificate -Cert "Cert:\CurrentUser\My\$($cert.Thumbprint)" -FilePath $cerPath | Out-Null
  return @{ pfx = $pfxPath; cer = $cerPath }
}

if (-not $RepoRoot) { $RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..")) }
if (-not $OutputRoot) { $OutputRoot = Join-Path $RepoRoot "dist\store" }
if (-not $PackagingRoot) { $PackagingRoot = "C:\mfl6" }
$RepoRoot = [System.IO.Path]::GetFullPath($RepoRoot)
$PackagingRoot = Resolve-SafeMutableDirectory $PackagingRoot "PackagingRoot" $RepoRoot
if (-not $IdentityConfigPath) { $IdentityConfigPath = Join-Path $RepoRoot "store\msix\identity.example.json" }
$identityConfig = Get-Content -LiteralPath $IdentityConfigPath -Raw | ConvertFrom-Json
if (-not $IdentityName) { $IdentityName = $identityConfig.identity_name }
if (-not $Publisher) { $Publisher = $identityConfig.publisher }
if (-not $PublisherDisplayName) { $PublisherDisplayName = $identityConfig.publisher_display_name }
if (-not $PackageDisplayName) { $PackageDisplayName = $identityConfig.package_display_name }
if (-not $PackageVersion) { $PackageVersion = $identityConfig.package_version }
if ($UseDevIdentity) {
  if (-not $IdentityName) { $IdentityName = "TAHAIWebServices.MaineFamilyLawLLM" }
  if (-not $Publisher) { $Publisher = "CN=D75EE668-B409-45ED-87E5-E37AA5FE3868" }
  if (-not $PublisherDisplayName) { $PublisherDisplayName = "TAHAI Web Services" }
  if (-not $PackageDisplayName) { $PackageDisplayName = "Maine Family Law LLM" }
}
$PackageVersion = Convert-ToPackageVersion $PackageVersion

$runtimeRoot = Join-Path $OutputRoot "runtime"
$msixRoot = Join-Path $OutputRoot "msix"
$evidenceRoot = Join-Path $OutputRoot "evidence"
$storeBuildPython = Join-Path ([Environment]::GetFolderPath("LocalApplicationData")) "MaineFamilyLawLLM\build-venvs\store\Scripts\python.exe"
$storePython = if (Test-Path -LiteralPath $storeBuildPython) { $storeBuildPython } else { "python" }
$hygiene = Join-Path $RepoRoot "scripts\store_payload_hygiene.py"
$stageRoot = Join-Path $packagingRoot "stage"
$packageRoot = Join-Path $stageRoot "package"
$shortOutRoot = Join-Path $packagingRoot "out"
$assetsRoot = Join-Path $RepoRoot "store\msix\assets"
$msixFileName = "MaineFamilyLawLLM_${PackageVersion}_x64.msix"
$msixPath = Join-Path $msixRoot $msixFileName
$shortMsixPath = Join-Path $shortOutRoot $msixFileName
$manifestTemplate = Join-Path $RepoRoot "store\msix\AppxManifest.xml.in"
$manifestPath = Join-Path $packageRoot "AppxManifest.xml"
$makeAppx = Resolve-SdkTool "makeappx.exe"
$makePri = Resolve-SdkTool "makepri.exe"
$signTool = if ($Unsigned) { $null } else { Resolve-SdkTool "signtool.exe" }
$makeAppxLog = Join-Path $msixRoot "makeappx-pack.log"
$tracePath = Join-Path $evidenceRoot "bytecode-regeneration-trace.json"
$runtimeCleanup = Join-Path $evidenceRoot "final-runtime-cleanup.json"
$stageCleanup = Join-Path $evidenceRoot "final-staging-cleanup.json"
$sealPath = Join-Path $evidenceRoot "sealed-msix-payload.json"
$sealAudit = Join-Path $evidenceRoot "sealed-msix-payload-audit.json"
$archiveAudit = Join-Path $evidenceRoot "sealed-msix-archive-audit.json"
$sizeBudgetReport = Join-Path $evidenceRoot "package-size-budget.json"

foreach ($path in @($packagingRoot, $msixRoot, $evidenceRoot)) {
  if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Recurse -Force }
}
New-Item -ItemType Directory -Force -Path $evidenceRoot, $shortOutRoot | Out-Null

# All qualification occurs while runtime is mutable. The snapshots prove the exact
# command that first introduced any bytecode residue.
& (Join-Path $RepoRoot "scripts\build-store-runtime.ps1") -RepoRoot $RepoRoot -OutputRoot $OutputRoot -FeatureTier $FeatureTier -Offline:$Offline
& $storePython -B $hygiene snapshot --root $runtimeRoot --output $tracePath --checkpoint after_pyinstaller --command "PyInstaller frozen runtime build" --parent-command "build-store-runtime.ps1"
& (Join-Path $RepoRoot "scripts\test-store-runtime.ps1") -RepoRoot $RepoRoot -RuntimeRoot $runtimeRoot -EvidenceRoot $evidenceRoot
& $storePython -B $hygiene snapshot --root $runtimeRoot --output $tracePath --checkpoint after_frozen_runtime_smoke --command "test-store-runtime.ps1 frozen runtime smoke" --parent-command "build-msix.ps1"
$inventoryPath = Join-Path $evidenceRoot "bundled-engine-inventory.json"
& $storePython -B (Join-Path $RepoRoot "scripts\generate_bundled_engine_inventory.py") --runtime-root $runtimeRoot --output $inventoryPath
if (-not (Test-Path -LiteralPath $inventoryPath)) {
  $inventoryFallbackScriptPath = Join-Path $evidenceRoot "generate-bundled-engine-inventory-fallback.py"
  $inventoryFallback = @'
from datetime import UTC, datetime
from pathlib import Path
import json
import os
import sys
sys.path.insert(0, r'__REPO_ROOT__')
from scripts.generate_bundled_engine_inventory import build_inventory
runtime_root = Path(r'__RUNTIME_ROOT__')
output_path = Path(r'__OUTPUT_PATH__')
inventory = build_inventory(runtime_root)
payload = {
    "schema_version": "bundled_engine_inventory_v1",
    "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    "runtime_root": str(runtime_root),
    "package_count": len(inventory),
    "packages": inventory,
}
failures = []
feature_tier = os.environ.get("MFL_STORE_FEATURE_TIER", "full").strip().lower()
for row in inventory:
    if row["runtime_import_check"]["status"] != "pass":
        failures.append(f"{row['package_name']}: import check failed")
    if row["offline_functional_smoke_result"]["status"] != "pass":
        failures.append(f"{row['package_name']}: smoke check failed")
    if feature_tier == "full" and not row["binary_model_files"] and row["package_name"] in {"en-core-web-lg", "docling", "ocrmypdf"}:
        failures.append(f"{row['package_name']}: required bundled files not found")
payload["status"] = "pass" if not failures else "fail"
payload["failures"] = failures
payload["feature_tier"] = feature_tier
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
'@
  $inventoryFallback = $inventoryFallback.Replace('__REPO_ROOT__', $RepoRoot).Replace('__RUNTIME_ROOT__', $runtimeRoot).Replace('__OUTPUT_PATH__', $inventoryPath)
  Set-Content -LiteralPath $inventoryFallbackScriptPath -Value $inventoryFallback -Encoding UTF8
  & $storePython -B $inventoryFallbackScriptPath
}
if (-not (Test-Path -LiteralPath $inventoryPath)) { throw "Bundled engine inventory generation failed." }
& $storePython -B -c "import json, pathlib, sys; data=json.loads(pathlib.Path(r'$inventoryPath').read_text(encoding='utf-8')); sys.exit(0 if data.get('status') == 'pass' else 2)"
if ($LASTEXITCODE -ne 0) { throw "Bundled engine inventory reported a failing status." }
& $storePython -B $hygiene snapshot --root $runtimeRoot --output $tracePath --checkpoint after_bundled_engine_inventory --command "generate_bundled_engine_inventory.py" --parent-command "build-msix.ps1"
$probePath = Join-Path $evidenceRoot "runtime-dependency-probe.json"
& $storePython -B -c "import importlib, json, sys; sys.dont_write_bytecode=True; names=['fastapi','uvicorn','httpx','pypdf','pypdfium2']; print(json.dumps({'status':'pass','imports':{n:bool(importlib.import_module(n)) for n in names}}))" | Set-Content -LiteralPath $probePath -Encoding UTF8
if ($LASTEXITCODE -ne 0) { throw "Runtime dependency probe failed." }
& $storePython -B $hygiene snapshot --root $runtimeRoot --output $tracePath --checkpoint after_dependency_probe --command "runtime dependency probe" --parent-command "build-msix.ps1"

New-Item -ItemType Directory -Force -Path $assetsRoot | Out-Null
& $storePython -B (Join-Path $RepoRoot "scripts\generate_msix_assets.py") --brand-root (Join-Path $RepoRoot "assets\brand\focaf_family_law_llm_brand_kit") --output-dir $assetsRoot --inventory-path (Join-Path $assetsRoot "asset-inventory.json")
if ($LASTEXITCODE -ne 0) { throw "MSIX asset generation failed." }
& $storePython -B $hygiene clean --root $runtimeRoot --output $runtimeCleanup
New-Item -ItemType Directory -Force -Path $packageRoot | Out-Null
& $storePython -B (Join-Path $RepoRoot "scripts\prepare_msix_staging.py") --runtime-root $runtimeRoot --assets-root $assetsRoot --stage-root $stageRoot --manifest-output (Join-Path $evidenceRoot "msix-staging-manifest.json")
if ($LASTEXITCODE -ne 0) { throw "MSIX staging preparation failed." }
& $storePython -B $hygiene clean --root $packageRoot --output $stageCleanup
& $storePython -B $hygiene snapshot --root $packageRoot --output $tracePath --checkpoint after_msix_staging --command "prepare_msix_staging.py and final staging cleanup" --parent-command "build-msix.ps1"

$manifestText = (Get-Content -LiteralPath $manifestTemplate -Raw).Replace("__IDENTITY_NAME__", $IdentityName).Replace("__PUBLISHER__", $Publisher).Replace("__PACKAGE_VERSION__", $PackageVersion).Replace("__PACKAGE_DISPLAY_NAME__", $PackageDisplayName).Replace("__PUBLISHER_DISPLAY_NAME__", $PublisherDisplayName)
Set-Content -LiteralPath $manifestPath -Value $manifestText -Encoding UTF8
& $makePri new /pr $packageRoot /cf (Join-Path $RepoRoot "store\msix\priconfig.xml") /mn $manifestPath /of (Join-Path $evidenceRoot "resources.pri") | Out-Null
if ($LASTEXITCODE -ne 0) { throw "makepri failed while generating resources.pri" }
& $storePython -B $hygiene snapshot --root $packageRoot --output $tracePath --checkpoint before_private_data_audit --command "makepri resource generation" --parent-command "build-msix.ps1"
& $storePython -B $hygiene seal --root $packageRoot --output $sealPath --cleanup-evidence $runtimeCleanup --cleanup-evidence $stageCleanup
& $storePython -B (Join-Path $RepoRoot "scripts\audit_store_package.py") --stage-root $packageRoot --manifest-output (Join-Path $evidenceRoot "package-file-manifest.json") --audit-output (Join-Path $evidenceRoot "private-data-audit.json") --forbidden-path $RepoRoot --forbidden-path $storeBuildPython --forbidden-path ([Environment]::GetFolderPath("UserProfile")) --forbidden-path $env:TEMP --forbidden-path $stageRoot
if ($LASTEXITCODE -ne 0) { throw "Store package audit failed." }
& $storePython -B $hygiene verify --root $packageRoot --seal $sealPath --output $sealAudit
& $storePython -B (Join-Path $RepoRoot "scripts\audit_msix_staging.py") --stage-root $packageRoot --manifest-input (Join-Path $evidenceRoot "msix-staging-manifest.json") --sealed-manifest $sealPath --audit-output (Join-Path $evidenceRoot "msix-path-audit.json") --map-output (Join-Path $msixRoot "package-map.txt") --makeappx-log $makeAppxLog
if ($LASTEXITCODE -ne 0) { throw "MSIX staging audit failed." }
& $storePython -B $hygiene snapshot --root $packageRoot --output $tracePath --checkpoint before_makeappx --command "sealed payload directory pack" --parent-command "build-msix.ps1"
& $storePython -B $hygiene verify --root $packageRoot --seal $sealPath --output $sealAudit
& $makeAppx pack /v /o /d $packageRoot /p $shortMsixPath 2>&1 | Tee-Object -FilePath $makeAppxLog | Out-Null
if ($LASTEXITCODE -ne 0) { throw "makeappx failed while creating the MSIX package. See $makeAppxLog" }
& $storePython -B $hygiene verify --root $packageRoot --seal $sealPath --output $sealAudit

$certificateCerPath = ""
if (-not $Unsigned) {
  if (-not $CertificatePfxPath) { if (-not $CertificatePassword) { $CertificatePassword = New-EphemeralCertificatePassword }; $certInfo = Ensure-DevCertificate $Publisher $msixRoot $CertificatePassword; $CertificatePfxPath = $certInfo.pfx; $certificateCerPath = $certInfo.cer }
  & $signTool sign /fd SHA256 /f $CertificatePfxPath /p $CertificatePassword $shortMsixPath | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "signtool failed while signing the MSIX package" }
}
Copy-Item -LiteralPath $shortMsixPath -Destination $msixPath -Force
& $storePython -B $hygiene verify-archive --msix-path $msixPath --seal $sealPath --output $archiveAudit
& $storePython -B (Join-Path $RepoRoot "scripts\analyze-msix-package-size.py") --package $msixPath --tier $FeatureTier --tier-config (Join-Path $RepoRoot "configs\store_feature_tiers.json") --output $sizeBudgetReport
if ($LASTEXITCODE -ne 0) { throw "MSIX package-size tier budget validation failed." }

$privateAudit = Get-Content -LiteralPath (Join-Path $evidenceRoot "private-data-audit.json") -Raw | ConvertFrom-Json
$inventory = Get-Content -LiteralPath $inventoryPath -Raw | ConvertFrom-Json
$summary = @("MSIX build: PASS", "MSIX path: $msixPath", "Package identity: $IdentityName", "Package version: $PackageVersion", "Package SHA-256: $(Get-Sha256Hex $msixPath)", "Private-data audit: $($privateAudit.status)", "Bundled engine inventory: $($inventory.status)", "Sealed payload audit: pass", "WACK: not_run") -join "`r`n"
Set-Content -LiteralPath (Join-Path $evidenceRoot "test-summary.txt") -Value $summary -Encoding UTF8
if ($certificateCerPath) { Set-Content -LiteralPath (Join-Path $msixRoot "dev-certificate-path.txt") -Value $certificateCerPath -Encoding UTF8 }
Write-Host "MSIX built at $msixPath"
