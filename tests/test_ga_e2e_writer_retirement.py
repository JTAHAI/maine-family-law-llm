from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_retired_v6_e2e_writer_refuses_to_emit_current_evidence() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "write-ga-e2e-evidence.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "Refusing to write retired v6 GA E2E evidence" in result.stdout
    assert "do not replay this historical matrix" in result.stdout
