param(
  [string]$BundleRoot = "",
  [string]$InstallRoot = "",
  [switch]$SkipLaunch
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $BundleRoot) {
  $BundleRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
}
if (-not $InstallRoot) {
  $InstallRoot = Join-Path $env:LOCALAPPDATA "Programs\MaineFamilyLawLLM"
}

$payloadRoot = Join-Path $BundleRoot "payload\maine-family-law-llm"
if (-not (Test-Path -LiteralPath $payloadRoot)) {
  throw "Installer payload not found at $payloadRoot"
}

New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
Write-Host "Copying application files to $InstallRoot"
$null = robocopy $payloadRoot $InstallRoot /E /NFL /NDL /NJH /NJS /NP
if ($LASTEXITCODE -ge 8) {
  throw "File copy failed with robocopy exit code $LASTEXITCODE"
}

$bootstrapScript = Join-Path $InstallRoot "scripts\bootstrap-windows-launcher.ps1"
& powershell -NoProfile -ExecutionPolicy Bypass -File $bootstrapScript -RepoRoot $InstallRoot -InstallOnly
if ($LASTEXITCODE -ne 0) {
  throw "Prerequisite/bootstrap install failed."
}

function New-Shortcut {
  param(
    [string]$ShortcutPath,
    [string]$TargetPath,
    [string]$Arguments = "",
    [string]$WorkingDirectory = ""
  )
  $shell = New-Object -ComObject WScript.Shell
  $shortcut = $shell.CreateShortcut($ShortcutPath)
  $shortcut.TargetPath = $TargetPath
  $shortcut.Arguments = $Arguments
  if ($WorkingDirectory) {
    $shortcut.WorkingDirectory = $WorkingDirectory
  }
  $shortcut.Save()
}

$startMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Maine Family Law LLM"
$desktopDir = [Environment]::GetFolderPath("Desktop")
New-Item -ItemType Directory -Force -Path $startMenuDir | Out-Null

$startCmd = Join-Path $InstallRoot "START_MAINE_FAMILY_LAW_LLM.cmd"
$guideHtml = Join-Path $InstallRoot "docs\README_FOR_NONTECHNICAL_USERS.html"
$repairCmd = Join-Path $InstallRoot "REPAIR_AND_REBUILD_INDEX.cmd"

New-Shortcut -ShortcutPath (Join-Path $desktopDir "Maine Family Law LLM.lnk") -TargetPath $startCmd -WorkingDirectory $InstallRoot
New-Shortcut -ShortcutPath (Join-Path $startMenuDir "Maine Family Law LLM.lnk") -TargetPath $startCmd -WorkingDirectory $InstallRoot
New-Shortcut -ShortcutPath (Join-Path $startMenuDir "Maine Family Law LLM - Nontechnical Guide.lnk") -TargetPath $guideHtml -WorkingDirectory $InstallRoot
New-Shortcut -ShortcutPath (Join-Path $startMenuDir "Maine Family Law LLM - Repair.lnk") -TargetPath $repairCmd -WorkingDirectory $InstallRoot

Write-Host "Installation complete."
Write-Host "App location: $InstallRoot"
Write-Host "Desktop shortcut: $desktopDir\Maine Family Law LLM.lnk"

if (-not $SkipLaunch) {
  & $startCmd
}
