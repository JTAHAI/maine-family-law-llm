param(
  [string]$RepoRoot = "",
  [string]$OutputRoot = "",
  [string]$IdentityConfigPath = "",
  [string]$IdentityName = "",
  [string]$Publisher = "",
  [string]$PublisherDisplayName = "",
  [string]$PackageDisplayName = "",
  [string]$PackageVersion = "",
  [string]$CertificatePfxPath = "",
  [string]$CertificatePassword = "",
  [switch]$UseDevIdentity,
  [switch]$Unsigned
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-SdkTool([string]$ToolName) {
  $path = Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin" -Recurse -Filter $ToolName -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match "\\x64\\" } |
    Select-Object -First 1 -ExpandProperty FullName
  if (-not $path) {
    throw "Windows SDK tool not found: $ToolName"
  }
  return $path
}

function Convert-ToPackageVersion([string]$VersionText) {
  $trimmed = $VersionText.Trim()
  if (-not $trimmed) {
    throw "Package version is required."
  }
  $parts = $trimmed.Split(".")
  if ($parts.Count -ne 3 -and $parts.Count -ne 4) {
    throw "Package version must be three-part or four-part version text."
  }
  $normalizedParts = @()
  foreach ($part in $parts) {
    if ($part -notmatch '^\d+$') {
      throw "Package version segments must be numeric."
    }
    $value = [int]$part
    if ($value -lt 0 -or $value -gt 65535) {
      throw "Package version segments must be between 0 and 65535."
    }
    $normalizedParts += $value.ToString()
  }
  if ($normalizedParts.Count -eq 3) {
    $normalizedParts += "0"
  }
  if ($normalizedParts[3] -ne "0") {
    throw "Package version revision must be zero for this Store release."
  }
  return ($normalizedParts -join ".")
}

function Get-VersionInfo([string]$RepoRootPath) {
  $json = python -c "import json, pathlib, sys; sys.path[:0]=[r'$RepoRootPath', r'$RepoRootPath\\src']; from maine_family_law_llm.version import VERSION; print(json.dumps({'version': VERSION}))"
  return ($json | ConvertFrom-Json)
}

function Load-IdentityConfig([string]$PathText) {
  if (-not $PathText) {
    return $null
  }
  if (-not (Test-Path -LiteralPath $PathText)) {
    throw "Identity config not found: $PathText"
  }
  return (Get-Content -Path $PathText -Raw | ConvertFrom-Json)
}

function New-EphemeralCertificatePassword {
  $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try {
    $bytes = New-Object byte[] 32
    $generator.GetBytes($bytes)
    return [Convert]::ToBase64String($bytes)
  } finally {
    $generator.Dispose()
  }
}

function Ensure-DevCertificate([string]$PublisherName, [string]$TargetRoot, [string]$PasswordText) {
  $certDir = Join-Path $TargetRoot "dev-signing"
  New-Item -ItemType Directory -Force -Path $certDir | Out-Null
  $pfxPath = Join-Path $certDir "MaineFamilyLawLLM-Dev.pfx"
  $cerPath = Join-Path $certDir "MaineFamilyLawLLM-Dev.cer"
  $secure = ConvertTo-SecureString -String $PasswordText -AsPlainText -Force
  $cert = New-SelfSignedCertificate `
    -Type Custom `
    -Subject $PublisherName `
    -KeyUsage DigitalSignature `
    -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3", "2.5.29.19={text}") `
    -FriendlyName "Maine Family Law LLM Dev" `
    -HashAlgorithm SHA256 `
    -CertStoreLocation "Cert:\CurrentUser\My"
  Export-PfxCertificate -Cert "Cert:\CurrentUser\My\$($cert.Thumbprint)" -FilePath $pfxPath -Password $secure | Out-Null
  Export-Certificate -Cert "Cert:\CurrentUser\My\$($cert.Thumbprint)" -FilePath $cerPath | Out-Null
  return @{
    pfx = $pfxPath
    cer = $cerPath
    thumbprint = $cert.Thumbprint
  }
}

if (-not $RepoRoot) {
  $RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
}
if (-not $OutputRoot) {
  $OutputRoot = Join-Path $RepoRoot "dist\store"
}
if (-not $IdentityConfigPath) {
  $defaultIdentityConfigPath = Join-Path $RepoRoot "store\msix\identity.example.json"
  if (Test-Path -LiteralPath $defaultIdentityConfigPath) {
    $IdentityConfigPath = $defaultIdentityConfigPath
  }
}

$versionInfo = Get-VersionInfo $RepoRoot
$identityConfig = Load-IdentityConfig $IdentityConfigPath
if ($identityConfig) {
  if (-not $IdentityName) { $IdentityName = $identityConfig.identity_name }
  if (-not $Publisher) { $Publisher = $identityConfig.publisher }
  if (-not $PublisherDisplayName) { $PublisherDisplayName = $identityConfig.publisher_display_name }
  if (-not $PackageDisplayName) { $PackageDisplayName = $identityConfig.package_display_name }
  if (-not $PackageVersion) { $PackageVersion = $identityConfig.package_version }
}
if ($UseDevIdentity) {
  if (-not $IdentityName) { $IdentityName = "TAHAIWebServices.MaineFamilyLawLLM" }
  if (-not $Publisher) { $Publisher = "CN=D75EE668-B409-45ED-87E5-E37AA5FE3868" }
  if (-not $PublisherDisplayName) { $PublisherDisplayName = "TAHAI Web Services" }
  if (-not $PackageDisplayName) { $PackageDisplayName = "Maine Family Law LLM" }
  if (-not $PackageVersion) { $PackageVersion = "$($versionInfo.version).0" }
}
if (-not $IdentityName -or -not $Publisher -or -not $PublisherDisplayName -or -not $PackageDisplayName -or -not $PackageVersion) {
  throw "Identity Name, Publisher, Publisher Display Name, Package Display Name, and Package Version are required."
}
$PackageVersion = Convert-ToPackageVersion $PackageVersion

$runtimeRoot = Join-Path $OutputRoot "runtime"
$msixRoot = Join-Path $OutputRoot "msix"
$evidenceRoot = Join-Path $OutputRoot "evidence"
$stageRoot = Join-Path $msixRoot "staging"
$packageRoot = Join-Path $stageRoot "package"
$assetsRoot = Join-Path $RepoRoot "store\msix\assets"
$assetInventory = Join-Path $assetsRoot "asset-inventory.json"
$msixPath = Join-Path $msixRoot "MaineFamilyLawLLM_x64.msix"
$manifestTemplate = Join-Path $RepoRoot "store\msix\AppxManifest.xml.in"
$manifestPath = Join-Path $packageRoot "AppxManifest.xml"
$priConfig = Join-Path $RepoRoot "store\msix\priconfig.xml"
$makeAppx = Resolve-SdkTool "makeappx.exe"
$makePri = Resolve-SdkTool "makepri.exe"
$signTool = if ($Unsigned) { $null } else { Resolve-SdkTool "signtool.exe" }

& (Join-Path $RepoRoot "scripts\build-store-runtime.ps1") -RepoRoot $RepoRoot -OutputRoot $OutputRoot

$storeBuildPython = Join-Path `
  ([Environment]::GetFolderPath("LocalApplicationData")) `
  "MaineFamilyLawLLM\build-venvs\store\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $storeBuildPython)) {
  throw "Store build Python was not created at $storeBuildPython"
}

