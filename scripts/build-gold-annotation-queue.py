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
from legal.evals.external_eval_root import default_external_eval_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Build attorney annotation queue from source manifest.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-items-per-task-type", type=int, default=25)
    parser.add_argument("--reviewer", action="append", default=[], help="Attorney reviewer ID. Repeat to assign multiple reviewers.")
    parser.add_argument("--single-review", action="store_true", help="Disable double-review assignment requirement.")
    parser.add_argument("--csv-output", type=Path, default=None, help="Optional spreadsheet-friendly CSV export.")
    parser.add_argument("--dataset-filter", action="append", default=[], help="Only include rows for these dataset names.")
    parser.add_argument("--source-class-filter", action="append", default=[], help="Only include source classes that match.")
    parser.add_argument("--issue-filter", action="append", default=[], help="Only include rows with these issue labels.")
    parser.add_argument("--posture-filter", action="append", default=[], help="Only include rows with these posture labels.")
    parser.add_argument("--target-dataset-type", default=None, help="Only build rows for one dataset type.")
    parser.add_argument("--seed", default=None, help="Bounded randomization seed for reproducible queue order.")
    parser.add_argument("--dry-run", action="store_true", help="Summarize the queue without writing output files.")
    parser.add_argument("--include-fixture-candidates", action="store_true", help="Allow clearly synthetic fixtures into the queue.")
    parser.add_argument("--summary-output", type=Path, default=None, help="Optional machine-readable summary output path.")
    parser.add_argument("--eval-root", type=Path, default=None, help="Optional external eval root for write-time validation.")
    args = parser.parse_args()
    eval_root = args.eval_root or default_external_eval_root(ROOT)
    result = GoldAnnotationQueueBuilder(project_root=ROOT).build_from_manifest(
        manifest_path=args.manifest,
        output_path=args.output,
        max_items_per_task_type=args.max_items_per_task_type,
        reviewer_ids=args.reviewer,
        double_review=not args.single_review,
        csv_output_path=args.csv_output,
        dataset_filter=args.dataset_filter,
        source_class_filter=args.source_class_filter,
        issue_filter=args.issue_filter,
        posture_filter=args.posture_filter,
        target_dataset_type=args.target_dataset_type,
        seed=args.seed,
        dry_run=args.dry_run,
        include_fixture_candidates=args.include_fixture_candidates,
        summary_output_path=args.summary_output or (eval_root / "annotation_queue" / "gold_annotation_queue_summary.json"),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
