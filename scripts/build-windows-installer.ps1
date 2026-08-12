param(
  [string]$RepoRoot = "",
  [string]$OutputRoot = "",
  [switch]$SkipZip
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $RepoRoot) {
  $RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
}
if (-not $OutputRoot) {
  $OutputRoot = Join-Path $RepoRoot "dist\windows_installer"
}

$stageRoot = Join-Path $OutputRoot "MaineFamilyLawLLM_Installer"
$payloadRoot = Join-Path $stageRoot "payload\maine-family-law-llm"
$zipPath = Join-Path $OutputRoot "MaineFamilyLawLLM_Installer.zip"

if (Test-Path -LiteralPath $stageRoot) {
  Remove-Item -LiteralPath $stageRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $payloadRoot | Out-Null
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null

$excludedDirs = @(
  ".git",
  ".venv",
  "venv",
  "env",
  "dist",
  "build",
  "node_modules",
  "__pycache__",
  ".pytest_cache",
  ".ruff_cache",
  ".mypy_cache",
  ".idea",
  ".vscode"
)
$excludedFiles = @(
  "*.pyc",
  "*.pyo",
  "*.db",
  "*.sqlite",
  "*.sqlite3",
  "*.log",
  "*.tmp",
  "*.bak",
  "*.gguf",
  "*.safetensors"
)

$robocopyArgs = @($RepoRoot, $payloadRoot, "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/NP")
foreach ($dir in $excludedDirs) {
  $robocopyArgs += @("/XD", (Join-Path $RepoRoot $dir))
}
foreach ($pattern in $excludedFiles) {
  $robocopyArgs += @("/XF", $pattern)
}
$null = & robocopy @robocopyArgs
if ($LASTEXITCODE -ge 8) {
  throw "Installer payload copy failed with robocopy exit code $LASTEXITCODE"
}

$installerRoot = Join-Path $RepoRoot "installer"
Copy-Item -Path $installerRoot -Destination $stageRoot -Recurse -Force

$installLauncher = @(
  "@echo off",
  "setlocal",
  "cd /d %~dp0",
  "powershell -NoProfile -ExecutionPolicy Bypass -File ""%~dp0installer\install.ps1"" -BundleRoot ""%~dp0"""
) -join "`r`n"
Set-Content -Path (Join-Path $stageRoot "INSTALL_MAINE_FAMILY_LAW_LLM.cmd") -Encoding ASCII -Value $installLauncher

$installerReadme = @(
  "Maine Family Law LLM Windows Installer Package",
  "",
  "1. Extract this ZIP.",
  "2. Double-click INSTALL_MAINE_FAMILY_LAW_LLM.cmd.",
  "3. The installer copies the app into %LOCALAPPDATA%\Programs\MaineFamilyLawLLM, installs missing prerequisites, and creates a desktop shortcut.",
  "4. If you already have a completed case build, you can skip the import wizard and choose Open Existing Case Corpus from the launcher."
) -join "`r`n"
Set-Content -Path (Join-Path $stageRoot "README_INSTALLER_FIRST.txt") -Encoding UTF8 -Value $installerReadme

if (-not $SkipZip) {
  if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
  }
  Compress-Archive -Path (Join-Path $stageRoot "*") -DestinationPath $zipPath -CompressionLevel Optimal
}

Write-Host "Windows installer package ready at $stageRoot"
if (-not $SkipZip) {
  Write-Host "Zip artifact: $zipPath"
}

# Robocopy uses successful non-zero exit codes (for example, 1 means files
# were copied). Do not leak that status as the PowerShell process exit code.
exit 0
