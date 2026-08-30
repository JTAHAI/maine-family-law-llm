from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from app import store_entrypoint as entry

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = r"D:\fictional-private\record.txt contains fictional confidential text"


@pytest.mark.parametrize(
    "mode", ["--smoke-test", "--serve-local-api", "--document-intelligence-worker"]
)
@pytest.mark.parametrize("failure_point", ["context", "configure", "operation"])
def test_unattended_failures_never_open_desktop_dialogs(
    monkeypatch, tmp_path: Path, mode: str, failure_point: str
) -> None:
    def fail(*args, **kwargs):
        raise FileNotFoundError(PRIVATE)

    def forbidden(*args, **kwargs):
        pytest.fail("Unattended process attempted to open a desktop dialog")

    logged = []
    monkeypatch.setattr(entry, "log_exception", lambda ctx, exc: logged.append(str(exc)))
    monkeypatch.setattr(entry.tk, "Tk", forbidden)
    monkeypatch.setattr(entry.messagebox, "showerror", forbidden)
    monkeypatch.setattr(entry, "build_runtime_context", lambda **kw: object())
    monkeypatch.setattr(entry, "configure_runtime_environment", lambda ctx: ctx)
    if failure_point == "context":
        monkeypatch.setattr(entry, "build_runtime_context", fail)
    elif failure_point == "configure":
        monkeypatch.setattr(entry, "configure_runtime_environment", fail)
    else:
        monkeypatch.setattr(entry, "run_local_service", fail)
        monkeypatch.setattr(entry, "_run_smoke_workflow", fail)
        from legal.document_intelligence import worker

        monkeypatch.setattr(worker, "main", fail)
    output = tmp_path / "smoke.json"
    args = [mode]
    if mode == "--smoke-test":
        args += ["--smoke-json", str(output)]
        output.write_text('{"launch_result":"pass"}', encoding="utf-8")
    elif mode == "--document-intelligence-worker":
        args += ["ocr", "fictional.txt"]
    assert entry.main(args) == 1
    assert PRIVATE not in str(logged)
    if mode == "--smoke-test":
        result = json.loads(output.read_text(encoding="utf-8"))
        assert result["launch_result"] == "fail"
        assert result["error_code"] == "runtime_start_failed"
        assert PRIVATE not in str(result)


def test_failed_logging_does_not_mask_unattended_failure(monkeypatch, tmp_path: Path) -> None:
    def fail(*args, **kwargs):
        raise OSError(PRIVATE)

    monkeypatch.setattr(entry, "build_runtime_context", lambda **kw: object())
    monkeypatch.setattr(entry, "configure_runtime_environment", lambda ctx: ctx)
    monkeypatch.setattr(entry, "run_local_service", fail)
    monkeypatch.setattr(entry, "log_exception", fail)
    monkeypatch.setattr(entry.tk, "Tk", lambda: pytest.fail("desktop dialog"))
    assert entry.main(["--serve-local-api"]) == 1


def test_interactive_error_is_content_free_and_destroys_dialog(monkeypatch) -> None:
    events = []

    class Dialog:
        def withdraw(self):
            events.append("withdraw")

        def destroy(self):
            events.append("destroy")

    def fail(**kwargs):
        raise OSError(PRIVATE)

    monkeypatch.setattr(entry, "build_runtime_context", fail)
    monkeypatch.setattr(entry.tk, "Tk", Dialog)
    monkeypatch.setattr(entry.messagebox, "showerror", lambda *a, **kw: events.append(a[1]))
    assert entry.main([]) == 1
    assert PRIVATE not in str(events)
    assert "runtime_start_failed" in str(events)
    assert events[-1] == "destroy"


def test_offline_build_requires_preexisting_environment_without_mutating_output(
    tmp_path: Path,
) -> None:
    shell = shutil.which("powershell") or shutil.which("pwsh")
    if not shell:
        pytest.skip("PowerShell required for Windows build-script execution")
    # The production script now refuses external build output. Keep this
    # negative fixture's mutable sentinel under the repository's ignored dist
    # tree while its fake cached environment stays outside the repository.
    output = ROOT / "dist" / "qa801" / "offline-build-fixtures" / tmp_path.name
    output.mkdir(parents=True, exist_ok=True)
    sentinel = output / "preserve.txt"
    sentinel.write_text("existing output", encoding="utf-8")
    env = os.environ.copy()
    # Windows GetFolderPath reads the profile registry, not LOCALAPPDATA.
    # Redirect only the build-cache location in a copy of the real script;
    # never let a negative fixture start PyInstaller in the user's real venv.
    source = (ROOT / "scripts/build-store-runtime.ps1").read_text(encoding="utf-8")
    cache_line = next(line for line in source.splitlines() if line.startswith("$venvRoot = "))
    legacy_cache_line = next(
        line for line in source.splitlines() if line.startswith("$legacyVenvRoot = ")
    )
    missing_cache = tmp_path / "missing-build-environment"
    fixture_script = tmp_path / "build-store-runtime.ps1"
    fixture_script.write_text(
        source.replace(
            cache_line,
            "$venvRoot = '" + str(missing_cache).replace("'", "''") + "'",
        ).replace(
            legacy_cache_line,
            "$legacyVenvRoot = '" + str(missing_cache).replace("'", "''") + "'",
        ),
        encoding="utf-8",
    )
    shutil.copy2(ROOT / "scripts/store-build-workspace.ps1", tmp_path / "store-build-workspace.ps1")
    result = subprocess.run(
        [
            shell,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(fixture_script),
            "-RepoRoot",
            str(ROOT),
            "-OutputRoot",
            str(output),
            "-Offline",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert result.returncode != 0
    assert "existing provisioned Store build environment" in result.stdout + result.stderr
    assert sentinel.read_text(encoding="utf-8") == "existing output"
    assert not missing_cache.exists()


def test_offline_build_and_isolated_smoke_are_wired_through_canonical_scripts() -> None:
    build = (ROOT / "scripts/build-msix.ps1").read_text(encoding="utf-8")
    runtime = (ROOT / "scripts/build-store-runtime.ps1").read_text(encoding="utf-8")
    smoke = (ROOT / "scripts/test-store-runtime.ps1").read_text(encoding="utf-8")
    assert "[switch]$Offline" in build and "-Offline:$Offline" in build
    assert "-not $SkipDependencyInstall -and -not $Offline" in runtime
    assert "-Destination $whisperRuntimeRoot -Offline:$Offline" in runtime
    assert 'if ($Offline) { throw "Offline full build requires cached Docling' in runtime
    assert 'if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed' in runtime
    assert '"mfl-frozen-smoke-"' in smoke and "-WindowStyle Hidden" in smoke
    assert "$env:LOCALAPPDATA = $priorLocalAppData" in smoke
    assert "build-store-runtime.ps1" not in smoke
