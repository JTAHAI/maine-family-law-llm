#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.evals.operator_release_eval import OperatorSourceBackedReleaseEvalRunner


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Pass 46 operator/source-backed release-eval gate without claiming attorney review or legal signoff."
    )
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--eval-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--measurement-output", type=Path)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()

    report = OperatorSourceBackedReleaseEvalRunner(project_root=ROOT).run(
        data_root=args.data_root,
        eval_root=args.eval_root,
        output_path=args.output,
        measurement_output_path=args.measurement_output,
    )
    payload = report.as_dict()
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.require_ready and payload["status"] != "pass":
        return 2
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
