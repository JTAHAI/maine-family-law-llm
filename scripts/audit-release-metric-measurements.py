#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.evals import ReleaseMetricMeasurementAuditor


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit task-specific release metric measurements for GA use.")
    parser.add_argument("--measurement-path", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--allow-repo-path", action="store_true", help="Only for unit tests/fixtures; GA measurements must be external.")
    parser.add_argument("--require-ready", action="store_true", help="Exit non-zero unless the measurement file passes.")
    args = parser.parse_args()
    report = ReleaseMetricMeasurementAuditor(project_root=ROOT).audit(
        measurement_path=args.measurement_path,
        output_path=args.output,
        allow_repo_path=args.allow_repo_path,
    )
    payload = report.as_dict()
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.require_ready and payload["status"] != "pass":
        return 2
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
