from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_outreach_truthfulness_script_passes_and_confirms_no_outreach_sent() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check-outreach-truthfulness.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "pass"
    assert payload["emails_sent"] is False
    assert payload["outreach_complete"] is False
    assert payload["attorney_reviewed"] is False
