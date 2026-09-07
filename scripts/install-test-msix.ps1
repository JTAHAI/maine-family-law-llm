param(
  [string]$RepoRoot = "",
  [string]$PackagePath = "",
  [string]$CertificatePath = "",
  [switch]$IsolatedTestEnvironment
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if (-not $IsolatedTestEnvironment) { throw "Installation qualification requires an explicitly isolated Windows user, Sandbox, or disposable VM. The real Store installation must not be changed." }

function Test-IsAdministrator {
  $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
  return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not $RepoRoot) {
  $RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
}
if (-not $PackagePath) {
  throw "An explicit exact candidate -PackagePath is required; no historical package is selected automatically."
}
if (-not (Test-Path -LiteralPath $PackagePath -PathType Leaf)) {
  throw "The exact candidate package does not exist."
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