& (Join-Path $RepoRoot "scripts\test-store-runtime.ps1") `
  -RepoRoot $RepoRoot `
  -RuntimeRoot $runtimeRoot `
  -EvidenceRoot $evidenceRoot

New-Item -ItemType Directory -Force -Path $assetsRoot | Out-Null
& $storeBuildPython (Join-Path $RepoRoot "scripts\generate_msix_assets.py") `
  --brand-root (Join-Path $RepoRoot "assets\brand\focaf_family_law_llm_brand_kit") `
  --output-dir $assetsRoot `
  --inventory-path $assetInventory

foreach ($path in @($stageRoot, $msixRoot)) {
  if (Test-Path -LiteralPath $path) {
    Remove-Item -LiteralPath $path -Recurse -Force
  }
}
New-Item -ItemType Directory -Force -Path $packageRoot | Out-Null
New-Item -ItemType Directory -Force -Path $evidenceRoot | Out-Null
Copy-Item -Path (Join-Path $runtimeRoot "*") -Destination $packageRoot -Recurse -Force
Copy-Item -Path $assetsRoot -Destination (Join-Path $packageRoot "Assets") -Recurse -Force

$manifestText = (Get-Content -Path $manifestTemplate -Raw).
  Replace("__IDENTITY_NAME__", $IdentityName).
  Replace("__PUBLISHER__", $Publisher).
  Replace("__PACKAGE_VERSION__", $PackageVersion).
  Replace("__PACKAGE_DISPLAY_NAME__", $PackageDisplayName).
  Replace("__PUBLISHER_DISPLAY_NAME__", $PublisherDisplayName)
Set-Content -Path $manifestPath -Value $manifestText -Encoding UTF8

& $makePri new /pr $packageRoot /cf $priConfig /mn $manifestPath /of (Join-Path $packageRoot "resources.pri") | Out-Null
if (Test-Path -LiteralPath $msixPath) {
  Remove-Item -LiteralPath $msixPath -Force
}
& $makeAppx pack /d $packageRoot /p $msixPath /o | Out-Null

$certificateCerPath = ""
if (-not $Unsigned) {
  if (-not $CertificatePfxPath) {
    if (-not $CertificatePassword) {
      $CertificatePassword = New-EphemeralCertificatePassword
    }
    $certInfo = Ensure-DevCertificate $Publisher $msixRoot $CertificatePassword
    $CertificatePfxPath = $certInfo.pfx
    $certificateCerPath = $certInfo.cer
  } else {
    $certificateCerPath = ""
  }
  & $signTool sign /fd SHA256 /f $CertificatePfxPath /p $CertificatePassword $msixPath | Out-Null

}

