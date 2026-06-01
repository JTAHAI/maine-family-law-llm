from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
TIMEOUT = 45


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "src"), str(ROOT)])
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _run(args: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        env=_env(),
        text=True,
        capture_output=True,
        check=check,
        timeout=TIMEOUT,
    )


def test_cli_smoke_sources_ask_draft_and_doctor() -> None:
    base = ["python", "-m", "maine_family_law_llm.cli"]
    for args in (
        ["sources", "validate"],
        ["sources", "list"],
        ["sources", "fetch", "--fixtures"],
        ["sources", "normalize", "--fixtures"],
        ["index", "build", "--fixtures"],
    ):
        result = _run(base + args)
        assert result.returncode == 0, result.stderr + result.stdout

    ask = _run(base + ["ask", "How do I start a family matter?"])
    assert ask.returncode == 0
    assert "Citation appendix" in ask.stdout

    draft = _run(base + ["draft", "child support form checklist"])
    assert draft.returncode == 0
    assert "not filing-ready" in draft.stdout


def test_api_endpoints_use_same_safety_and_sources() -> None:
    pytest.importorskip("fastapi")
    from maine_family_law_llm import api

    assert api.app is not None
    assert api.healthz()["status"] == "ok"
    assert api.api_health()["status"] == "ok"
    assert api.sources()

    ask = api.ask(api.AskRequest(question="How do I start a family matter?"))
    assert ask["citations"]

    unsafe = api.ask(api.AskRequest(question="I need protection from abuse and immediate danger help"))
    assert unsafe["safety"]["requires_emergency_language"] is True

    draft = api.draft(api.DraftRequest(request="child support form checklist"))
    assert "not filing-ready" in draft["text"]

    inspect = api.inspect_source("mrs-title-19a-domestic-relations")
    assert inspect["official"] is True


def test_local_scripts_exist_parse_and_doctor_json() -> None:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    scripts = [
        ROOT / "START_LOCAL_TEST.ps1",
        ROOT / "START_LOCAL_CHAT.ps1",
        ROOT / "STOP_LOCAL_TEST.ps1",
        ROOT / "CHECK_LOCAL_REPO.ps1",
        ROOT / "CREATE_REVIEW_ZIP.ps1",
        ROOT / "REPAIR_LOCAL_REPO.ps1",
        ROOT / "scripts" / "local-test-spin-up.ps1",
        ROOT / "scripts" / "run-tests.ps1",
    ]
    for script in scripts:
        assert script.exists(), f"missing script: {script}"

    if shell is None:
        pytest.skip("PowerShell parser unavailable on this runner")

    for script in scripts:
        result = subprocess.run(
            [
                shell,
                "-NoProfile",
                "-Command",
                f"$tokens=$null; $errors=$null; "
                f"[System.Management.Automation.Language.Parser]::ParseFile('{script}', [ref]$tokens, [ref]$errors) | Out-Null; "
                "if($errors.Count){ $errors | ConvertTo-Json; exit 1 }",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=TIMEOUT,
        )
        assert result.returncode == 0, result.stderr + result.stdout

    _run(["python", "scripts/clean-local-artifacts.py", "--repo-root", str(ROOT)])
    doctor = _run(["python", "scripts/doctor-local-repo.py", "--repo-root", str(ROOT), "--json"])
    payload = json.loads(doctor.stdout)
    assert payload["status"] == "pass"
    assert payload["safe_to_push"] is True
