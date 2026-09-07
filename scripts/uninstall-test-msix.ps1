param(
  [string]$PackageFullName = "",
  [switch]$IsolatedTestEnvironment
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $IsolatedTestEnvironment -or -not $PackageFullName -or $PackageFullName -match '[*?\[\]]') {
  throw "Uninstall requires -IsolatedTestEnvironment and one exact -PackageFullName from the QA installation receipt. No default production identity is allowed."
}
$packages = @(Get-AppxPackage | Where-Object { $_.PackageFullName -ceq $PackageFullName })
if ($packages.Count -ne 1) { throw "Expected exactly one installed QA package matching the receipt." }
foreach ($package in $packages) {
  Remove-AppxPackage -Package $package.PackageFullName
}
Write-Host "Removed the isolated QA package $PackageFullName"
