from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from legal.release.pre_push_gate import run_pre_push_gate

ROOT = Path(__file__).resolve().parents[1]


def test_public_source_pre_push_gate_passes_source_hygiene_without_claiming_ga() -> None:
    report = run_pre_push_gate(ROOT).as_dict()

    assert report["status"] == "pass"
    assert report["safe_to_push"] is True
    assert report["production_legal_ready"] is False
    assert report["blockers"] == []
    checks = {check["name"]: check for check in report["checks"]}
    assert checks["local_doctor"]["status"] == "pass"
    assert checks["public_repo_readiness"]["status"] == "pass"
    assert checks["version_consistency"]["status"] == "pass"
    assert checks["launch_evidence_fail_closed"]["status"] == "pass"
    assert checks["launch_evidence_fail_closed"]["details"]["open_passes"] == [48, 49, 50, 51]
    assert checks["launch_evidence_fail_closed"]["details"]["expected_blocked_until_external_evidence"] is True
    assert checks["git_safe_push_wrapper"]["status"] == "pass"


def test_package_version_metadata_is_consistent_and_current() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    init_py = (ROOT / "src" / "maine_family_law_llm" / "__init__.py").read_text(encoding="utf-8")
    release_notes = (ROOT / "docs" / "release-notes.md").read_text(encoding="utf-8")
    pass_changes = (ROOT / "PASS_CHANGES.txt").read_text(encoding="utf-8")

    pyproject_version = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, flags=re.M)
    package_version = re.search(r'__version__\s*=\s*"([^"]+)"', init_py)
    assert pyproject_version is not None
    assert package_version is not None
    assert pyproject_version.group(1) == package_version.group(1) == "1.93.0"
    assert "v1.92.0" in release_notes
    assert "v1.92.0" in pass_changes


def test_public_source_preflight_cli_writes_report(tmp_path: Path) -> None:
    output = tmp_path / "public_source_pre_push_gate.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run-public-source-preflight.py",
            "--repo-root",
            str(ROOT),
            "--output",
            str(output),
            "--require-ready",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    stdout_payload = json.loads(result.stdout)
    assert payload["status"] == "pass"
    assert stdout_payload["safe_to_push"] is True
    assert payload["production_legal_ready"] is False
    assert any(check["name"] == "launch_evidence_fail_closed" for check in payload["checks"])
    assert any(check["name"] == "git_safe_push_wrapper" for check in payload["checks"])


def test_safe_push_wrappers_delegate_to_no_op_safe_python_gate() -> None:
    root_wrapper = (ROOT / "PUSH_SAFE.ps1").read_text(encoding="utf-8")
    ps_wrapper = (ROOT / "scripts" / "git-safe-push.ps1").read_text(encoding="utf-8")
    sh_wrapper = (ROOT / "scripts" / "git-safe-push.sh").read_text(encoding="utf-8")
    python_wrapper = (ROOT / "scripts" / "git-safe-push.py").read_text(encoding="utf-8")
    python_module = (ROOT / "legal" / "release" / "git_safe_push.py").read_text(encoding="utf-8")

    for text in (root_wrapper, ps_wrapper, sh_wrapper):
        assert "git-safe-push.py" in text
        assert "git_safe_push_v192.json" in text
        assert "git commit" not in text
        assert "git push -u origin" not in text

    assert "run_git_safe_push" in python_wrapper
    assert "--dry-run" in python_wrapper
    assert "git diff" in python_module
    assert "--cached" in python_module
    assert "--quiet" in python_module
    assert "No staged changes; skipping commit." in python_module
    assert "test_git_safe_push_v192.py" in python_module


def test_ci_runs_pre_push_and_launch_guardrails() -> None:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "run-public-source-preflight.py" in ci
    assert "doctor-local-repo.py" in ci
    assert "run-chat-library-evidence.py" in ci
    assert "test_pass48_51_launch_evidence_gates.py" in ci
    assert "test_public_source_pre_push_gate_v191.py" in ci
    assert "test_git_safe_push_v192.py" in ci
