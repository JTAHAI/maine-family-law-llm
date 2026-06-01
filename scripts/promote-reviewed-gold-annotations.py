#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.evals import ReviewedGoldAnnotationPromoter


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Promote attorney-reviewed annotation queue rows into gold JSONL datasets."
    )
    parser.add_argument("--reviewed-queue", type=Path, required=True)
    parser.add_argument("--eval-root", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to existing gold JSONL datasets instead of replacing them.",
    )
    parser.add_argument(
        "--require-promoted",
        action="store_true",
        help="Exit non-zero unless at least one attorney-reviewed row was promoted.",
    )
    args = parser.parse_args()

    report = ReviewedGoldAnnotationPromoter(project_root=ROOT).promote(
        reviewed_queue_path=args.reviewed_queue,
        eval_root=args.eval_root,
        output_report_path=args.output_report,
        append=args.append,
    )
    payload = report.as_dict()
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.require_promoted and payload["status"] != "pass":
        return 2
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
