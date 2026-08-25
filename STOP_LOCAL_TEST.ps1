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
$pidValue = 0
if ($pidText -and [int]::TryParse($pidText, [ref]$pidValue) -and $pidValue -gt 0) {
  $proc = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
  if ($null -ne $proc) {
    # A stale or tampered PID file must never terminate an unrelated process.
    # The local test launcher always starts Uvicorn with one of these app targets.
    $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $pidValue" -ErrorAction SilentlyContinue
    $commandLine = if ($null -ne $processInfo) { [string]$processInfo.CommandLine } else { "" }
    $isLocalApi = $commandLine -match "(?i)uvicorn" -and (
      $commandLine -match "(?i)maine_family_law_llm\.api:app" -or
      $commandLine -match "(?i)app\.api\.main:app"
    )
    if ($isLocalApi) {
      Stop-Process -Id $proc.Id -Force
      Write-Output "stopped_local_api_pid=$pidValue"
    } else {
      Write-Warning "refused_to_stop_unverified_pid=$pidValue; inspect the process manually and remove the stale PID file."
    }
  } else {
    Write-Output "pid_not_running=$pidValue"
  }
} elseif ($pidText) {
  Write-Warning "invalid_pid_file_contents; removing stale PID file."
}
Remove-Item -LiteralPath $pidPath -Force
Write-Output "removed_pid_file=$pidPath"
