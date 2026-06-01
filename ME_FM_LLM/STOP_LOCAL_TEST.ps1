param(
  [string]$RepoRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repo = [System.IO.Path]::GetFullPath($RepoRoot)
$pidPath = Join-Path -Path $repo -ChildPath ".local_server.pid"
if (-not (Test-Path -LiteralPath $pidPath)) {
  Write-Output "no_local_server_pid_file"
  exit 0
}
$pidText = (Get-Content -LiteralPath $pidPath -Raw).Trim()
if ($pidText) {
  $proc = Get-Process -Id ([int]$pidText) -ErrorAction SilentlyContinue
  if ($null -ne $proc) {
    Stop-Process -Id $proc.Id -Force
    Write-Output "stopped_pid=$pidText"
  } else {
    Write-Output "pid_not_running=$pidText"
  }
}
Remove-Item -LiteralPath $pidPath -Force
Write-Output "removed_pid_file=$pidPath"
