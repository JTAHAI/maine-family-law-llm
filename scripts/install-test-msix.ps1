param(
  [string]$RepoRoot = "",
  [string]$PackagePath = "",
  [string]$CertificatePath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-IsAdministrator {
  $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
  return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not $RepoRoot) {
  $RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
}
if (-not $PackagePath) {
  $PackagePath = Join-Path $RepoRoot "dist\release\v7.0.0\msix\MaineFamilyLawLLM_7.0.0.0_x64.msix"
}
if (-not $CertificatePath) {
  $certHint = Join-Path $RepoRoot "dist\store\msix\dev-certificate-path.txt"
  if (Test-Path -LiteralPath $certHint) {
    $CertificatePath = (Get-Content -Path $certHint -Raw).Trim()
  }
}

if ($CertificatePath -and (Test-Path -LiteralPath $CertificatePath)) {
  $certificate = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new($CertificatePath)
  $storeEntries = if (Test-IsAdministrator) {
    @(
      @{ Name = "TrustedPeople"; Location = "LocalMachine" }
    )
  } else {
    @(
      @{ Name = "TrustedPeople"; Location = "CurrentUser" },
      @{ Name = "Root"; Location = "CurrentUser" }
    )
  }
  foreach ($storeEntry in $storeEntries) {
    $store = [System.Security.Cryptography.X509Certificates.X509Store]::new($storeEntry.Name, $storeEntry.Location)
    try {
      $store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
      $store.Add($certificate)
    } finally {
      $store.Close()
    }
  }
}
Add-AppxPackage -Path $PackagePath -ForceApplicationShutdown
Write-Host "Installed MSIX from $PackagePath"
