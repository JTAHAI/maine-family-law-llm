from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_doc_unsafe_claims_script_passes_and_keeps_production_legal_ready_false() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check-doc-unsafe-claims.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "pass"
    assert payload["production_legal_ready"] is False
    assert payload["finding_count"] == 0
