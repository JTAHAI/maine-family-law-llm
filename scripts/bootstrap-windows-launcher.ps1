param(
  [string]$RepoRoot = "",
  [string]$VenvRoot = "",
  [switch]$InstallOnly,
  [switch]$VerifyOnly,
  [switch]$Repair,
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$LauncherArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
  param([string]$ExplicitRepoRoot)
  if ($ExplicitRepoRoot) {
    $cleanRoot = $ExplicitRepoRoot.Trim()
    $cleanRoot = $cleanRoot.Trim([char[]]@([char]34, [char]39))
    $cleanRoot = [Environment]::ExpandEnvironmentVariables($cleanRoot)
    if ($cleanRoot.IndexOf([char]0) -ge 0 -or $cleanRoot.Contains("`r") -or $cleanRoot.Contains("`n")) {
      throw "The repository path contains unsupported control characters."
    }
    if (-not $cleanRoot) {
      throw "The repository path is empty after normalization."
    }
    return [System.IO.Path]::GetFullPath($cleanRoot)
  }
  return [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
}

function Get-RepoFingerprint {
  param([string]$Value)
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($Value)
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    $hash = $sha.ComputeHash($bytes)
  } finally {
    $sha.Dispose()
  }
  $hex = [System.BitConverter]::ToString($hash).Replace("-", "").ToLowerInvariant()
  return $hex.Substring(0, 12)
}

function Test-PythonCandidate {
  param(
    [string]$Command,
    [string[]]$PrefixArgs = @()
  )
  try {
    $json = & $Command @($PrefixArgs + @("-c", "import json,sys; print(json.dumps({'major':sys.version_info[0],'minor':sys.version_info[1],'micro':sys.version_info[2],'executable':sys.executable}))")) 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $json) {
      return $null
    }
    $version = ($json | Select-Object -First 1 | ConvertFrom-Json)
    if ($version.major -eq 3 -and $version.minor -ge 11) {
      return @{
        Command = $Command
        PrefixArgs = $PrefixArgs
        Executable = [string]$version.executable
        Version = "$($version.major).$($version.minor).$($version.micro)"
      }
    }
  } catch {
    return $null
  }
  return $null
}

function Get-PythonInterpreter {
  $candidates = @(
    @{ Command = "py"; PrefixArgs = @("-3.13") },
    @{ Command = "py"; PrefixArgs = @("-3.12") },
    @{ Command = "py"; PrefixArgs = @("-3.11") },
    @{ Command = "py"; PrefixArgs = @("-3") },
    @{ Command = "python"; PrefixArgs = @() }
  )
  foreach ($candidate in $candidates) {
    $result = Test-PythonCandidate -Command $candidate.Command -PrefixArgs $candidate.PrefixArgs
    if ($null -ne $result) {
      return $result
    }
  }
  $commonPaths = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"),
    (Join-Path $env:ProgramFiles "Python313\python.exe"),
    (Join-Path $env:ProgramFiles "Python312\python.exe"),
    (Join-Path $env:ProgramFiles "Python311\python.exe")
  )
  foreach ($path in $commonPaths) {
    if (Test-Path -LiteralPath $path) {
      $result = Test-PythonCandidate -Command $path
      if ($null -ne $result) {
        return $result
      }
    }
  }
  return $null
}

function Ensure-PythonInterpreter {
  $python = Get-PythonInterpreter
  if ($null -ne $python) {
    return $python
  }
  $winget = Get-Command winget -ErrorAction SilentlyContinue
  if ($null -eq $winget) {
    throw "Python 3.11 or newer was not found, and winget is not available to install it automatically. Install Python 3.11+ from python.org, then run the launcher again."
  }
  Write-Host "Python 3.11+ was not found. Installing it now for the current Windows user..."
  & $winget.Source install --id Python.Python.3.11 --scope user --accept-package-agreements --accept-source-agreements --silent --disable-interactivity
  if ($LASTEXITCODE -ne 0) {
    throw "Automatic Python installation failed. Install Python 3.11+ and then run the launcher again."
  }
  $python = Get-PythonInterpreter
  if ($null -eq $python) {
    throw "Python was installed, but this session could not find it yet. Close this window, reopen the launcher, and try again."
  }
  return $python
}

