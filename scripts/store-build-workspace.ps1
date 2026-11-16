# Shared containment for generated Store build state. No deletion is performed here.
function Resolve-RepoBuildDirectory([string]$PathText, [string]$RepoRootPath) {
  if (-not $PathText) { throw "Build directory is required." }
  $sep = [System.IO.Path]::DirectorySeparatorChar
  $comparison = if ($sep -eq '\') { [StringComparison]::OrdinalIgnoreCase } else { [StringComparison]::Ordinal }
  $repo = [System.IO.Path]::GetFullPath($RepoRootPath).TrimEnd($sep)
  $dist = Join-Path $repo 'dist'
  $full = [System.IO.Path]::GetFullPath($PathText).TrimEnd($sep)
  if (-not $full.StartsWith($dist + $sep, $comparison)) {
    throw "Build directories must be dedicated children of repository dist; no external drive folders."
  }
  $cursor = $full
  while ($cursor) {
    if (Test-Path -LiteralPath $cursor) {
      $item = Get-Item -LiteralPath $cursor -Force
      if (-not $item.PSIsContainer -or ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
        throw "Build paths must not traverse files, junctions or symbolic links."
      }
    }
    if ($cursor.Equals($repo, $comparison)) { break }
    $cursor = [System.IO.Path]::GetDirectoryName($cursor)
  }
  return $full
}

function Assert-SeparateBuildDirectories([string]$First, [string]$Second) {
  $sep = [System.IO.Path]::DirectorySeparatorChar
  $comparison = if ($sep -eq '\') { [StringComparison]::OrdinalIgnoreCase } else { [StringComparison]::Ordinal }
  $a = $First.TrimEnd($sep) + $sep
  $b = $Second.TrimEnd($sep) + $sep
  if ($a.StartsWith($b, $comparison) -or $b.StartsWith($a, $comparison)) {
    throw "Build output, staging and temporary directories must not overlap."
  }
}

function Initialize-RepoBuildEnvironment([string]$RepoRootPath) {
  $tempRoot = Resolve-RepoBuildDirectory (Join-Path $RepoRootPath 'dist\build-temp') $RepoRootPath
  New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
  $env:TEMP = $tempRoot
  $env:TMP = $tempRoot
  $env:PYTHONDONTWRITEBYTECODE = '1'
  $env:PYTHONPYCACHEPREFIX = Join-Path $tempRoot 'pycache-disabled'
  $env:PYINSTALLER_CONFIG_DIR = Join-Path $tempRoot 'pyinstaller'
  $env:PIP_CACHE_DIR = Join-Path $tempRoot 'pip-cache'
  $env:HF_HOME = Join-Path $tempRoot 'huggingface'
  $env:TORCH_HOME = Join-Path $tempRoot 'torch'
  return $tempRoot
}

function Assert-StoreBuildDiskSpace([string]$PathText, [long]$MinimumBytes) {
  $drive = New-Object System.IO.DriveInfo([System.IO.Path]::GetPathRoot($PathText))
  if ($drive.AvailableFreeSpace -lt $MinimumBytes) {
    throw "Insufficient free space for bounded Store build; existing artifacts preserved."
  }
}
