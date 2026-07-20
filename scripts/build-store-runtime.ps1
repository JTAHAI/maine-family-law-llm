param(
  [string]$RepoRoot = "",
  [string]$OutputRoot = "",
  [string]$PythonExe = "",
  [switch]$SkipDependencyInstall,
  [switch]$DebugConsole
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-Python([string]$Preferred) {
  if ($Preferred -and (Get-Command $Preferred -ErrorAction SilentlyContinue)) {
    return (Get-Command $Preferred).Source
  }
  if (Get-Command py -ErrorAction SilentlyContinue) {
    return "py"
  }
  if (Get-Command python -ErrorAction SilentlyContinue) {
    return (Get-Command python).Source
  }
  throw "No Python interpreter was found for the Store build."
}

function Stop-StoreRuntimeProcesses([string]$RuntimeRootPath) {
  if (-not (Test-Path -LiteralPath $RuntimeRootPath)) {
    return
  }
  $normalizedRoot = [System.IO.Path]::GetFullPath($RuntimeRootPath).TrimEnd("\")
  $running = Get-Process -ErrorAction SilentlyContinue | Where-Object {
    try {
      $_.Path -and ([System.IO.Path]::GetFullPath($_.Path)).StartsWith($normalizedRoot, [System.StringComparison]::OrdinalIgnoreCase)
    } catch {
      $false
    }
  }
  foreach ($process in $running) {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
  }
}

if (-not $RepoRoot) {
  $RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
}
if (-not $OutputRoot) {
  $OutputRoot = Join-Path $RepoRoot "dist\store"
}

$basePython = Resolve-Python $PythonExe
# Build dependencies are mutable runtime state and must never be created in a
# source release.  Keeping this venv under LocalAppData lets the repository's
# strict privacy/source-hygiene audits continue to pass after a Store build.
$venvRoot = Join-Path ([Environment]::GetFolderPath("LocalApplicationData")) "MaineFamilyLawLLM\build-venvs\store"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"
$requirementsPath = Join-Path $RepoRoot "store\pyinstaller\requirements-store-build.txt"
$specPath = Join-Path $RepoRoot "store\pyinstaller\maine_family_law_llm.spec"
$pyiDistRoot = Join-Path $OutputRoot "pyinstaller"
$pyiWorkRoot = Join-Path $OutputRoot "build"
$runtimeRoot = Join-Path $OutputRoot "runtime"

Stop-StoreRuntimeProcesses $runtimeRoot

if (-not (Test-Path -LiteralPath $venvPython)) {
  if ($basePython -eq "py") {
    & py -3.11 -m venv $venvRoot
  } else {
    & $basePython -m venv $venvRoot
  }
}

if (-not $SkipDependencyInstall) {
  & $venvPython -m pip install --upgrade pip
  & $venvPython -m pip install -r $requirementsPath
}

foreach ($path in @($pyiDistRoot, $pyiWorkRoot, $runtimeRoot)) {
  if (Test-Path -LiteralPath $path) {
    Remove-Item -LiteralPath $path -Recurse -Force
  }
}
New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null

$pyInstallerEnv = @{ MFL_STORE_DEBUG_CONSOLE = $(if ($DebugConsole) { "1" } else { "0" }) }
foreach ($pair in $pyInstallerEnv.GetEnumerator()) {
  [System.Environment]::SetEnvironmentVariable($pair.Key, $pair.Value, "Process")
}
& $venvPython -m PyInstaller --noconfirm --clean --distpath $pyiDistRoot --workpath $pyiWorkRoot $specPath

$collectedRoot = Join-Path $pyiDistRoot "MaineFamilyLawLLM"
if (-not (Test-Path -LiteralPath $collectedRoot)) {
  throw "PyInstaller did not produce the expected runtime folder at $collectedRoot"
}
Copy-Item -Path (Join-Path $collectedRoot "*") -Destination $runtimeRoot -Recurse -Force

$runtimeExe = Join-Path $runtimeRoot "MaineFamilyLawLLM.exe"
if (-not (Test-Path -LiteralPath $runtimeExe)) {
  throw "Frozen runtime executable missing at $runtimeExe"
}

Write-Host "Store runtime built at $runtimeRoot"
Write-Host "Executable: $runtimeExe"
