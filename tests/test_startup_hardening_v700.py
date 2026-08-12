from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_normal_local_startup_preserves_environment_and_exposes_safe_reset() -> None:
    script = (ROOT / "START_LOCAL_TEST.ps1").read_text(encoding="utf-8")

    assert "[switch]$ResetEnvironment" in script
    assert "[switch]$RefreshDependencies" in script
    assert "[ValidateRange(1, 65535)]" in script
    assert '"-PreserveVenv"' in script
    assert '"-IncludeVenv"' in script
    assert "if ($ResetEnvironment)" in script
    assert 'import fastapi, uvicorn, pypdf, docx, pytest' in script
    assert 'Write-Output "dependencies=ready; install_skipped=true"' in script
    assert "STOP_LOCAL_TEST.ps1 -RepoRoot $repo" in script
    assert "powershell -NoProfile -ExecutionPolicy Bypass -File .\\REPAIR_LOCAL_REPO.ps1" in script
    assert "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }" in script


def test_local_spin_up_waits_for_health_and_cleans_failed_startup() -> None:
    script = (ROOT / "scripts" / "local-test-spin-up.ps1").read_text(encoding="utf-8")

    assert "[int]$StartupTimeoutSeconds = 30" in script
    assert '$healthUrl = "http://127.0.0.1:$Port/api/health"' in script
    assert "Invoke-WebRequest -Uri $healthUrl" in script
    assert "local_api_exited_before_ready" in script
    assert "local_api_start_timeout" in script
    assert "Stop-Process -Id $proc.Id -Force" in script
    assert 'Write-Output "api_health=ready"' in script
    assert "-RedirectStandardOutput $stdoutLogPath" in script
    assert "-RedirectStandardError $stderrLogPath" in script
    assert "diagnostic_logs=$stdoutLogPath,$stderrLogPath" in script
    assert "[switch]$SkipDoctor" in script
    assert "doctor=skipped_explicitly; release_preflight_not_certified=true" in script


def test_local_api_scripts_validate_ports_and_safe_shutdown_ownership() -> None:
    run_api = (ROOT / "scripts" / "run-local-api.ps1").read_text(encoding="utf-8")
    spin_up = (ROOT / "scripts" / "local-test-spin-up.ps1").read_text(encoding="utf-8")
    stop = (ROOT / "STOP_LOCAL_TEST.ps1").read_text(encoding="utf-8")

    assert "[ValidateRange(1, 65535)]" in run_api
    assert "[switch]$AllowNetworkHost" in run_api
    assert "Refusing to expose a local legal-workbench API" in run_api
    assert "[ValidateRange(1, 65535)]" in spin_up
    assert "refused_to_stop_unverified_pid" in stop
    assert "Get-CimInstance Win32_Process" in stop
    assert "maine_family_law_llm\\.api:app" in stop


def test_repair_stops_verified_service_and_refuses_reparse_point_deletion() -> None:
    repair = (ROOT / "REPAIR_LOCAL_REPO.ps1").read_text(encoding="utf-8")

    assert "function Remove-WorkspacePath" in repair
    assert "ReparsePoint" in repair
    assert "Refusing to remove reparse-point workspace path" in repair
    assert "STOP_LOCAL_TEST.ps1 -RepoRoot $repo" in repair
    assert repair.rstrip().endswith("exit $LASTEXITCODE")
