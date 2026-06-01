#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.evals.retrieval_smoke import RetrievalSmokeEvalRunner


def main() -> int:
    parser = argparse.ArgumentParser(description="Run measured retrieval smoke eval over indexed Maine authority.")
    parser.add_argument("--data-root", required=True, help="External data root with embedding_store indexes.")
    parser.add_argument("--eval-root", default=None, help="External eval root. Defaults to <data-root>/eval_store.")
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--min-case-count", type=int, default=1)
    parser.add_argument("--min-recall-at-20", type=float, default=0.9)
    parser.add_argument(
        "--max-case-count",
        type=int,
        default=None,
        help="Bound source-derived smoke cases. Defaults to max(25, --min-case-count) to keep local GA runs finite.",
    )
    parser.add_argument("--progress-interval", type=int, default=10, help="Write progress JSON every N cases.")
    args = parser.parse_args()
    report = RetrievalSmokeEvalRunner(data_root=args.data_root, eval_root=args.eval_root).run(
        write_report=True,
        top_k=args.top_k,
        min_case_count=args.min_case_count,
        min_recall_at_20=args.min_recall_at_20,
        max_case_count=args.max_case_count,
        progress_interval=args.progress_interval,
    )
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
