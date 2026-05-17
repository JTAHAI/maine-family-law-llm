#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.evals import ReleaseMetricsEvidenceBuilder


def main() -> int:
    parser = argparse.ArgumentParser(description="Build release metrics evidence from gold eval artifacts.")
    parser.add_argument("--eval-root", type=Path, default=ROOT / "eval_data")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = ReleaseMetricsEvidenceBuilder(project_root=ROOT, eval_root=args.eval_root).build(
        output_path=args.output,
    )
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
