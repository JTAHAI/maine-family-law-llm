param(
  [string]$RepoRoot = "",
  [string]$OutputRoot = "",
  [string]$PythonExe = "",
  [switch]$SkipDependencyInstall,
  [switch]$Offline,
  [switch]$SkipRuntimeSmoke,
  [switch]$DebugConsole,
  [ValidateSet("essential", "full")]
  [string]$FeatureTier = "essential"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "store-build-workspace.ps1")

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
  $normalizedRoot = [System.IO.Path]::GetFullPath($RuntimeRootPath).TrimEnd("\") + [System.IO.Path]::DirectorySeparatorChar
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

function Resolve-TesseractRoot {
  $candidates = @(
    "C:\Program Files\Tesseract-OCR",
    "C:\Program Files (x86)\Tesseract-OCR",
    (Join-Path ([Environment]::GetFolderPath("LocalApplicationData")) "Programs\Tesseract-OCR")
  )
  foreach ($candidate in $candidates) {
    if (Test-Path -LiteralPath (Join-Path $candidate "tesseract.exe")) {
      return $candidate
    }
  }
  throw "Bundled Tesseract source was not found on this build machine."
}

function Ensure-SpacyModel([string]$PythonPath) {
  & $PythonPath -c "import importlib.util as u, sys; sys.exit(0 if u.find_spec('en_core_web_lg') else 1)"
  if ($LASTEXITCODE -eq 0) {
    return
  }
  & $PythonPath -m spacy download en_core_web_lg
}

function Resolve-InstalledPackagePath([string]$PythonPath, [string]$PackageName, [string]$SubPath = "") {
  $script = @"
import pathlib
import sys
try:
    import $PackageName
except Exception:
    raise SystemExit(1)
root = pathlib.Path($PackageName.__file__).resolve().parent
target = root / r'$SubPath' if r'$SubPath' else root
print(target)
"@
  $resolved = (& $PythonPath -c $script).Trim()
  if (-not $resolved -or -not (Test-Path -LiteralPath $resolved)) {
    throw "Installed package path not found for $PackageName."
  }
  return $resolved
}

if (-not $RepoRoot) {
  $RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
}
if (-not $OutputRoot) {
  $OutputRoot = Join-Path $RepoRoot "dist\store"
}
$OutputRoot = Resolve-RepoBuildDirectory $OutputRoot $RepoRoot
$buildTemp = Resolve-RepoBuildDirectory (Join-Path $RepoRoot "dist\build-temp") $RepoRoot
Assert-SeparateBuildDirectories $OutputRoot $buildTemp
Assert-StoreBuildDiskSpace $OutputRoot $(if ($FeatureTier -eq "full") { 12GB } else { 6GB })
$null = Initialize-RepoBuildEnvironment $RepoRoot

$basePython = Resolve-Python $PythonExe
# New dependencies stay under ignored dist, never in the shipped source/payload.
# Offline builds may consume an existing external environment read-only.
$venvRoot = Resolve-RepoBuildDirectory (Join-Path $RepoRoot "dist\build-env\store") $RepoRoot
Assert-SeparateBuildDirectories $OutputRoot $venvRoot
$legacyVenvRoot = Join-Path ([Environment]::GetFolderPath("LocalApplicationData")) "MaineFamilyLawLLM\build-venvs\store"
if ($Offline -and -not (Test-Path -LiteralPath (Join-Path $venvRoot "Scripts\python.exe"))) {
  $venvRoot = $legacyVenvRoot
}
$venvPython = Join-Path $venvRoot "Scripts\python.exe"
$requirementsPath = Join-Path $RepoRoot "store\pyinstaller\requirements-store-build.txt"
$specPath = Join-Path $RepoRoot "store\pyinstaller\maine_family_law_llm.spec"
$pyiDistRoot = Join-Path $OutputRoot "pyinstaller"
$pyiWorkRoot = Join-Path $OutputRoot "build"
$runtimeRoot = Join-Path $OutputRoot "runtime"

Stop-StoreRuntimeProcesses $runtimeRoot

if (-not (Test-Path -LiteralPath $venvPython)) {
  if ($Offline) { throw "Offline build requires an existing provisioned Store build environment." }
  if ($basePython -eq "py") {
    & py -3.11 -m venv $venvRoot
  } else {
    & $basePython -m venv $venvRoot
  }
}

if (-not $SkipDependencyInstall -and -not $Offline) {
  & $venvPython -m pip install --upgrade pip
  & $venvPython -m pip install -r $requirementsPath
  if ($FeatureTier -eq "full") {
    Ensure-SpacyModel $venvPython
  }
}

if ($Offline) {
  & $venvPython -B -m pip check
  if ($LASTEXITCODE -ne 0) { throw "Offline build dependencies are inconsistent; provision them separately before building." }
  if ($FeatureTier -eq "full") {
    & $venvPython -B -c "import importlib.util as u, sys; sys.exit(0 if u.find_spec('en_core_web_lg') else 1)"
    if ($LASTEXITCODE -ne 0) { throw "Offline full build requires the cached spaCy model; no download was attempted." }
  }
}

foreach ($path in @($pyiDistRoot, $pyiWorkRoot, $runtimeRoot)) {
  $path = Resolve-RepoBuildDirectory $path $RepoRoot
  if (Test-Path -LiteralPath $path) {
    Remove-Item -LiteralPath $path -Recurse -Force
  }
}
New-Item -ItemType Directory -Force -Path $pyiDistRoot, $pyiWorkRoot | Out-Null

$pyInstallerEnv = @{
  MFL_STORE_DEBUG_CONSOLE = $(if ($DebugConsole) { "1" } else { "0" })
  MFL_STORE_FEATURE_TIER = $FeatureTier
}
foreach ($pair in $pyInstallerEnv.GetEnumerator()) {
  [System.Environment]::SetEnvironmentVariable($pair.Key, $pair.Value, "Process")
}
& $venvPython -B -m PyInstaller --noconfirm --clean --distpath $pyiDistRoot --workpath $pyiWorkRoot $specPath
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed; this runtime must not be packaged." }

$collectedRoot = Join-Path $pyiDistRoot "MaineFamilyLawLLM"
if (-not (Test-Path -LiteralPath $collectedRoot)) {
  throw "PyInstaller did not produce the expected runtime folder at $collectedRoot"
}
$collectedRoot = Resolve-RepoBuildDirectory $collectedRoot $RepoRoot
# Both paths are validated children of the same repository. Rename the collected
# runtime instead of retaining a second multi-gigabyte copy of identical bytes.
Move-Item -LiteralPath $collectedRoot -Destination $runtimeRoot

$tesseractSourceRoot = Resolve-TesseractRoot
$tesseractRuntimeRoot = Join-Path $runtimeRoot "store\tesseract"
New-Item -ItemType Directory -Force -Path $tesseractRuntimeRoot | Out-Null
Copy-Item -Path (Join-Path $tesseractSourceRoot "*") -Destination $tesseractRuntimeRoot -Recurse -Force

# Native transcription is part of the essential offline product. Provisioning
# happens only in repository dist (old offline caches are read-only), verifies hashes,
# and copies the admitted CPU runtime/model into the frozen payload. The app
# itself never downloads an engine or model.
$whisperRuntimeRoot = Join-Path $runtimeRoot "store\whisper"
& (Join-Path $PSScriptRoot "provision-whisper-engine.ps1") -Destination $whisperRuntimeRoot -Offline:$Offline
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $whisperRuntimeRoot "whisper-cli.exe"))) {
  throw "Pinned whisper.cpp runtime provisioning failed."
}

