#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.ops import run_final_local_acceptance


def main() -> int:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "sample-evidence" / "final_local_acceptance_evidence.json"
    evidence = run_final_local_acceptance(ROOT)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
