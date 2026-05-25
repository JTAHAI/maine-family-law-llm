param(
  [string]$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path,
  [int]$Port = 8000,
  [switch]$SkipTests,
  [string]$PythonExe = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repo = [System.IO.Path]::GetFullPath($RepoRoot)
Set-Location -LiteralPath $repo
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONPATH = "$repo\src;$repo"

python .\scripts\doctor-local-repo.py --repo-root $repo --json --allow-venv
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if (-not $SkipTests) {
  python -m pytest -q
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

$python = if ($PythonExe) { $PythonExe } else { (Get-Command python).Source }
$argsList = @("-m", "uvicorn", "maine_family_law_llm.api:app", "--host", "127.0.0.1", "--port", [string]$Port)
$proc = Start-Process -FilePath $python -ArgumentList $argsList -WorkingDirectory $repo -WindowStyle Hidden -PassThru
$pidPath = Join-Path -Path $repo -ChildPath ".local_server.pid"
[System.IO.File]::WriteAllText($pidPath, [string]$proc.Id, [System.Text.UTF8Encoding]::new($false))
Write-Output "started_pid=$($proc.Id)"
Write-Output "docs_url=http://127.0.0.1:$Port/docs"
Write-Output "pid_file=$pidPath"
