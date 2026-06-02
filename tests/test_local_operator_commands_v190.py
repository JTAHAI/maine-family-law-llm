from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_v190_doctor_underscore_wrapper_exists_and_delegates() -> None:
    wrapper = ROOT / "scripts" / "doctor_local_repo.py"
    canonical = ROOT / "scripts" / "doctor-local-repo.py"
    assert wrapper.is_file()
    assert canonical.is_file()
    text = wrapper.read_text(encoding="utf-8")
    assert "doctor-local-repo.py" in text
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "clean-local-artifacts.py"), "--repo-root", str(ROOT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    result = subprocess.run(
        [sys.executable, str(wrapper), "--repo-root", str(ROOT), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"status": "pass"' in result.stdout


def test_v190_pyproject_extras_are_the_canonical_operator_install_path() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "uvicorn" in pyproject
    assert "pytest" in pyproject
    assert 'version = "1.90.0"' in pyproject
    docs = (ROOT / "docs" / "chat-language-coverage-local-commands-pass-v190.md").read_text(encoding="utf-8")
    assert 'python -m pip install -e ".[dev,api]"' in docs
