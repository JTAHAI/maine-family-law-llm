#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from maine_family_law_llm.install_lifecycle_qualification import run_install_lifecycle_qualification


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the synthetic Windows application lifecycle qualification slice.")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-root", default=str(ROOT / "dist" / "store" / "evidence"))
    args = parser.parse_args()
    report = run_install_lifecycle_qualification(Path(args.repo_root), Path(args.evidence_root))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("final_readiness_state") == "READY_FOR_PARTNER_CENTER_UPLOAD" else 1


if __name__ == "__main__":
    raise SystemExit(main())
