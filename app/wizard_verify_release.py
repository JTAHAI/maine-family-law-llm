from __future__ import annotations

import json
from pathlib import Path


def verify_release(case_root: Path) -> dict[str, object]:
    proof_path = case_root / "15_PROOF_VALIDATION" / "CASE_BUILD_PROOF.json"
    if not proof_path.exists():
        return {"result": "FAIL", "missing": [str(proof_path)]}
    return {"result": "PASS", "proof": json.loads(proof_path.read_text(encoding="utf-8"))}
