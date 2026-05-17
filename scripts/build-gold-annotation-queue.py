#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.evals import GoldAnnotationQueueBuilder


def main() -> int:
    parser = argparse.ArgumentParser(description="Build attorney annotation queue from source manifest.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-items-per-task-type", type=int, default=25)
    parser.add_argument("--reviewer", action="append", default=[], help="Attorney reviewer ID. Repeat to assign multiple reviewers.")
    parser.add_argument("--single-review", action="store_true", help="Disable double-review assignment requirement.")
    parser.add_argument("--csv-output", type=Path, default=None, help="Optional spreadsheet-friendly CSV export.")
    args = parser.parse_args()
    result = GoldAnnotationQueueBuilder(project_root=ROOT).build_from_manifest(
        manifest_path=args.manifest,
        output_path=args.output,
        max_items_per_task_type=args.max_items_per_task_type,
        reviewer_ids=args.reviewer,
        double_review=not args.single_review,
        csv_output_path=args.csv_output,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
