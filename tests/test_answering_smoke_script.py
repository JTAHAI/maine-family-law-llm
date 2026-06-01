from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def test_answering_smoke_script_is_non_mutating_and_green() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "run-answering-smoke.py"

    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
        timeout=45,
    )

    assert completed.returncode == 0
    assert "ANSWERING_SMOKE_OK" in completed.stdout
    assert completed.stderr == ""
