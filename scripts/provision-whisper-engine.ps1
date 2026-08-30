param(
  [string]$Destination = "",
  [switch]$Offline
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "store-build-workspace.ps1")
$repo = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))

$version = "1.9.2"
$archiveUrl = "https://github.com/ggml-org/whisper.cpp/releases/download/v1.9.2/whisper-bin-x64.zip"
$modelUrl = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.en-q5_1.bin"
$archiveSha256 = "49dcc16de826f20bd53d44f947a1ae49dfa81f86cad67a64d80820cb192d674a"
$cliSha256 = "95e3c0b0e778ad9499eb0125f97c1dcf437dd9eb4ea77050b043574f93c2631d"
$modelSha256 = "c77c5766f1cef09b6b7d47f21b546cbddd4157886b3b5d6d4f709e91e66c7c2b"
$cacheRoot = Resolve-RepoBuildDirectory (Join-Path $repo "dist\build-cache\whisper-cpp\v$version") $repo
$legacyCacheRoot = Join-Path ([Environment]::GetFolderPath("LocalApplicationData")) "MaineFamilyLawLLM\build-cache\whisper-cpp\v$version"
$archive = Join-Path $cacheRoot "whisper-bin-x64.zip"
$model = Join-Path $cacheRoot "ggml-tiny.en-q5_1.bin"
$expanded = Join-Path $cacheRoot "bin"
if (-not $Destination) { $Destination = Join-Path $cacheRoot "runtime" }
$Destination = Resolve-RepoBuildDirectory $Destination $repo
if ($Offline) {
  if (-not (Test-Path -LiteralPath $archive)) { $archive = Join-Path $legacyCacheRoot "whisper-bin-x64.zip" }
  if (-not (Test-Path -LiteralPath $model)) { $model = Join-Path $legacyCacheRoot "ggml-tiny.en-q5_1.bin" }
}

function Assert-Hash([string]$Path, [string]$Expected, [string]$Label) {
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "$Label is missing: $Path" }
  # Get-FileHash is unavailable in a few minimal Windows PowerShell hosts.
  # Use the BCL directly so the pinned-engine admission check works in the
  # same non-interactive host used by the packaging pipeline.
  $stream = [System.IO.File]::OpenRead($Path)
  try {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
      $actual = ([System.BitConverter]::ToString($sha.ComputeHash($stream))).Replace("-", "").ToLowerInvariant()
    } finally {
      $sha.Dispose()
    }
  } finally {
    $stream.Dispose()
  }
  if ($actual -ne $Expected) { throw "$Label SHA-256 mismatch: $actual" }
}

New-Item -ItemType Directory -Force -Path $cacheRoot | Out-Null
if (-not (Test-Path -LiteralPath $archive)) {
  if ($Offline) { throw "Pinned whisper.cpp archive is absent from the external build cache." }
  Invoke-WebRequest -Uri $archiveUrl -OutFile $archive
}
if (-not (Test-Path -LiteralPath $model)) {
  if ($Offline) { throw "Pinned whisper.cpp model is absent from the external build cache." }
  Invoke-WebRequest -Uri $modelUrl -OutFile $model
}
Assert-Hash $archive $archiveSha256 "whisper.cpp release archive"
Assert-Hash $model $modelSha256 "whisper.cpp model"

New-Item -ItemType Directory -Force -Path $expanded | Out-Null
Expand-Archive -LiteralPath $archive -DestinationPath $expanded -Force
$releaseRoot = Join-Path $expanded "Release"
$cli = Join-Path $releaseRoot "whisper-cli.exe"
Assert-Hash $cli $cliSha256 "whisper.cpp CLI"

if (-not $Destination) { $Destination = Join-Path $cacheRoot "runtime" }
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
Copy-Item -LiteralPath $cli -Destination (Join-Path $Destination "whisper-cli.exe") -Force
Get-ChildItem -LiteralPath $releaseRoot -Filter "*.dll" -File | ForEach-Object {
  Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $Destination $_.Name) -Force
}
Copy-Item -LiteralPath $model -Destination (Join-Path $Destination "ggml-tiny.en-q5_1.bin") -Force
$licenseSource = Join-Path ([System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))) "licenses\whisper.cpp-MIT.md"
if (Test-Path -LiteralPath $licenseSource) {
  Copy-Item -LiteralPath $licenseSource -Destination (Join-Path $Destination "LICENSE-whisper.cpp.txt") -Force
}

$manifest = [ordered]@{
  schema_version = "whisper_cpp_bundle_v1"
  version = $version
  architecture = "x64"
  runtime_downloads = $false
  executable = "whisper-cli.exe"
  executable_sha256 = $cliSha256
  model = "ggml-tiny.en-q5_1.bin"
  model_sha256 = $modelSha256
  upstream = "https://github.com/ggml-org/whisper.cpp"
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Destination "engine-manifest.json") -Encoding UTF8
Write-Output ([System.IO.Path]::GetFullPath($Destination))
