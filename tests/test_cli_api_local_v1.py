from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ROOT / 'src'};{ROOT}"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def test_cli_smoke_sources_ask_draft_and_doctor() -> None:
    subprocess.run(
        ["python", "scripts/clean-local-artifacts.py", "--repo-root", str(ROOT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=_env(),
    )
    base = ["python", "-m", "maine_family_law_llm.cli"]
    for args in (
        ["sources", "validate"],
        ["sources", "list"],
        ["sources", "fetch", "--fixtures"],
        ["sources", "normalize", "--fixtures"],
        ["index", "build", "--fixtures"],
        ["doctor"],
    ):
        result = subprocess.run(base + args, cwd=ROOT, env=_env(), text=True, capture_output=True, check=False)
        assert result.returncode == 0, result.stderr + result.stdout

    ask = subprocess.run(base + ["ask", "How do I start a family matter?"], cwd=ROOT, env=_env(), text=True, capture_output=True, check=False)
    assert ask.returncode == 0
    assert "Citation appendix" in ask.stdout

    draft = subprocess.run(base + ["draft", "child support form checklist"], cwd=ROOT, env=_env(), text=True, capture_output=True, check=False)
    assert draft.returncode == 0
    assert "not filing-ready" in draft.stdout


def test_api_endpoints_use_same_safety_and_sources() -> None:
    fastapi = pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from maine_family_law_llm.api import app

    assert fastapi
    client = TestClient(app)
    assert client.get("/healthz").json()["status"] == "ok"
    assert client.get("/sources").json()

    ask = client.post("/ask", json={"question": "How do I start a family matter?"})
    assert ask.status_code == 200
    assert ask.json()["citations"]

    unsafe = client.post("/ask", json={"question": "I need protection from abuse and immediate danger help"})
    assert unsafe.json()["safety"]["requires_emergency_language"] is True

    draft = client.post("/draft", json={"request": "child support form checklist"})
    assert "not filing-ready" in draft.json()["text"]

    inspect = client.get("/inspect-source/mrs-title-19a-domestic-relations")
    assert inspect.json()["official"] is True


def test_local_scripts_exist_parse_and_doctor_json() -> None:
    scripts = [
        ROOT / "START_LOCAL_TEST.ps1",
        ROOT / "REPAIR_LOCAL_REPO.ps1",
        ROOT / "scripts" / "local-test-spin-up.ps1",
        ROOT / "scripts" / "run-tests.ps1",
    ]
    for script in scripts:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"$tokens=$null; $errors=$null; [System.Management.Automation.Language.Parser]::ParseFile('{script}', [ref]$tokens, [ref]$errors) | Out-Null; if($errors.Count){{ $errors | ConvertTo-Json; exit 1 }}",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr + result.stdout

    subprocess.run(
        ["python", "scripts/clean-local-artifacts.py", "--repo-root", str(ROOT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=_env(),
    )
    doctor = subprocess.run(
        ["python", "scripts/doctor-local-repo.py", "--repo-root", str(ROOT), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=_env(),
    )
    payload = json.loads(doctor.stdout)
    assert payload["status"] == "pass"
