from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_conversation_quality_regression_script_outputs_json(tmp_path: Path) -> None:
    output = tmp_path / "quality-report.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run-conversation-quality-regression.py"),
            str(output),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "pass"
    assert payload["case_count"] >= 40
    assert output.is_file()
