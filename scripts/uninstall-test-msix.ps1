param(
  [string]$IdentityName = "TAHAIWebServices.MaineFamilyLawLLM"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$packages = Get-AppxPackage -Name $IdentityName -ErrorAction SilentlyContinue
foreach ($package in $packages) {
  Remove-AppxPackage -Package $package.PackageFullName
}
Write-Host "Removed installed package(s) for $IdentityName"