function Invoke-PythonCommand {
  param(
    [hashtable]$Python,
    [string[]]$CommandArgs
  )
  $allArgs = @()
  if ($Python.PrefixArgs) {
    $allArgs += $Python.PrefixArgs
  }
  $allArgs += $CommandArgs
  & $Python.Command @allArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Python command failed: $($Python.Command) $($allArgs -join ' ')"
  }
}

function Test-InstalledImports {
  param([string]$PythonPath)
  & $PythonPath -c "import app.launcher, maine_family_law_llm.case_corpus_builder; print('INSTALLATION_OK')" 2>$null
  return $LASTEXITCODE -eq 0
}

$resolvedRepoRoot = Get-RepoRoot -ExplicitRepoRoot $RepoRoot
$pyprojectPath = Join-Path $resolvedRepoRoot "pyproject.toml"
if (-not (Test-Path -LiteralPath $pyprojectPath)) {
  throw "pyproject.toml was not found under $resolvedRepoRoot"
}
$repoFingerprint = Get-RepoFingerprint -Value $resolvedRepoRoot
if (-not $VenvRoot) {
  $VenvRoot = Join-Path $env:LOCALAPPDATA "MaineFamilyLawLLM\venvs\$repoFingerprint"
}
$statePath = Join-Path $VenvRoot "bootstrap-state.json"
$venvPython = Join-Path $VenvRoot "Scripts\python.exe"
$pyprojectHash = (Get-FileHash -Algorithm SHA256 -Path $pyprojectPath).Hash.ToLowerInvariant()

$python = Ensure-PythonInterpreter
$needsInstall = $Repair -or -not (Test-Path -LiteralPath $venvPython)

if (-not $needsInstall -and (Test-Path -LiteralPath $statePath)) {
  try {
    $state = Get-Content -Path $statePath -Raw | ConvertFrom-Json
    if ($state.repo_root -ne $resolvedRepoRoot -or $state.pyproject_sha256 -ne $pyprojectHash) {
      $needsInstall = $true
    }
  } catch {
    $needsInstall = $true
  }
} elseif (-not $needsInstall) {
  $needsInstall = $true
}

if (-not $needsInstall) {
  $needsInstall = -not (Test-InstalledImports -PythonPath $venvPython)
}

if ($needsInstall) {
  New-Item -ItemType Directory -Force -Path $VenvRoot | Out-Null
  if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "Creating local runtime environment at $VenvRoot"
    Invoke-PythonCommand -Python $python -CommandArgs @("-m", "venv", $VenvRoot)
    if (-not (Test-Path -LiteralPath $venvPython)) {
      throw "Virtual environment creation did not produce $venvPython"
    }
  }
  Write-Host "Installing or updating required packages for the launcher and local workbench..."
  & $venvPython -m pip install --upgrade pip
  if ($LASTEXITCODE -ne 0) {
    throw "pip upgrade failed."
  }
  & $venvPython -m pip install -e "$resolvedRepoRoot[api]"
  if ($LASTEXITCODE -ne 0) {
    throw "Package installation failed."
  }
  $state = @{
    repo_root = $resolvedRepoRoot
    pyproject_sha256 = $pyprojectHash
    python_version = $python.Version
  }
  $state | ConvertTo-Json | Set-Content -Path $statePath -Encoding UTF8
}

if ($VerifyOnly) {
  if (Test-InstalledImports -PythonPath $venvPython) {
    Write-Host "INSTALLATION_OK"
    exit 0
  }
  Write-Host "INSTALLATION_IMPORT_FAILED"
  exit 1
}

if ($Repair) {
  & $venvPython -m maine_family_law_llm.case_corpus_builder --bootstrap --repo-root $resolvedRepoRoot
  if ($LASTEXITCODE -ne 0) {
    throw "Repository bootstrap repair failed."
  }
  Write-Host "Repository launchers, docs, and sample assets were refreshed."
  if ($InstallOnly) {
    exit 0
  }
}

if ($InstallOnly) {
  Write-Host "Installation complete. Launch START_MAINE_FAMILY_LAW_LLM.cmd when you are ready."
  exit 0
}

Write-Host "Starting Maine Family Law LLM..."
& $venvPython (Join-Path $resolvedRepoRoot "app\launcher.py") @LauncherArgs
exit $LASTEXITCODE
