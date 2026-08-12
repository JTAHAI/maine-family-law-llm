param(
  [string]$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path,
  [ValidateRange(1, 65535)]
  [int]$Port = 8000,
  [switch]$SkipTests,
  [switch]$SkipDoctor,
  [string]$PythonExe = "",
  [ValidateSet("LocalWorkbench", "Enterprise")]
  [string]$ApiMode = "LocalWorkbench",
  [ValidateRange(5, 120)]
  [int]$StartupTimeoutSeconds = 30
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repo = [System.IO.Path]::GetFullPath($RepoRoot)
$python = if ($PythonExe) { $PythonExe } else { (Get-Command python).Source }
if (-not (Test-Path -LiteralPath $python)) {
  throw "python_not_found:$python"
}
Set-Location -LiteralPath $repo
$env:PYTHONDONTWRITEBYTECODE = "1"
$sep = [System.IO.Path]::PathSeparator
$env:PYTHONPATH = "$repo\src$sep$repo"

if (-not $SkipDoctor) {
  & $python .\scripts\doctor-local-repo.py --repo-root $repo --json
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
  Write-Output "doctor=skipped_explicitly; release_preflight_not_certified=true"
}
if (-not $SkipTests) {
  & $python -m pytest -q
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$client = New-Object System.Net.Sockets.TcpClient
try {
  $iar = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
  if ($iar.AsyncWaitHandle.WaitOne(250, $false)) {
    $client.EndConnect($iar)
    throw "port_busy:$Port; recovery_command=Stop-Process -Id (Get-NetTCPConnection -LocalPort $Port).OwningProcess"
  }
} catch [System.Management.Automation.RuntimeException] {
  throw
} catch {
} finally {
  $client.Close()
}

$appTarget = if ($ApiMode -eq "Enterprise") { "app.api.main:app" } else { "maine_family_law_llm.api:app" }
$argsList = @("-m", "uvicorn", $appTarget, "--host", "127.0.0.1", "--port", [string]$Port)
$stdoutLogPath = Join-Path -Path $repo -ChildPath ".local_server.stdout.log"
$stderrLogPath = Join-Path -Path $repo -ChildPath ".local_server.stderr.log"
# Redirecting child output prevents an inherited console pipe from keeping a
# non-interactive launcher invocation open after readiness has been confirmed.
$proc = Start-Process -FilePath $python -ArgumentList $argsList -WorkingDirectory $repo -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput $stdoutLogPath -RedirectStandardError $stderrLogPath
$pidPath = Join-Path -Path $repo -ChildPath ".local_server.pid"
[System.IO.File]::WriteAllText($pidPath, [string]$proc.Id, [System.Text.UTF8Encoding]::new($false))

$healthUrl = "http://127.0.0.1:$Port/api/health"
$deadline = [DateTime]::UtcNow.AddSeconds($StartupTimeoutSeconds)
$ready = $false
while ([DateTime]::UtcNow -lt $deadline) {
  if ($proc.HasExited) {
    Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
    throw "local_api_exited_before_ready:pid=$($proc.Id); diagnostic_logs=$stdoutLogPath,$stderrLogPath; recovery_command=START_LOCAL_TEST.ps1 -ResetEnvironment"
  }
  try {
    $response = Invoke-WebRequest -Uri $healthUrl -TimeoutSec 2 -UseBasicParsing
    if ($response.StatusCode -eq 200) {
      $payload = $response.Content | ConvertFrom-Json
      if ($payload.status -eq "ok") {
        $ready = $true
        break
      }
    }
  } catch {
    # Uvicorn may still be binding the loopback port; retry until the deadline.
  }
  Start-Sleep -Milliseconds 250
}

if (-not $ready) {
  if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force }
  Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
  throw "local_api_start_timeout:$StartupTimeoutSeconds seconds; diagnostic_logs=$stdoutLogPath,$stderrLogPath; recovery_command=START_LOCAL_TEST.ps1 -ResetEnvironment"
}

Write-Output "started_pid=$($proc.Id)"
Write-Output "api_mode=$ApiMode"
Write-Output "api_health=ready"
Write-Output "workbench_url=http://127.0.0.1:$Port/"
Write-Output "docs_url=http://127.0.0.1:$Port/docs"
Write-Output "pid_file=$pidPath"
Write-Output "stdout_log=$stdoutLogPath"
Write-Output "stderr_log=$stderrLogPath"