& $storeBuildPython (Join-Path $RepoRoot "scripts\audit_store_package.py") `
  --stage-root $packageRoot `
  --manifest-output (Join-Path $evidenceRoot "package-file-manifest.json") `
  --audit-output (Join-Path $evidenceRoot "private-data-audit.json") `
  --sha-output (Join-Path $evidenceRoot "package-sha256.txt") `
  --msix-path $msixPath

if ($LASTEXITCODE -ne 0) {
  $failedAuditPath = Join-Path $evidenceRoot "private-data-audit.json"

  if (Test-Path -LiteralPath $failedAuditPath) {
    Write-Host "Private-data audit findings:" -ForegroundColor Red
    Write-Host (Get-Content -LiteralPath $failedAuditPath -Raw)
  }

  throw "Store-package private-data audit failed."
}

$smokePath = Join-Path $evidenceRoot "store-build-smoke.json"
$smoke = Get-Content -Path $smokePath -Raw | ConvertFrom-Json
$packageManifest = Get-Content -Path (Join-Path $evidenceRoot "package-file-manifest.json") -Raw | ConvertFrom-Json
$privateAudit = Get-Content -Path (Join-Path $evidenceRoot "private-data-audit.json") -Raw | ConvertFrom-Json

if ($privateAudit.status -ne "pass") {
  Write-Host ($privateAudit | ConvertTo-Json -Depth 8) -ForegroundColor Red
  throw "Private-data audit did not pass."
}

$gitCommit = "unavailable"
if ((Get-Command git -ErrorAction SilentlyContinue) -and (Test-Path -LiteralPath (Join-Path $RepoRoot ".git"))) {
  $candidateCommit = (& git -C $RepoRoot rev-parse HEAD 2>$null).Trim()
  if ($LASTEXITCODE -eq 0 -and $candidateCommit) {
    $gitCommit = $candidateCommit
  }
}
$runtimeDeps = & $storeBuildPython -c "import importlib.metadata as m, json; names=['fastapi','starlette','uvicorn','httpx','pypdf','pypdfium2','python-docx','defusedxml','docx-editor']; print(json.dumps({n:m.version(n) for n in names}))"

if ($LASTEXITCODE -ne 0) {
  throw "Could not read dependency versions from the Store build environment."
}
$wackFolder = Join-Path $evidenceRoot "wack"
New-Item -ItemType Directory -Force -Path $wackFolder | Out-Null
$smoke | Add-Member -NotePropertyName git_commit -NotePropertyValue $gitCommit -Force
$smoke | Add-Member -NotePropertyName package_identity -NotePropertyValue $IdentityName -Force
$smoke | Add-Member -NotePropertyName package_version -NotePropertyValue $PackageVersion -Force
$smoke | Add-Member -NotePropertyName build_timestamp -NotePropertyValue ([DateTime]::UtcNow.ToString("o")) -Force
$smoke | Add-Member -NotePropertyName architecture -NotePropertyValue "x64" -Force
$smoke | Add-Member -NotePropertyName runtime_dependency_versions -NotePropertyValue ($runtimeDeps | ConvertFrom-Json) -Force
$smoke | Add-Member -NotePropertyName msix_sha256 -NotePropertyValue ((Get-FileHash -Algorithm SHA256 $msixPath).Hash.ToLowerInvariant()) -Force
$smoke | Add-Member -NotePropertyName packaged_file_count -NotePropertyValue ($packageManifest.Count) -Force
$smoke | Add-Member -NotePropertyName excluded_sensitive_path_checks -NotePropertyValue $privateAudit.status -Force
$smoke | Add-Member -NotePropertyName wack_result -NotePropertyValue @{ status = "not_run"; reason = "Run scripts/run-wack.ps1 to execute WACK when elevation is available."; output_root = $wackFolder } -Force
$smoke | ConvertTo-Json -Depth 8 | Set-Content -Path $smokePath -Encoding UTF8

$summary = @(
  "MSIX build: PASS",
  "MSIX path: $msixPath",
  "Package identity: $IdentityName",
  "Package version: $PackageVersion",
  "Package SHA-256: $((Get-FileHash -Algorithm SHA256 $msixPath).Hash.ToLowerInvariant())",
  "Private-data audit: $($privateAudit.status)",
  "WACK: not_run"
) -join "`r`n"
Set-Content -Path (Join-Path $evidenceRoot "test-summary.txt") -Value $summary -Encoding UTF8

if ($certificateCerPath) {
  Set-Content -Path (Join-Path $msixRoot "dev-certificate-path.txt") -Value $certificateCerPath -Encoding UTF8
}

Write-Host "MSIX built at $msixPath"