if ($FeatureTier -eq "full") {
  $doclingModelsSourceRoot = Resolve-RepoBuildDirectory (Join-Path $RepoRoot "dist\build-cache\docling-models") $RepoRoot
  if ($Offline -and -not (Test-Path -LiteralPath $doclingModelsSourceRoot)) {
    $doclingModelsSourceRoot = Join-Path ([Environment]::GetFolderPath("LocalApplicationData")) "MaineFamilyLawLLM\build-cache\docling-models"
  }
  $requiredDoclingModels = @(
    (Join-Path $doclingModelsSourceRoot "docling-project--docling-layout-heron"),
    (Join-Path $doclingModelsSourceRoot "docling-project--docling-models"),
    (Join-Path $doclingModelsSourceRoot "RapidOcr")
  )
  $missingDoclingModels = @($requiredDoclingModels | Where-Object { -not (Test-Path -LiteralPath $_) })
  if ($missingDoclingModels.Count -gt 0) {
    if ($Offline) { throw "Offline full build requires cached Docling models; no download was attempted." }
    New-Item -ItemType Directory -Force -Path $doclingModelsSourceRoot | Out-Null
    & $venvPython -B -c "from pathlib import Path; import sys; from docling.utils.model_downloader import download_models; download_models(output_dir=Path(sys.argv[1]), progress=False, with_layout=True, with_tableformer=True, with_code_formula=False, with_picture_classifier=False, with_rapidocr=True)" $doclingModelsSourceRoot
    if ($LASTEXITCODE -ne 0) { throw "Docling offline model download failed." }
  }
  foreach ($requiredModel in $requiredDoclingModels) {
    if (-not (Test-Path -LiteralPath $requiredModel)) {
      throw "Required Docling offline model artifact is missing: $requiredModel"
    }
  }
  $doclingModelsRuntimeRoot = Join-Path $runtimeRoot "store\docling\models"
  New-Item -ItemType Directory -Force -Path $doclingModelsRuntimeRoot | Out-Null
  Copy-Item -Path (Join-Path $doclingModelsSourceRoot "*") -Destination $doclingModelsRuntimeRoot -Recurse -Force
}

$runtimeExe = Join-Path $runtimeRoot "MaineFamilyLawLLM.exe"
if (-not (Test-Path -LiteralPath $runtimeExe)) {
  throw "Frozen runtime executable missing at $runtimeExe"
}

# A successful PyInstaller collection is not enough: dynamic imports can be
# omitted while the binary still exists. Exercise the frozen runtime before a
# later MSIX step can seal an unusable payload.
if (-not $SkipRuntimeSmoke) {
  $smokeScript = Join-Path $PSScriptRoot "test-store-runtime.ps1"
  $evidenceRoot = Join-Path $OutputRoot "evidence"
  & powershell -NoProfile -ExecutionPolicy Bypass -File $smokeScript -RepoRoot $RepoRoot -RuntimeRoot $runtimeRoot -EvidenceRoot $evidenceRoot
  if ($LASTEXITCODE -ne 0) {
    throw "Frozen Store runtime smoke failed. Do not package this build; inspect $evidenceRoot."
  }
}

Write-Host "Store runtime built at $runtimeRoot"
Write-Host "Executable: $runtimeExe"
Write-Host "Feature tier: $FeatureTier"
